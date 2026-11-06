"""Campus Customs backend — FastAPI routes for the React desk dashboard.

Start it from backend/:
    uvicorn main:app --reload --port 8000      ->  http://localhost:8000  (docs at /docs)

Every shop fact (tickets, cash, approvals, drafts) is read through the Campus
Customs MCP server, the same tools the agents use. Agents only PREPARE payments;
the approve route below is the only place money actually moves, and it runs
only when a human clicks Approve.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

import agents  # noqa: F401  (builds and registers the five agents)
from agents import audit, run_team
from agents.config import AUDIT_PATH, MODEL_NAME, mcp_toolset
from models import AGENT_ROLES

mcp_toolset()  # puts mcp_server/ on sys.path
from server import DB_PATH, ORIGINAL_DB  # noqa: E402  (mcp_server/server.py)
from server import mcp as campus_mcp  # noqa: E402

app = FastAPI(title="Campus Customs API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One team run at a time, so two runs can never race over the same cash.
RUNS: dict[str, dict[str, Any]] = {}
_active_run: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def mcp_call(tool: str, **args: Any) -> dict[str, Any]:
    """Call one Campus Customs MCP tool (in-process) and return its JSON result."""
    try:
        async with Client(campus_mcp) as client:
            result = await client.call_tool(tool, args)
    except ToolError as exc:
        raise HTTPException(status_code=502, detail=f"MCP tool {tool} failed: {exc}") from exc
    return result.data


def _refusal(result: dict[str, Any]) -> None:
    """Turn a tool's business refusal (not enough cash, already paid...) into HTTP 409."""
    if result.get("refused"):
        raise HTTPException(status_code=409, detail=result.get("reason", "Refused."))


# --- request bodies --------------------------------------------------------

class ApproveBody(BaseModel):
    approved_by: str = Field(..., min_length=1, description="Name of the human approving, e.g. 'Laila'.")


class RejectBody(BaseModel):
    rejected_by: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ResolveBody(BaseModel):
    resolved_by: str = Field(..., min_length=1, description="Name of the human closing the ticket.")
    note: str = Field("Closed by a person on the desk.", min_length=1)


# --- health and team -------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Backend is up; which model and database it uses."""
    return {"ok": True, "model": MODEL_NAME, "database": DB_PATH.name, "active_run": _active_run}


@app.get("/api/agents")
async def roster() -> list[dict[str, str]]:
    """The five agents and their roles (for the dashboard)."""
    return [{"name": name, "role": role} for name, role in AGENT_ROLES.items()]


# --- tickets and runs -------------------------------------------------------

@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    """The tickets on the desk and whether each is open or resolved."""
    data = await mcp_call("list_tickets")
    tickets = [
        {k: t[k] for k in ("id", "type", "requester", "subject", "sku", "size", "qty",
                           "lease_id", "invoice_id", "status", "resolved", "created_at")}
        for t in data["tickets"]
    ]
    return {"shop_today": data["shop_today"], "tickets": tickets}


async def _run_ticket(run_id: str, ticket_id: int) -> None:
    global _active_run
    task = (f"Work ticket {ticket_id}. Read it, decide which teammates need to work on it, "
            "delegate precise tasks, and make the final call. Prepare any payments or purchase orders "
            "for human approval only, save any customer message as a draft, and update the ticket status.")
    RUNS[run_id].update(status="running")
    try:
        result = await run_team(task, ticket_id=ticket_id, run_id=run_id)
        RUNS[run_id].update(status=result["status"], result=result, finished_at=_now())
        # A person may have signed everything while the team was still working.
        if (await _resolve_ticket_if_clear(ticket_id)) is not None:
            audit.append({"event": "human_resolve", "agent": "human", "ticket_id": ticket_id, "run_id": run_id,
                          "summary": f"Ticket {ticket_id} resolved: every approval was signed before the run ended."})
    except Exception as exc:  # noqa: BLE001
        RUNS[run_id].update(status="error", error=f"{type(exc).__name__}: {exc}", finished_at=_now())
    finally:
        _active_run = None


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int, wait: bool = Query(False, description="Wait for the run to finish.")) -> dict[str, Any]:
    """Run the agent team on one ticket. Returns a run_id right away (poll /api/events), or the result if wait=true."""
    global _active_run
    ticket = await mcp_call("get_ticket", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(status_code=404, detail=ticket.get("message", "Ticket not found."))
    if ticket["status"] == "resolved":
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already resolved. Reset to run it again.")
    if _active_run is not None:
        raise HTTPException(status_code=409, detail=f"Run {_active_run} is still working; one run at a time.")

    run_id = uuid.uuid4().hex[:12]
    _active_run = run_id
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "starting", "started_at": _now()}
    if wait:
        await _run_ticket(run_id, ticket_id)
        return RUNS[run_id]
    asyncio.create_task(_run_ticket(run_id, ticket_id))
    return RUNS[run_id]


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveBody) -> dict[str, Any]:
    """A person marks a ticket resolved (refused while it still has pending approvals)."""
    result = await mcp_call("update_ticket", ticket_id=ticket_id, status="resolved",
                            note=body.note, updated_by=body.resolved_by)
    audit.append({"event": "human_resolve", "agent": "human", "actor": body.resolved_by, "ticket_id": ticket_id,
                  "summary": f"{body.resolved_by} marked ticket {ticket_id} resolved" if result.get("ok")
                             else f"Resolve {ticket_id} refused: {result.get('reason')}"})
    _refusal(result)
    return result


