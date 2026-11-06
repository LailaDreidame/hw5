"""Inventory: checks stock by SKU and size, spots shortfalls, and finds which vendor can restock."""

from models import WorkerReport

from .base import build_agent

NAME = "inventory"
MCP_TOOLS = [
    "get_shop_today",
    "get_ticket",
    "check_stock",
    "list_vendors",   # specialty, lead_days, and whether each vendor will ship
    "get_invoice",    # to see why a vendor is blocked
]

agent = build_agent(NAME, WorkerReport, MCP_TOOLS)
