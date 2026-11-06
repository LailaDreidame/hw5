"""Customer Service: drafts messages to customers. Drafts stay on the board; nothing is sent."""

from models import WorkerReport

from .base import build_agent

NAME = "customer_service"
MCP_TOOLS = [
    "get_shop_today",
    "get_ticket",
    "save_customer_draft",
    "list_drafts",
]

agent = build_agent(NAME, WorkerReport, MCP_TOOLS)
