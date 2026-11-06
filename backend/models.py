"""Data types for the Campus Customs agent team.

- AgentName / AGENT_ROLES: the five roles on the team.
- WorkerReport: what Inventory, Accounting, Facilities and Customer Service hand back.
- BossDecision: the Boss's final call on a ticket.
- DelegationResult: what an agent gets back when it asks a teammate for help.
- TeamDeps / RunBudget: per-run state passed to every agent (who is running,
  how deep the delegation chain is, shared limits, optional live-event queue).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_ROLES: dict[str, str] = {
    "boss": "Reads each ticket, decides who should work on it, and makes the final call.",
    "inventory": "Checks stock by SKU and size, spots shortfalls, and finds which vendor can restock.",
    "accounting": "Watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval.",
    "facilities": "Handles the shop space: the lease, rent amount and rent due dates.",
    "customer_service": "Drafts messages to customers and requesters. Drafts stay on the board; nothing is sent.",
}


class WorkerReport(BaseModel):
    """A specialist's answer to the task it was given."""

    agent: AgentName
    ticket_id: int | None = Field(None, description="Ticket this work is for, if any.")
    findings: list[str] = Field(
        default_factory=list,
        description="Facts found, each one taken from an MCP tool result (name the tool).",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Things changed through MCP tools, e.g. 'request_payment -> approval 1 (pending)'.",
    )
    approval_ids: list[int] = Field(
        default_factory=list, description="Approval-queue ids this agent created (waiting for a human)."
    )
    draft_ids: list[int] = Field(default_factory=list, description="Customer draft ids this agent saved.")
    blockers: list[str] = Field(
        default_factory=list, description="What stops the ticket moving (no stock, unpaid invoice, not enough cash...)."
    )
    recommendation: str = Field(description="What this agent recommends the Boss decide, in one or two sentences.")
    needs_human: bool = Field(False, description="True if a person must approve or decide something.")


class TicketStatusChange(BaseModel):
    ticket_id: int
    new_status: Literal["open", "in_progress", "waiting_approval", "resolved"]
    why: str


class BossDecision(BaseModel):
    """The Boss's final call on the ticket(s) it was asked to handle."""

    ticket_ids: list[int]
    summary: str = Field(description="Plain-English summary of what is going on with the ticket(s).")
    decision: str = Field(description="The Boss's final call and the reason for it.")
    delegated_to: list[AgentName] = Field(default_factory=list)
    approvals_waiting: list[int] = Field(
        default_factory=list, description="Approval ids a human must approve or reject on the board."
    )
    drafts_saved: list[int] = Field(default_factory=list, description="Customer draft ids on the board.")
    status_changes: list[TicketStatusChange] = Field(default_factory=list)
    next_steps_for_human: list[str] = Field(default_factory=list)


class DelegationResult(BaseModel):
    """Returned to the agent that called ask_agent."""

    to_agent: AgentName
    status: Literal["done", "refused", "error"]
    report: dict[str, Any] | None = None
    reason: str | None = None


@dataclass
class RunBudget:
    """Shared across every agent in one team run, so limits apply to the whole run."""

    max_delegations: int
    delegations_used: int = 0
    steps_used: int = 0


@dataclass
class TeamDeps:
    """Passed to every agent run (PydanticAI deps)."""

    run_id: str
    agent: AgentName
    budget: RunBudget
    ticket_id: int | None = None
    depth: int = 0
    chain: list[str] = field(default_factory=list)
    events: asyncio.Queue | None = None  # live events for the dashboard (later problems)

    def child(self, agent: AgentName) -> "TeamDeps":
        return TeamDeps(run_id=self.run_id, agent=agent, budget=self.budget, ticket_id=self.ticket_id,
                        depth=self.depth + 1, chain=[*self.chain, agent], events=self.events)