@app.get("/api/runs")
async def list_runs() -> list[dict[str, Any]]:
    """Team runs started since the server came up (newest first)."""
    return sorted(RUNS.values(), key=lambda r: r["started_at"], reverse=True)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Status and final result of one team run."""
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail=f"No run {run_id} since the server started.")
    return RUNS[run_id]


# --- agent events (from the audit trail) ------------------------------------

def _summarize(index: int, e: dict[str, Any]) -> dict[str, Any] | None:
    """One audit entry -> what that agent said and which tools it used."""
    node = e.get("node_type")
    if e.get("event") == "agent_step" and node == "model_request" and not e.get("tool_results") and not e.get("retries"):
        return None  # just "sending to the model": nothing for the board
    if node == "model_response" and not e.get("tool_calls") and (e.get("text") or [""])[0].lstrip().startswith("{"):
        return None  # the final JSON answer; the 'end' step right after shows it in plain words
    said = None
    if e.get("text"):
        said = " ".join(e["text"])
    elif node == "end" and isinstance(e.get("output"), dict):
        out = e["output"]
        said = out.get("decision") or out.get("recommendation") or out.get("summary")
    elif e.get("event") in ("run_start", "delegation", "delegation_refused") or node == "task_received":
        said = e.get("task") or e.get("reason")
    elif e.get("event") == "run_end":
        said = f"Run {e.get('status')}" + (f": {e['error']}" if e.get("error") else "")
    elif e.get("event") in ("human_approval", "human_rejection", "human_resolve", "database_reset"):
        said = e.get("summary")
    return {
        "index": index,
        "time": e.get("time"),
        "run_id": e.get("run_id"),
        "ticket_id": e.get("ticket_id"),
        "agent": e.get("agent"),
        "depth": e.get("depth"),
        "event": e.get("event"),
        "step": node,
        "said": said,
        "tools": [c["tool"] for c in e.get("tool_calls") or []],
        "tool_calls": e.get("tool_calls") or [],
        "tool_results": [{"tool": r["tool"], "result": audit.preview(r["result"], 300)}
                         for r in e.get("tool_results") or []],
        "from_agent": e.get("from_agent"),
        "to_agent": e.get("to_agent"),
        "output": e.get("output") if node == "end" or e.get("event") == "run_end" else None,
        "model": e.get("model"),
        "usage": e.get("usage"),
    }


@app.get("/api/events")
async def events(since: int = Query(0, ge=0, description="Return entries after this index."),
                 run_id: str | None = None, ticket_id: int | None = None,
                 limit: int = Query(200, ge=1, le=1000)) -> dict[str, Any]:
    """Recent agent events (what each agent said, which tools it used). Poll with since=next_since."""
    rows: list[dict[str, Any]] = []
    if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
        rows = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    out = []
    for i, e in enumerate(rows):
        if i < since:
            continue
        if run_id and e.get("run_id") != run_id:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        s = _summarize(i, e)
        if s:
            out.append(s)
    return {"next_since": len(rows), "count": len(out[-limit:]), "events": out[-limit:]}


# --- approvals: the only place money moves ---------------------------------

@app.get("/api/approvals")
async def approvals(status: str = Query("pending", pattern="^(pending|approved|rejected|all)$")) -> dict[str, Any]:
    """Payments and purchase orders the agents prepared, waiting for (or decided by) a human."""
    return await mcp_call("list_approvals", status=status)


async def _resolve_ticket_if_clear(ticket_id: int) -> dict[str, Any] | None:
    """If a ticket is waiting only on approvals, none are pending, and a human approved at least one, resolve it.

    Called after every human approval AND when a run finishes, because a person may sign a
    cheque before the Boss has finished and set the ticket to waiting_approval.
    """
    mine = [a for a in (await mcp_call("list_approvals", status="all"))["approvals"] if a["ticket_id"] == ticket_id]
    if not mine or any(a["status"] == "pending" for a in mine) or not any(a["status"] == "approved" for a in mine):
        return None
    ticket = await mcp_call("get_ticket", ticket_id=ticket_id)
    if ticket.get("status") != "waiting_approval":
        return None
    human = sorted((a for a in mine if a["status"] == "approved"), key=lambda a: a["id"])[-1]["decided_by"]
    decided = [f"{a['id']} {a['status']}" for a in mine]
    return await mcp_call("update_ticket", ticket_id=ticket_id, status="resolved", updated_by=human,
                          note=f"All approvals decided by a human ({', '.join(decided)}).")


async def _resolve_if_clear(approval_id: int) -> dict[str, Any] | None:
    """After a human approval: resolve that approval's ticket if nothing is left to sign."""
    every = (await mcp_call("list_approvals", status="all"))["approvals"]
    this = next((a for a in every if a["id"] == approval_id), None)
    if not this or this.get("ticket_id") is None:
        return None
    return await _resolve_ticket_if_clear(this["ticket_id"])


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApproveBody) -> dict[str, Any]:
    """A human clicked Approve: pay it. This is the only route that changes cash."""
    result = await mcp_call("approve_and_pay", approval_id=approval_id, approved_by=body.approved_by)
    audit.append({"event": "human_approval", "agent": "human", "actor": body.approved_by,
                  "approval_id": approval_id, "result": result,
                  "summary": (f"{body.approved_by} approved {approval_id}: paid {result.get('amount')} "
                              f"(new balance {result.get('new_balance')})") if result.get("ok")
                             else f"Approval {approval_id} refused: {result.get('reason')}"})
    _refusal(result)
    resolved = await _resolve_if_clear(approval_id)
    return {**result, "ticket_resolved": resolved}


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: RejectBody) -> dict[str, Any]:
    """A human clicked Reject. No money moves."""
    result = await mcp_call("reject_approval", approval_id=approval_id,
                            rejected_by=body.rejected_by, reason=body.reason)
    audit.append({"event": "human_rejection", "agent": "human", "actor": body.rejected_by,
                  "approval_id": approval_id, "result": result,
                  "summary": f"{body.rejected_by} rejected {approval_id}: {body.reason}" if result.get("ok")
                             else f"Reject {approval_id} refused: {result.get('reason')}"})
    _refusal(result)
    return result


# --- cash, drafts, reset ----------------------------------------------------

@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts, plus what is waiting for approval."""
    data = await mcp_call("get_cash_balance")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No 'checking' row in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"],
            "shop_today": data["shop_today"], "pending_approvals_total": data["pending_approvals_total"],
            "available_after_pending": data["available_after_pending"]}


@app.get("/api/drafts")
async def drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """Customer message drafts on the board (never sent)."""
    return await mcp_call("list_drafts", ticket_id=ticket_id)


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Copy the original campus_customs.db over the working copy for a fresh run. The audit trail is kept."""
    if _active_run is not None:
        raise HTTPException(status_code=409, detail=f"Run {_active_run} is still working; reset after it finishes.")
    if not ORIGINAL_DB.exists():
        raise HTTPException(status_code=500, detail="Original campus_customs.db is missing.")
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    audit.append({"event": "database_reset", "agent": "human",
                  "summary": f"Working database {DB_PATH.name} reset from {ORIGINAL_DB.name}."})
    return {"ok": True, "reset_from": ORIGINAL_DB.name, "database": DB_PATH.name,
            "tickets": (await list_tickets())["tickets"], "cash": await cash()}
