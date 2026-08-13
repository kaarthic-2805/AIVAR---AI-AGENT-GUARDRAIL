import os
import certifi
from dotenv import load_dotenv

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import Any, TypedDict, Annotated, List, Dict
import operator
import uuid
import asyncio
import json
import psycopg
from psycopg.rows import dict_row
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command, interrupt
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq

from action_guardrail import evaluator, audit_logger
from mcp_client import (
    tavily_mcp_search,
    weather_mcp_search,
    extract_location,
    execute_db_delete_tool,
    execute_send_email_tool,
    execute_read_path_tool,
)


raw_groq_keys = os.getenv("GROQ_API_KEY", "")
groq_keys = [k.strip() for k in raw_groq_keys.split(",") if k.strip()]
if not groq_keys:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")

primary_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

llm_chain = []
for k in groq_keys:
    llm_chain.append(ChatGroq(model=primary_model, api_key=k))
    llm_chain.append(ChatGroq(model=fallback_model, api_key=k))

primary_llm = llm_chain[0]
fallback_llms = llm_chain[1:]
llm = primary_llm.with_fallbacks(fallback_llms) if fallback_llms else primary_llm


# =========================
# Real Estate Graph State
# =========================
class RealEstateState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    dry_run: bool

    # Supervisor + guardrail state
    guardrail_allowed: bool
    guardrail_reason: str
    selected_agents: list[str]
    property_constraints: dict[str, Any]
    supervisor_reasoning: str

    # Specialist agent results
    property_results: str
    valuation_results: str
    neighborhood_results: str
    action_results: str
    action_evaluations: list[dict]
    proposal: str

    # HITL state
    approval_request: str
    approved: bool
    human_feedback: str
    final_response: str

    llm_calls: int


# =========================
# Shared Helpers
# =========================
KNOWN_AGENTS = {
    "property_search_agent",
    "valuation_agent",
    "neighborhood_agent",
    "action_dispatch_agent",
    "property_plan_agent",
}

AGENT_ORDER = [
    "property_search_agent",
    "valuation_agent",
    "neighborhood_agent",
    "action_dispatch_agent",
    "property_plan_agent",
]


def _llm_text(system_prompt: str, user_prompt: str) -> str:
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    return str(response.content)


