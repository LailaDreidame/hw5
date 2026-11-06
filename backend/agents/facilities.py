"""Facilities: handles the shop space side — the lease, the rent amount and when rent is due."""

from models import WorkerReport

from .base import build_agent

NAME = "facilities"
MCP_TOOLS = [
    "get_shop_today",
    "get_ticket",
    "get_lease",
]

agent = build_agent(NAME, WorkerReport, MCP_TOOLS)
