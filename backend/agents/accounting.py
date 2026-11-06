"""Accounting: watches cash and invoices, checks margins, and prepares payments or
purchase orders for human approval. It can request money; it can never move it."""

from models import WorkerReport

from .base import build_agent

NAME = "accounting"
MCP_TOOLS = [
    "get_shop_today",
    "get_ticket",
    "get_cash_balance",
    "list_open_invoices",
    "get_invoice",
    "check_margin",
    "list_payments",
    "list_approvals",
    "request_payment",          # invoice or rent -> pending human approval
    "request_purchase_order",   # restock order -> pending human approval
]

agent = build_agent(NAME, WorkerReport, MCP_TOOLS)
