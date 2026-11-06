"""Entry point for one team run: a task (usually a ticket) goes to an agent (usually the Boss).

From backend/:
    python run_team.py --ticket 102 "Work ticket 102."
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from models import AgentName, RunBudget, TeamDeps

from . import audit
from .base import AgentStepLimit, run_agent
from .config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MAX_MODEL_CALLS_PER_AGENT,
    MODEL_NAME,
    RUN_LIMITS,
    mcp_toolset,
)


async def run_team(task: str, ticket_id: int | None = None, start_agent: AgentName = "boss",
                   events: asyncio.Queue | None = None, run_id: str | None = None) -> dict[str, Any]:
    """Run the team on one task. Every step is appended to output/audit_trail.json."""
    deps = TeamDeps(run_id=run_id or uuid.uuid4().hex[:12], agent=start_agent, ticket_id=ticket_id,
                    budget=RunBudget(max_delegations=MAX_DELEGATIONS_PER_RUN), chain=[start_agent], events=events)
    usage = RunUsage()
    import server as mcp_server  # noqa: PLC0415  (mcp_server/server.py, on sys.path via mcp_toolset)

    audit.append({"event": "run_start", "task": audit.preview(task, 800), "model": MODEL_NAME,
                  "database": str(mcp_server.DB_PATH),
                  "limits": {"requests": RUN_LIMITS.request_limit, "tool_calls": RUN_LIMITS.tool_calls_limit,
                             "total_tokens": RUN_LIMITS.total_tokens_limit,
                             "model_calls_per_agent": MAX_MODEL_CALLS_PER_AGENT,
                             "delegation_depth": MAX_DELEGATION_DEPTH,
                             "delegations": MAX_DELEGATIONS_PER_RUN}}, deps)
    status, output, error = "done", None, None
    try:
        async with mcp_toolset():
            result = await run_agent(start_agent, task, deps, usage=usage)
        output = result.model_dump() if hasattr(result, "model_dump") else result
    except UsageLimitExceeded as exc:
        status, error = "stopped_usage_limit", str(exc)
    except AgentStepLimit as exc:
        status, error = "stopped_step_limit", str(exc)
    except Exception as exc:  # noqa: BLE001  (record any failure in the audit trail)
        status, error = "error", f"{type(exc).__name__}: {exc}"[:600]

    totals = {"requests": usage.requests, "tool_calls": usage.tool_calls,
              "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
              "total_tokens": usage.total_tokens}
    audit.append({"event": "run_end", "status": status, "error": error, "output": output,
                  "usage": totals, "delegations_used": deps.budget.delegations_used}, deps)
    return {"run_id": deps.run_id, "status": status, "error": error, "output": output,
            "usage": totals, "delegations_used": deps.budget.delegations_used}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team on one task.")
    parser.add_argument("task")
    parser.add_argument("--ticket", type=int, default=None)
    parser.add_argument("--agent", default="boss")
    args = parser.parse_args()
    import agents  # noqa: F401, PLC0415  (builds and registers all five agents)

    print(json.dumps(asyncio.run(run_team(args.task, args.ticket, args.agent)), indent=2))


if __name__ == "__main__":
    main()
