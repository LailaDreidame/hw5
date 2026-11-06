"""Shared machinery for the five agents.

- build_agent(): one PydanticAI Agent per role, with its own prompt file, its own
  allow-list of MCP tools, and the ask_agent delegation tool.
- ask_agent: full connectivity — any agent can hand a task to any other agent.
  Guardrails: no delegating to yourself, max depth, max delegations per run.
- run_agent(): drives one agent's loop step by step (agent.iter) so every step
  is written to output/audit_trail.json and per-agent step caps are enforced.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent, CallToolsNode, ModelRequestNode, NativeOutput, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from models import AGENT_ROLES, AgentName, DelegationResult, TeamDeps

from . import audit
from .config import (
    HUMAN_ONLY_TOOLS,
    MAX_DELEGATION_DEPTH,
    MAX_MODEL_CALLS_PER_AGENT,
    MODEL_SETTINGS,
    PROMPTS_DIR,
    RUN_LIMITS,
    build_model,
    mcp_toolset,
)

REGISTRY: dict[str, Agent[TeamDeps, Any]] = {}


class AgentStepLimit(RuntimeError):
    """One agent used more loop steps than MAX_STEPS_PER_AGENT."""


# --- delegation (full connectivity) ---------------------------------------

_TEAM_LIST = "\n".join(f"- {name}: {role}" for name, role in AGENT_ROLES.items())


async def ask_agent(ctx: RunContext[TeamDeps], agent: AgentName, task: str) -> dict[str, Any]:
    """Hand a focused task to another agent on the team and wait for its report.

    Say exactly what you need: the ticket id, the SKU/size/qty, invoice or lease id,
    and the question to answer or the action to prepare. The teammate has its own
    MCP tools and returns findings, actions taken, approval/draft ids and blockers.

    Team:
    - boss: reads tickets, decides who works on them, makes the final call.
    - inventory: stock by SKU and size, shortfalls, which vendor can restock.
    - accounting: cash, invoices, margins; prepares payments / purchase orders for human approval.
    - facilities: the shop space, lease, rent amount and rent due date.
    - customer_service: drafts customer messages (saved on the board, never sent).
    """
    deps = ctx.deps
    budget = deps.budget

    def refuse(reason: str) -> dict[str, Any]:
        audit.append({"event": "delegation_refused", "to_agent": agent, "task": audit.preview(task, 400),
                      "reason": reason}, deps)
        return DelegationResult(to_agent=agent, status="refused", reason=reason).model_dump()

    if agent not in AGENT_ROLES:
        return refuse(f"Unknown agent '{agent}'. Team: {list(AGENT_ROLES)}")
    if agent == deps.agent:
        return refuse("You cannot delegate to yourself; do the work with your own tools.")
    if deps.depth >= MAX_DELEGATION_DEPTH:
        return refuse(f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached; finish with what you have "
                      "and report the open question to whoever asked you.")
    if budget.delegations_used >= budget.max_delegations:
        return refuse(f"Delegation budget for this run ({budget.max_delegations}) is used up; finish with what you have.")
    if not task.strip():
        return refuse("Task is empty; say exactly what you need.")

    budget.delegations_used += 1
    child = deps.child(agent)
    audit.append({"event": "delegation", "from_agent": deps.agent, "to_agent": agent,
                  "task": audit.preview(task, 800), "delegations_used": budget.delegations_used}, deps)
    try:
        output = await run_agent(agent, task, child, usage=ctx.usage)
    except UsageLimitExceeded:
        raise  # the whole run is out of budget; stop everything
    except AgentStepLimit as exc:
        return DelegationResult(to_agent=agent, status="error", reason=str(exc)).model_dump()
    report = output.model_dump() if hasattr(output, "model_dump") else {"text": str(output)}
    return DelegationResult(to_agent=agent, status="done", report=report).model_dump()


# --- building agents -------------------------------------------------------

def build_agent(name: AgentName, output_type: type, mcp_tools: list[str]) -> Agent[TeamDeps, Any]:
    """Create one role's agent: its prompt file, its MCP tool allow-list, and ask_agent."""
    bad = HUMAN_ONLY_TOOLS.intersection(mcp_tools)
    if bad:
        raise ValueError(f"{name} may not be given human-only tools: {sorted(bad)}")
    allowed = frozenset(mcp_tools)
    prompt = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")

    agent: Agent[TeamDeps, Any] = Agent(
        build_model(),
        name=name,
        deps_type=TeamDeps,
        output_type=NativeOutput(output_type),  # API-enforced JSON schema for the final answer
        instructions=prompt,
        model_settings=MODEL_SETTINGS,
        retries=1,
        toolsets=[
            mcp_toolset().filtered(lambda ctx, tool_def: tool_def.name in allowed),
            FunctionToolset([ask_agent]),
        ],
    )

    @agent.instructions
    def run_context(ctx: RunContext[TeamDeps]) -> str:
        d = ctx.deps
        left = d.budget.max_delegations - d.budget.delegations_used
        return (
            f"Run context: you are '{d.agent}'. Call chain: {' -> '.join(d.chain)}. "
            f"Delegation depth {d.depth} of max {MAX_DELEGATION_DEPTH}; {left} delegations left in this run. "
            f"Ticket in focus: {d.ticket_id if d.ticket_id is not None else 'none given'}.\n"
            f"Your MCP tools: {', '.join(sorted(allowed))}, plus ask_agent.\n"
            f"Team:\n{_TEAM_LIST}"
        )

    REGISTRY[name] = agent
    return agent


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage | None = None) -> Any:
    """Run one agent's loop, logging every step to the audit trail."""
    agent = REGISTRY[name]
    steps = model_calls = 0
    async with agent.iter(task, deps=deps, usage=usage, usage_limits=RUN_LIMITS) as run:
        async for node in run:
            # About to make another model call after already using this agent's allowance: stop.
            if isinstance(node, ModelRequestNode) and model_calls >= MAX_MODEL_CALLS_PER_AGENT:
                reason = f"{name} stopped after {MAX_MODEL_CALLS_PER_AGENT} model calls without finishing."
                audit.append({"event": "agent_stopped", "reason": reason}, deps)
                raise AgentStepLimit(reason)
            steps += 1
            deps.budget.steps_used += 1
            audit.log_node(node, steps, deps)
            if isinstance(node, CallToolsNode):
                model_calls += 1
        return run.result.output
