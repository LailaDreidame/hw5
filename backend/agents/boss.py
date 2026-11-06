"""Boss: reads each ticket, decides who should work on it, and makes the final call."""

from models import BossDecision

from .base import build_agent

NAME = "boss"
MCP_TOOLS = [
    "get_shop_today",
    "list_open_tickets",
    "get_ticket",
    "get_cash_balance",   # to weigh competing payments before deciding
    "list_approvals",
    "list_drafts",
    "update_ticket",      # only the Boss changes ticket status
]

agent = build_agent(NAME, BossDecision, MCP_TOOLS)
