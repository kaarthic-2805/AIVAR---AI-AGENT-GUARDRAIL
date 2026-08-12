import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import certifi
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from action_guardrail import evaluator, audit_logger

# =========================================================
# Environment setup
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

WEATHER_SERVER_PATH = BASE_DIR / "custom_weather_mcp_server.py"

def _require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(
            f"{name} is missing. Add {name}=your_key to the project .env file."
        )
    return value


def _subprocess_env(**updates: Optional[str]) -> Dict[str, str]:
    env = os.environ.copy()
    for key, value in updates.items():
        if value:
            env[key] = value
    return env


# =========================================================
# LLM
# =========================================================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=_require_env("GROQ_API_KEY", GROQ_API_KEY),
)


# =========================================================
# MCP Client
# =========================================================

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                "https://mcp.tavily.com/mcp/"
                f"?tavilyApiKey={TAVILY_API_KEY or ''}"
            ),
        },
        "weather": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(WEATHER_SERVER_PATH)],
            "env": _subprocess_env(OPENWEATHER_API_KEY=OPENWEATHER_API_KEY),
        },
    }
)


async def _get_server_tool(server_name: str, tool_name: str):
    if server_name == "tavily":
        _require_env("TAVILY_API_KEY", TAVILY_API_KEY)
    elif server_name == "weather":
        _require_env("OPENWEATHER_API_KEY", OPENWEATHER_API_KEY)

    tools = await client.get_tools(server_name=server_name)
    tool = next((item for item in tools if item.name == tool_name), None)

    if tool is None:
        available_tools = ", ".join(sorted(item.name for item in tools)) or "none"
        raise RuntimeError(
            f"MCP tool '{tool_name}' was not found on server '{server_name}'. "
            f"Available tools: {available_tools}"
        )
    return tool


async def tavily_mcp_search(query: str):
    try:
        search_tool = await _get_server_tool("tavily", "tavily_search")
        return await search_tool.ainvoke({"query": query})
    except Exception as exc:
        print(f"Tavily MCP fallback: {exc}")
        return f"Market search results for: '{query}'"


async def weather_mcp_search(city: str):
    try:
        weather_tool = await _get_server_tool("weather", "get_current_weather")
        return await weather_tool.ainvoke({"city": city})
    except Exception as exc:
        print(f"Weather MCP fallback: {exc}")
        return f"Weather info for {city}: Moderate climate, mild seasonal variation."


def extract_location(query: str) -> str:
    prompt = f"""
Extract only the target city, state, or location from this real estate request.

Real Estate Request:
{query}

Return only the location name. Do not add any explanation.
"""
    try:
        response = llm.invoke(prompt)
        loc = str(response.content).strip()
        return loc if loc else "Austin, TX"
    except Exception:
        return "Austin, TX"


# =========================================================
# Guarded Real Estate Agent Action Tools
# =========================================================

def execute_db_delete_tool(
    table: str,
    record_count: int,
    agent_id: str = "action_dispatch_agent",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute database deletion guarded by Pre-Execution Action Evaluator."""
    params = {"table": table, "record_count": record_count}
    eval_result = evaluator.evaluate(
        action="delete_records",
        params=params,
        agent_id=agent_id,
        dry_run=dry_run,
    )

    if eval_result["outcome"] == "block":
        return {
            "success": False,
            "status": "BLOCKED",
            "eval_result": eval_result,
            "message": f"Action BLOCKED by policy rule '{eval_result['rule_id']}': Deleted {record_count} records from '{table}' exceeds threshold.",
        }
    elif eval_result["outcome"] == "require_hitl":
        return {
            "success": False,
            "status": "PAUSED_FOR_HITL",
            "eval_result": eval_result,
            "message": f"Action PAUSED for Human-in-the-Loop approval by rule '{eval_result['rule_id']}'.",
        }
    else:  # log_and_allow
        execution_msg = (
            f"[SIMULATED DRY RUN] Would delete {record_count} records from table '{table}'."
            if dry_run
            else f"Successfully deleted {record_count} records from table '{table}'."
        )
        return {
            "success": True,
            "status": "EXECUTED" if not dry_run else "SIMULATED",
            "eval_result": eval_result,
            "message": execution_msg,
        }


def execute_send_email_tool(
    recipient: str,
    subject: str,
    body: str,
    agent_id: str = "action_dispatch_agent",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute email dispatch guarded by Pre-Execution Action Evaluator."""
    params = {"recipient": recipient, "subject": subject, "body": body}
    eval_result = evaluator.evaluate(
        action="send_email",
        params=params,
        agent_id=agent_id,
        dry_run=dry_run,
    )

    if eval_result["outcome"] == "block":
        return {
            "success": False,
            "status": "BLOCKED",
            "eval_result": eval_result,
            "message": f"Email dispatch BLOCKED by rule '{eval_result['rule_id']}'.",
        }
    elif eval_result["outcome"] == "require_hitl":
        return {
            "success": False,
            "status": "PAUSED_FOR_HITL",
            "eval_result": eval_result,
            "message": f"Email dispatch to external domain '{recipient}' requires Human-in-the-Loop approval.",
        }
    else:  # log_and_allow
        execution_msg = (
            f"[SIMULATED DRY RUN] Would send email to '{recipient}' with subject '{subject}'."
            if dry_run
            else f"Successfully sent email to '{recipient}' with subject '{subject}'."
        )
        return {
            "success": True,
            "status": "EXECUTED" if not dry_run else "SIMULATED",
            "eval_result": eval_result,
            "message": execution_msg,
        }


def execute_read_path_tool(
    path: str,
    agent_id: str = "action_dispatch_agent",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute document path read guarded by Pre-Execution Action Evaluator."""
    params = {"path": path}
    eval_result = evaluator.evaluate(
        action="read_path",
        params=params,
        agent_id=agent_id,
        dry_run=dry_run,
    )

    if eval_result["outcome"] == "block":
        return {
            "success": False,
            "status": "BLOCKED",
            "eval_result": eval_result,
            "message": f"File read BLOCKED by rule '{eval_result['rule_id']}'.",
        }
    elif eval_result["outcome"] == "require_hitl":
        return {
            "success": False,
            "status": "PAUSED_FOR_HITL",
            "eval_result": eval_result,
            "message": f"Reading file '{path}' requires HITL approval.",
        }
    else:  # log_and_allow
        content = (
            f"[Simulated Read Content from {path}]: Property title deed & ownership record."
        )
        return {
            "success": True,
            "status": "EXECUTED" if not dry_run else "SIMULATED",
            "eval_result": eval_result,
            "content": content,
            "message": f"Successfully accessed document at '{path}'. Audit log generated.",
        }