def _json_from_llm(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("The model did not return a JSON object.")
    return json.loads(text[start : end + 1])


def _empty_constraints() -> dict[str, Any]:
    return {
        "location": "",
        "property_type": "",
        "max_price": "",
        "bedrooms": "",
        "special_requests": [],
    }


# =========================
# Supervisor Agent + Input Guardrail
# =========================
def supervisor_agent(state: RealEstateState):
    query = state["user_query"]
    llm_calls = state.get("llm_calls", 0)

    guardrail_prompt = f"""
You are evaluating whether a user request belongs to EstateGuard AI (a Real Estate multi-agent system).

VALID REQUESTS (Set allowed = true):
- Searching for real estate properties, listings, estates, homes, villas, or apartments.
- Real estate valuation, price estimation, market trends, ROI, or neighborhood amenities.
- Sending emails containing real estate proposals, property showcases, or listing reports.
- Managing property database records or reading property documents.

INVALID REQUESTS (Set allowed = false only if completely unrelated):
- Topics totally unrelated to real estate (e.g., medical/health advice, flight/hotel bookings, sports, cooking, illegal content).

Return strict JSON only:
{{
  "allowed": true,
  "reason": "Brief explanation"
}}

User request:
{query}
"""

    try:
        guardrail_raw = _llm_text(
            "You are the input guardrail for EstateGuard Real Estate AI. Return strict JSON only.",
            guardrail_prompt,
        )
        guardrail_result = _json_from_llm(guardrail_raw)
        allowed = bool(guardrail_result.get("allowed", True))
        guardrail_reason = str(guardrail_result.get("reason", "")).strip()
        llm_calls += 1
    except Exception as exc:
        print(f"Guardrail fallback used: {exc}")
        allowed = True
        guardrail_reason = "Guardrail validation fallback allowed the request."

    if not allowed:
        reason = guardrail_reason or (
            "EstateGuard AI can only assist with Real Estate requests, property valuations, listing actions, or document operations."
        )
        return {
            "guardrail_allowed": False,
            "guardrail_reason": reason,
            "selected_agents": [],
            "property_constraints": _empty_constraints(),
            "supervisor_reasoning": reason,
            "final_response": reason,
            "messages": [AIMessage(content=f"Guardrail blocked request: {reason}")],
            "llm_calls": llm_calls,
        }

    supervisor_prompt = f"""
You are the supervisor of a multi-agent Real Estate system.
Select the specialist agents required for this request.

Available agents:
- property_search_agent: property listings, features, location search, price ranges
- valuation_agent: property valuation, ROI estimation, market comparison, mortgage advice
- neighborhood_agent: neighborhood amenities, school ratings, crime, weather/climate
- action_dispatch_agent: required whenever the request asks to delete database records, send emails, or read file paths
- property_plan_agent: synthesizes the final real estate plan / proposal (must always be included)

Return strict JSON only using this schema:
{{
  "selected_agents": ["property_search_agent", "valuation_agent", "neighborhood_agent", "action_dispatch_agent", "property_plan_agent"],
  "property_constraints": {{
    "location": "",
    "property_type": "",
    "max_price": "",
    "bedrooms": "",
    "special_requests": []
  }},
  "reasoning": ""
}}

User request:
{query}
"""

    try:
        supervisor_raw = _llm_text(
            "You route work to real estate specialist agents. Return strict JSON only.",
            supervisor_prompt,
        )
        parsed = _json_from_llm(supervisor_raw)
        requested_agents = parsed.get("selected_agents", [])
        selected_agents = [
            name for name in AGENT_ORDER
            if name in requested_agents and name in KNOWN_AGENTS
        ]

        if "property_plan_agent" not in selected_agents:
            selected_agents.append("property_plan_agent")

        constraints = _empty_constraints()
        parsed_constraints = parsed.get("property_constraints", {})
        if isinstance(parsed_constraints, dict):
            constraints.update(parsed_constraints)

        reasoning = str(parsed.get("reasoning", "")).strip()
        llm_calls += 1
    except Exception as exc:
        print(f"Supervisor fallback used: {exc}")
        selected_agents = AGENT_ORDER.copy()
        constraints = _empty_constraints()
        reasoning = "Supervisor routing selected all real estate agents as safe fallback."

    return {
        "guardrail_allowed": True,
        "guardrail_reason": guardrail_reason,
        "selected_agents": selected_agents,
        "property_constraints": constraints,
        "supervisor_reasoning": reasoning,
        "messages": [AIMessage(content="Supervisor created execution plan.")],
        "llm_calls": llm_calls,
    }


def guardrail_blocked_agent(state: RealEstateState):
    reason = state.get("final_response") or state.get("guardrail_reason") or (
        "This request was blocked by the Real Estate input guardrail."
    )
    return {
        "final_response": reason,
        "messages": [AIMessage(content=reason)],
    }


# =========================
# Specialist Agents
# =========================

def property_search_agent(state: RealEstateState):
    query = f"Real estate property listings for {state['user_query']}"
    try:
        search_data = asyncio.run(tavily_mcp_search(query))
    except Exception as exc:
        search_data = f"Live listing search unavailable: {exc}"

    return {
        "property_results": str(search_data),
        "messages": [AIMessage(content="Property listings processed.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def valuation_agent(state: RealEstateState):
    prompt = f"""
Provide property valuation and financial analysis for this real estate query:
Query: {state['user_query']}
Property Search Data: {state.get('property_results', '')[:1500]}

Include:
1. Estimated market valuation range
2. Projected annual ROI & rental yield
3. Estimated monthly mortgage/payment breakdown
4. Key investment risks & opportunities
"""
    response = llm.invoke([
        SystemMessage(content="You are a senior real estate financial analyst."),
        HumanMessage(content=prompt),
    ])

    return {
        "valuation_results": response.content,
        "messages": [AIMessage(content="Valuation and financial analysis completed.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def neighborhood_agent(state: RealEstateState):
    location = extract_location(state["user_query"])
    try:
        weather_info = asyncio.run(weather_mcp_search(location))
    except Exception:
        weather_info = "Mild climate with seasonal changes."

    prompt = f"""
Evaluate the neighborhood and location quality for {location}.
Query: {state['user_query']}
Climate/Weather Data: {weather_info}

Include:
1. School district ratings & healthcare facilities
2. Safety, crime index, and neighborhood vibe
3. Public transit and highway accessibility
4. Climate and seasonal guidance for living in {location}
"""
    response = llm.invoke([
        SystemMessage(content="You are an expert real estate neighborhood consultant."),
        HumanMessage(content=prompt),
    ])

    return {
        "neighborhood_results": response.content,
        "messages": [AIMessage(content="Neighborhood analysis generated.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def action_dispatch_agent(state: RealEstateState):
    """
    Evaluates and executes tool calls (delete_records, send_email, read_path)
    guarded pre-execution by ActionEvaluator against policy rules.
    """
    query = state["user_query"].lower()
    dry_run = state.get("dry_run", False)
    evaluations = []
    action_logs = []

    # Scenario 1: Database Delete
    if "delete" in query or "remove" in query:
        record_count = 500 if ("500" in query or "bulk" in query or "many" in query) else 5
        res = execute_db_delete_tool(
            table="property_listings",
            record_count=record_count,
            agent_id="action_dispatch_agent",
            dry_run=dry_run,
        )
        evaluations.append(res["eval_result"])
        action_logs.append(f"DB Delete Action ({record_count} records): {res['message']}")

    # Scenario 2: Send Email
    if "email" in query or "send proposal" in query or "mail" in query:
        import re
        emails_found = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", state.get("user_query", ""))
        if emails_found:
            recipient = emails_found[0]
        elif "external" in query:
            recipient = "client@externaldomain.com"
        else:
            recipient = "team@realestate.com"

        res = execute_send_email_tool(
            recipient=recipient,
            subject="Real Estate Property Proposal",
            body="Attached property evaluation report.",
            agent_id="action_dispatch_agent",
            dry_run=dry_run,
        )
        evaluations.append(res["eval_result"])
        action_logs.append(f"Email Dispatch Action ({recipient}): {res['message']}")

    # Scenario 3: Read Document / File Path
    if "read" in query or "deed" in query or "confidential" in query or "document" in query or "path" in query:
        path = "/documents/confidential_title_deed.pdf" if "confidential" in query else "/public/brochure.pdf"
        res = execute_read_path_tool(
            path=path,
            agent_id="action_dispatch_agent",
            dry_run=dry_run,
        )
        evaluations.append(res["eval_result"])
        action_logs.append(f"Document Read Action ({path}): {res['message']}")

    summary_text = "\n".join(action_logs) if action_logs else "No explicit database delete, email, or path read actions were requested."

    return {
        "action_results": summary_text,
        "action_evaluations": evaluations,
        "messages": [AIMessage(content="Action evaluations completed by Action Guardrail.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def property_plan_agent(state: RealEstateState):
    prompt = f"""
Create a comprehensive Real Estate Plan / Proposal.

User Query: {state['user_query']}
Property Listings: {state.get('property_results', '')[:1000]}
Valuation & Financial Analysis: {state.get('valuation_results', '')}
Neighborhood Analysis: {state.get('neighborhood_results', '')}
Pre-Execution Tool Action Guardrail Results:
{state.get('action_results', '')}

Structure the draft proposal clearly:
1. Executive Summary & Property Recommendations
2. Valuation & ROI Analysis
3. Neighborhood & Location Profile
4. Tool Actions & Action Guardrail Audit Status
5. Next Steps & Approval Guidance
"""

    response = llm.invoke([
        SystemMessage(content="You are a lead Real Estate advisory agent."),
        HumanMessage(content=prompt),
    ])

    approval_req = "Please review the generated Real Estate Plan. Approve to finalize or submit feedback for revision."

    return {
        "proposal": response.content,
        "approval_request": approval_req,
        "messages": [AIMessage(content="Draft proposal created for human review.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def human_approval_agent(state: RealEstateState):
    review = interrupt(
        {
            "question": "Do you approve this Real Estate proposal?",
            "draft_proposal": state.get("proposal", ""),
            "approval_request": state.get("approval_request", ""),
            "selected_agents": state.get("selected_agents", []),
            "supervisor_reasoning": state.get("supervisor_reasoning", ""),
            "action_evaluations": state.get("action_evaluations", []),
        }
    )

    approved = bool(review.get("approved", False))
    human_feedback = str(review.get("feedback", "")).strip()

    return {
        "approved": approved,
        "human_feedback": human_feedback,
        "messages": [AIMessage(content="Human-in-the-Loop review completed.")],
    }


def final_agent(state: RealEstateState):
    if state.get("approved", False):
        review_instruction = "The user approved the draft. Finalize and polish the proposal."
    else:
        review_instruction = f"The user requested revision: {state.get('human_feedback', '') or 'Revise as needed.'}"

    final_prompt = f"""
Generate the final Real Estate Advisory response.

Review Status: {review_instruction}
User Query: {state['user_query']}
Property Search: {state.get('property_results', '')[:800]}
Valuation: {state.get('valuation_results', '')}
Neighborhood: {state.get('neighborhood_results', '')}
Guarded Actions: {state.get('action_results', '')}
Draft Proposal: {state.get('proposal', '')}

Format in clean GitHub markdown:
# Real Estate Investment & Action Audit Report
## 1. Property Overview & Recommendations
## 2. Financial Valuation & ROI Estimate
## 3. Neighborhood & Location Analysis
## 4. Pre-Execution Action Guardrail Audit Log
## 5. Final Advisory Summary
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional Real Estate Advisory Assistant."),
        HumanMessage(content=final_prompt),
    ])

    return {
        "final_response": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Dynamic Supervisor Routing
# =========================
ROUTE_MAP = {
    "guardrail_blocked": "guardrail_blocked",
    "property_search_agent": "property_search_agent",
    "valuation_agent": "valuation_agent",
    "neighborhood_agent": "neighborhood_agent",
    "action_dispatch_agent": "action_dispatch_agent",
    "property_plan_agent": "property_plan_agent",
}


def _selected_agents(state: RealEstateState) -> list[str]:
    selected = state.get("selected_agents", [])
    return [agent for agent in AGENT_ORDER if agent in selected]


def route_from_supervisor(state: RealEstateState) -> str:
    if not state.get("guardrail_allowed", True):
        return "guardrail_blocked"

    selected = _selected_agents(state)
    return selected[0] if selected else "property_plan_agent"


def route_after_agent(current_agent: str):
    def route(state: RealEstateState) -> str:
        selected = _selected_agents(state)
        current_index = AGENT_ORDER.index(current_agent)
        for next_agent in AGENT_ORDER[current_index + 1 :]:
            if next_agent in selected:
                return next_agent
        return "property_plan_agent"

    return route


# =========================
# Graph Construction
# =========================
graph = StateGraph(RealEstateState)

graph.add_node("supervisor", supervisor_agent)
graph.add_node("guardrail_blocked", guardrail_blocked_agent)
graph.add_node("property_search_agent", property_search_agent)
graph.add_node("valuation_agent", valuation_agent)
graph.add_node("neighborhood_agent", neighborhood_agent)
graph.add_node("action_dispatch_agent", action_dispatch_agent)
graph.add_node("property_plan_agent", property_plan_agent)
graph.add_node("human_approval", human_approval_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "supervisor")
graph.add_conditional_edges("supervisor", route_from_supervisor, ROUTE_MAP)

graph.add_conditional_edges("property_search_agent", route_after_agent("property_search_agent"), ROUTE_MAP)
graph.add_conditional_edges("valuation_agent", route_after_agent("valuation_agent"), ROUTE_MAP)
graph.add_conditional_edges("neighborhood_agent", route_after_agent("neighborhood_agent"), ROUTE_MAP)
graph.add_conditional_edges("action_dispatch_agent", route_after_agent("action_dispatch_agent"), ROUTE_MAP)

graph.add_edge("property_plan_agent", "human_approval")
graph.add_edge("human_approval", "final_agent")
graph.add_edge("final_agent", END)
graph.add_edge("guardrail_blocked", END)

# Checkpointer setup with MemorySaver fallback
checkpointer = MemorySaver()
try:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Remove channel_binding if present (causes SSL failures on Windows)
        db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require&", "?").replace("?channel_binding=require", "")
        if "sslmode=" not in db_url:
            db_url += "&sslmode=require" if "?" in db_url else "?sslmode=require"

        import ssl
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        ssl_ctx.check_hostname = True
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED

        conn = psycopg.connect(
            db_url,
            autocommit=True,
            row_factory=dict_row,
            sslcontext=ssl_ctx,
        )
        pg_saver = PostgresSaver(conn)
        pg_saver.setup()
        checkpointer = pg_saver
        print("PostgresSaver connected successfully.")
except Exception as exc:
        print(f"PostgresSaver unavailable, using MemorySaver: {exc}")

real_estate_graph = graph.compile(checkpointer=checkpointer)


# Serialization & Execution Helper
def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    first_interrupt = interrupts[0]
    payload = getattr(first_interrupt, "value", first_interrupt)
    return payload if isinstance(payload, dict) else {"value": payload}


def _serialize_result(result: dict[str, Any], thread_id: str) -> dict[str, Any]:
    messages = result.get("messages", [])
    last_message = messages[-1].content if messages else ""
    answer = result.get("final_response") or last_message
    interrupt_payload = _interrupt_payload(result)

    if interrupt_payload:
        answer = interrupt_payload.get("draft_proposal") or result.get("proposal", "")

    return {
        "thread_id": thread_id,
        "answer": answer,
        "requires_approval": interrupt_payload is not None,
        "approval_request": (
            interrupt_payload.get("approval_request", "")
            if interrupt_payload
            else result.get("approval_request", "")
        ),
        "property_results": result.get("property_results", ""),
        "valuation_results": result.get("valuation_results", ""),
        "neighborhood_results": result.get("neighborhood_results", ""),
        "action_results": result.get("action_results", ""),
        "action_evaluations": result.get("action_evaluations", []),
        "proposal": (
            interrupt_payload.get("draft_proposal", "")
            if interrupt_payload
            else result.get("proposal", "")
        ),
        "selected_agents": result.get("selected_agents", []),
        "property_constraints": result.get("property_constraints", {}),
        "supervisor_reasoning": result.get("supervisor_reasoning", ""),
        "guardrail_allowed": result.get("guardrail_allowed", True),
        "guardrail_reason": result.get("guardrail_reason", ""),
        "approved": result.get("approved"),
        "human_feedback": result.get("human_feedback", ""),
        "llm_calls": result.get("llm_calls", 0),
        "audit_logs": audit_logger.get_logs(limit=20),
    }


def run_real_estate_agent(user_input: str, thread_id: str | None = None, dry_run: bool = False):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}
    result = real_estate_graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "dry_run": dry_run,
            "guardrail_allowed": True,
            "guardrail_reason": "",
            "selected_agents": [],
            "property_constraints": _empty_constraints(),
            "supervisor_reasoning": "",
            "property_results": "",
            "valuation_results": "",
            "neighborhood_results": "",
            "action_results": "",
            "action_evaluations": [],
            "proposal": "",
            "approval_request": "",
            "approved": False,
            "human_feedback": "",
            "final_response": "",
            "llm_calls": 0,
        },
        config=config,
    )
    return _serialize_result(result, thread_id)


def resume_real_estate_agent(thread_id: str, approved: bool, feedback: str = ""):
    if not thread_id:
        raise ValueError("thread_id is required to resume.")

    config = {"configurable": {"thread_id": thread_id}}
    result = real_estate_graph.invoke(
        Command(resume={"approved": approved, "feedback": feedback.strip()}),
        config=config,
    )
    return _serialize_result(result, thread_id)
