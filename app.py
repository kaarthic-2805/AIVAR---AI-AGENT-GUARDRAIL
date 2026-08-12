from pathlib import Path
import traceback

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend import run_real_estate_agent, resume_real_estate_agent
from simulation_harness import run_simulation
from action_guardrail import evaluator, audit_logger

import nest_asyncio

nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="EstateGuard AI",
    description=(
        "LangGraph Multi-Agent Real Estate Platform with Pre-Execution Action Guardrails, "
        "Declarative Policies, Simulation Harness, Audit Logs, and HITL Approvals."
    ),
    version="3.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class RealEstateRequest(BaseModel):
    message: str
    thread_id: str | None = None
    dry_run: bool = False


class ApprovalRequest(BaseModel):
    thread_id: str = Field(min_length=1)
    approved: bool
    feedback: str = ""


class SimulationRequest(BaseModel):
    dry_run: bool = False


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.post("/api/realestate")
@app.post("/api/travel")  # Alias for backward compatibility
async def real_estate_agent_endpoint(request_data: RealEstateRequest):
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty.",
                },
            )

        result = run_real_estate_agent(
            user_input=user_message,
            thread_id=request_data.thread_id,
            dry_run=request_data.dry_run,
        )

        return JSONResponse(
            content={
                "success": True,
                **result,
            }
        )

    except Exception as exc:
        print("ERROR:", exc)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc),
            },
        )


@app.post("/api/realestate/approve")
@app.post("/api/travel/approve")  # Alias for backward compatibility
async def approve_real_estate_plan(request_data: ApprovalRequest):
    try:
        if not request_data.approved and not request_data.feedback.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Please provide revision feedback when rejecting the draft.",
                },
            )

        result = resume_real_estate_agent(
            thread_id=request_data.thread_id,
            approved=request_data.approved,
            feedback=request_data.feedback,
        )

        return JSONResponse(
            content={
                "success": True,
                **result,
            }
        )

    except Exception as exc:
        print("APPROVAL ERROR:", exc)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc),
            },
        )


@app.post("/api/simulate")
async def trigger_simulation(req: SimulationRequest):
    try:
        summary = run_simulation(dry_run=req.dry_run)
        return JSONResponse(
            content={
                "success": True,
                "simulation": summary,
            }
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc),
            },
        )


@app.get("/api/audit-logs")
async def get_audit_logs():
    return {
        "success": True,
        "logs": audit_logger.get_logs(limit=100),
    }


@app.get("/api/policies")
async def get_policies():
    evaluator.reload()
    return {
        "success": True,
        "policies": evaluator.policies,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "EstateGuard AI Real Estate Platform & Action Guardrails API is running",
        "features": [
            "pre_execution_action_guardrails",
            "block_outcome",
            "require_hitl_outcome",
            "log_and_allow_outcome",
            "dry_run_mode",
            "simulation_harness",
            "supervisor_agent",
            "audit_logging",
        ],
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
