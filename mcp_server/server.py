"""Campus Customs MCP server — the shared toolbox for every agent in HW5.

Works on the working copy data/campus_customs_new.db (never the original
data/campus_customs.db, which is kept untouched for resets).

Rules built into the tools:
- Every value returned comes straight from the database, or is simple
  arithmetic on database values (days between dates, qty x unit_cost).
  If a row is not found, the tool says so — it never fills in a guess.
- "Today" is desk.date_today, never the computer clock.
- Money never moves without a human. Agents can only REQUEST a payment or
  purchase order (amounts are read from the database, not typed by the
  agent). Only approve_and_pay / reject_approval move or close a request,
  and those are human-only: the backend calls them when a person clicks
  Approve/Reject, and no agent is given them.
- No negative balances: the pay tool refuses if cash would go below zero.
- A vendor will not ship while it has an unpaid invoice.
- Customer messages are saved as drafts only; nothing is ever sent.

Run (stdio):  python server.py
Run (HTTP):   python server.py --http   ->  http://127.0.0.1:8001/mcp
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator, Literal

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db")).resolve()
if DB_PATH == ORIGINAL_DB.resolve():
    raise RuntimeError("Refusing to use the original campus_customs.db; point at the working copy.")

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "resolved")
MAX_PO_QTY = 100  # guardrail: no single purchase order above 100 units

mcp = FastMCP("campus-customs")


# --- helpers -------------------------------------------------------------

def _query(sql: str, params: list | tuple = ()) -> list[dict]:
    """Run a SELECT against the working copy, opened read-only."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    with sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _rows(conn: sqlite3.Connection, sql: str, params: list | tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Approval queue and customer drafts live next to the shop tables in the working copy."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,            -- invoice | rent | purchase_order
            ref_id INTEGER,                -- invoices.id | leases.id | vendors.id
            ticket_id INTEGER,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            details TEXT,                  -- JSON copied from the database at request time
            reason TEXT,
            requested_by TEXT NOT NULL,
            requested_at TEXT NOT NULL,    -- desk.date_today
            status TEXT NOT NULL,          -- pending | approved | rejected
            decided_by TEXT,
            decided_at TEXT,
            decision_note TEXT,
            payment_id INTEGER
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            to_name TEXT NOT NULL,         -- always tickets.requester
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,      -- desk.date_today
            status TEXT NOT NULL DEFAULT 'draft'
        )"""
    )


@contextmanager
def _write_tx() -> Iterator[sqlite3.Connection]:
    """One all-or-nothing transaction on the working copy."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN IMMEDIATE")
    try:
        _ensure_tables(conn)
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _table_exists(name: str) -> bool:
    return bool(_query("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [name]))


def _shop_today(conn: sqlite3.Connection | None = None) -> str:
    """The shop's 'today' — desk.date_today, not the computer's clock."""
    rows = _rows(conn, "SELECT date_today FROM desk") if conn else _query("SELECT date_today FROM desk")
    if not rows:
        raise ValueError("desk table has no date_today row.")
    return rows[0]["date_today"]


def _days_between(start: str, end: str) -> int:
    """Whole days from start to end (both 'YYYY-MM-DD'; ISO timestamps are trimmed)."""
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _add_month(day: str) -> str:
    """Same day next month, clamped to month end (2026-01-31 -> 2026-02-28)."""
    d = date.fromisoformat(day[:10])
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _refused(reason: str, **extra) -> dict:
    return {"ok": False, "refused": True, "reason": reason, **extra}


def _open_invoices_for_vendor(conn: sqlite3.Connection | None, vendor_id: int) -> list[dict]:
    sql = "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date"
    return _rows(conn, sql, [vendor_id]) if conn else _query(sql, [vendor_id])


def _approval_out(row: dict) -> dict:
    row = dict(row)
    row["details"] = json.loads(row["details"]) if row.get("details") else {}
    return row


def _cash_check(conn: sqlite3.Connection, account: str, amount: float) -> dict | None:
    """Return a refusal if the account is unknown or the amount would overdraw it."""
    acct = _rows(conn, "SELECT name, balance FROM cash_accounts WHERE name = ?", [account])
    if not acct:
        names = [r["name"] for r in _rows(conn, "SELECT name FROM cash_accounts")]
        return _refused(f"Cash account '{account}' is not in cash_accounts. Accounts on file: {names}.")
    if amount > acct[0]["balance"]:
        return _refused(
            f"Not enough cash: {account} has {acct[0]['balance']:.2f}, this needs {amount:.2f}. "
            "No negative balances are allowed.",
            balance=acct[0]["balance"], amount=amount,
        )
    return None


def _pending_total(conn: sqlite3.Connection, account: str, exclude_id: int | None = None) -> float:
    rows = _rows(
        conn,
        "SELECT COALESCE(SUM(amount), 0) AS t FROM approvals WHERE status = 'pending' AND account = ? AND id IS NOT ?",
        [account, exclude_id],
    )
    return round(rows[0]["t"], 2)


# --- read tools: tickets and the shop date --------------------------------

@mcp.tool
def get_shop_today() -> dict:
    """Return the shop's today (desk.date_today) and desk notes. Use this date for anything overdue or due soon."""
    rows = _query("SELECT date_today, notes FROM desk")
    if not rows:
        return {"found": False, "message": "desk table is empty."}
    return {"found": True, **rows[0]}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet (reads the tickets table)."""
    rows = _query(
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
        "FROM tickets WHERE status != 'resolved' ORDER BY id"
    )
    return {"shop_today": _shop_today(), "count": len(rows), "tickets": rows}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and resolved) with its status — the desk board view (reads tickets)."""
    rows = _query(
        "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
        "FROM tickets ORDER BY id"
    )
    for r in rows:
        r["resolved"] = r["status"] == "resolved"
    return {"shop_today": _shop_today(), "count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket in full, including the notes and the sku/size/qty, lease_id and invoice_id it links to."""
    rows = _query("SELECT * FROM tickets WHERE id = ?", [ticket_id])
    if not rows:
        return {"found": False, "ticket_id": ticket_id,
                "message": f"Ticket {ticket_id} is not in the tickets table."}
    return {"found": True, "shop_today": _shop_today(), **rows[0]}


# --- read tools: stock, pricing and vendors ------------------------------

@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int = 0) -> dict:
    """Check stock on hand for one SKU in one size, and its cost and list price.

    Reads the inventory and pricing tables. Pass qty_needed (the qty on the
    ticket) to get the shortfall and what the shortfall would cost to restock
    at unit_cost. Example: check_stock("CC-TEE-WHITE", "S", 1).
    """
    sku = sku.strip().upper()
    size = size.strip().upper()
    rows = _query(
        """
        SELECT i.sku, i.name, i.size, i.qty AS on_hand, i.location,
               p.unit_cost, p.list_price
        FROM inventory i
        LEFT JOIN pricing p ON p.sku = i.sku
        WHERE UPPER(i.sku) = ? AND UPPER(i.size) = ?
        """,
        [sku, size],
    )
    if not rows:
        sizes = [r["size"] for r in _query(
            "SELECT size FROM inventory WHERE UPPER(sku) = ? ORDER BY size", [sku])]
        message = (f"No inventory row for {sku} in size {size}. Sizes on file: {sizes}."
                   if sizes else f"SKU {sku} is not in the inventory table.")
        return {"found": False, "sku": sku, "size": size, "message": message}

    row = rows[0]
    result = {"found": True, **row}
    if qty_needed > 0:
        shortfall = max(qty_needed - row["on_hand"], 0)
        result["qty_needed"] = qty_needed
        result["shortfall"] = shortfall
        result["can_fill_from_stock"] = shortfall == 0
        if row["unit_cost"] is not None:
            result["restock_cost_of_shortfall"] = round(shortfall * row["unit_cost"], 2)
    if row["unit_cost"] is None:
        result["pricing_note"] = f"No pricing row for {sku}."
    return result


@mcp.tool
def check_margin(sku: str, unit_price: float, qty: int = 1) -> dict:
    """Margin check for selling `qty` of a SKU at `unit_price` (e.g. a discounted bulk price).

    Reads the pricing table. Returns unit cost, list price, the discount off list,
    margin per unit and in total, and whether the price is below cost.
    """
    sku = sku.strip().upper()
    if unit_price <= 0 or qty <= 0:
        return _refused("unit_price and qty must both be greater than zero.")
    rows = _query("SELECT sku, unit_cost, list_price FROM pricing WHERE UPPER(sku) = ?", [sku])
    if not rows:
        return {"found": False, "sku": sku, "message": f"SKU {sku} is not in the pricing table."}
    p = rows[0]
    margin_unit = unit_price - p["unit_cost"]
    return {
        "found": True,
        "sku": p["sku"],
        "qty": qty,
        "unit_cost": p["unit_cost"],
        "list_price": p["list_price"],
        "unit_price": unit_price,
        "discount_off_list_pct": round((1 - unit_price / p["list_price"]) * 100, 1),
        "margin_per_unit": round(margin_unit, 2),
        "margin_pct_of_price": round(margin_unit / unit_price * 100, 1),
        "total_price": round(unit_price * qty, 2),
        "total_cost": round(p["unit_cost"] * qty, 2),
        "total_margin": round(margin_unit * qty, 2),
        "below_cost": unit_price < p["unit_cost"],
    }


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead_days, open invoices and whether it will ship.

    Reads the vendors and invoices tables. A vendor with any open invoice will not ship new products.
    """
    vendors = _query("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
    for v in vendors:
        open_inv = _open_invoices_for_vendor(None, v["id"])
        v["open_invoice_ids"] = [i["id"] for i in open_inv]
        v["open_invoice_total"] = round(sum(i["amount"] for i in open_inv), 2)
        v["will_ship"] = not open_inv
    return {"count": len(vendors), "vendors": vendors}


# --- read tools: money and the shop space --------------------------------

@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Look up one vendor invoice, its vendor, and whether that vendor will ship.

    Reads the invoices, vendors and desk tables. Days overdue are counted from
    desk.date_today. Shop rule: a vendor will not ship new products while it
    has any unpaid (open) invoice, so this also lists all of that vendor's
    open invoices.
    """
    rows = _query(
        """
        SELECT inv.id AS invoice_id, inv.amount, inv.due_date, inv.status,
               inv.description, v.id AS vendor_id, v.name AS vendor_name,
               v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days
        FROM invoices inv
        LEFT JOIN vendors v ON v.id = inv.vendor_id
        WHERE inv.id = ?
        """,
        [invoice_id],
    )
    if not rows:
        return {"found": False, "invoice_id": invoice_id,
                "message": f"Invoice {invoice_id} is not in the invoices table."}

    row = rows[0]
    today = _shop_today()
    days_past_due = _days_between(row["due_date"], today)
    open_invoices = _open_invoices_for_vendor(None, row["vendor_id"])
    return {
        "found": True,
        **row,
        "shop_today": today,
        "is_open": row["status"] == "open",
        "days_overdue": days_past_due if row["status"] == "open" and days_past_due > 0 else 0,
        "vendor_open_invoices": open_invoices,
        "vendor_open_total": round(sum(i["amount"] for i in open_invoices), 2),
        "vendor_will_ship": len(open_invoices) == 0,
    }


@mcp.tool
def list_open_invoices() -> dict:
    """List every unpaid (open) invoice with its vendor and days overdue as of desk.date_today.

    Reads the invoices, vendors and desk tables.
    """
    today = _shop_today()
    rows = _query(
        """
        SELECT inv.id AS invoice_id, inv.amount, inv.due_date, inv.description,
               v.id AS vendor_id, v.name AS vendor_name
        FROM invoices inv LEFT JOIN vendors v ON v.id = inv.vendor_id
        WHERE inv.status = 'open' ORDER BY inv.due_date
        """
    )
    for r in rows:
        r["days_overdue"] = max(_days_between(r["due_date"], today), 0)
    return {"shop_today": today, "count": len(rows),
            "total_open": round(sum(r["amount"] for r in rows), 2), "invoices": rows}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up one shop lease: space, landlord, monthly rent and next due date.

    Reads the leases and desk tables. Days until due are counted from
    desk.date_today (negative means the rent is already overdue).
    """
    rows = _query(
        "SELECT id AS lease_id, space_name, landlord, monthly_rent, next_due, notes "
        "FROM leases WHERE id = ?",
        [lease_id],
    )
    if not rows:
        return {"found": False, "lease_id": lease_id,
                "message": f"Lease {lease_id} is not in the leases table."}

    row = rows[0]
    today = _shop_today()
    days_until_due = _days_between(today, row["next_due"])
    return {
        "found": True,
        **row,
        "shop_today": today,
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
    }


@mcp.tool
def get_cash_balance() -> dict:
    """Cash on hand per account, plus money already waiting for human approval.

    Reads cash_accounts (and the approvals queue). available_after_pending is what
    would be left if every pending request were approved.
    """
    accounts = _query("SELECT name, balance, date FROM cash_accounts ORDER BY name")
    pending = 0.0
    if _table_exists("approvals"):
        pending = _query("SELECT COALESCE(SUM(amount), 0) AS t FROM approvals WHERE status = 'pending'")[0]["t"]
    total = round(sum(a["balance"] for a in accounts), 2)
    return {"shop_today": _shop_today(), "accounts": accounts, "total_balance": total,
            "pending_approvals_total": round(pending, 2),
            "available_after_pending": round(total - pending, 2)}


@mcp.tool
def list_payments() -> dict:
    """List every payment already made (reads the payments table), including who approved it."""
    rows = _query("SELECT * FROM payments ORDER BY id")
    return {"count": len(rows), "total_paid": round(sum(r["amount"] for r in rows), 2), "payments": rows}


# --- write tools agents may use (nothing here moves money) ---------------

@mcp.tool
def request_payment(kind: Literal["invoice", "rent"], ref_id: int, requested_by: str, reason: str,
                    ticket_id: int | None = None, account: str = "checking") -> dict:
    """Ask a human to approve paying a vendor invoice (kind="invoice", ref_id=invoices.id)
    or a lease's rent (kind="rent", ref_id=leases.id). NO money moves here.

    The amount is read from the database (invoices.amount or leases.monthly_rent), never
    supplied by the agent. Refuses duplicates, invoices that are not open, and anything
    larger than the cash on hand. Returns the pending approval id.
    """
    if not requested_by.strip() or not reason.strip():
        return _refused("requested_by and reason are required.")
    with _write_tx() as conn:
        today = _shop_today(conn)
        if kind == "invoice":
            inv = _rows(conn, """SELECT i.*, v.name AS vendor_name FROM invoices i
                                 LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?""", [ref_id])
            if not inv:
                return _refused(f"Invoice {ref_id} is not in the invoices table.")
            inv = inv[0]
            if inv["status"] != "open":
                return _refused(f"Invoice {ref_id} has status '{inv['status']}', not open; nothing to pay.")
            amount = inv["amount"]
            details = {"vendor_id": inv["vendor_id"], "vendor_name": inv["vendor_name"],
                       "due_date": inv["due_date"], "description": inv["description"],
                       "days_overdue": max(_days_between(inv["due_date"], today), 0)}
        elif kind == "rent":
            lease = _rows(conn, "SELECT * FROM leases WHERE id = ?", [ref_id])
            if not lease:
                return _refused(f"Lease {ref_id} is not in the leases table.")
            lease = lease[0]
            amount = lease["monthly_rent"]
            details = {"space_name": lease["space_name"], "landlord": lease["landlord"],
                       "period_due": lease["next_due"],
                       "days_until_due": _days_between(today, lease["next_due"])}
        else:
            return _refused(f"Unknown payment kind '{kind}'. Use 'invoice' or 'rent'.")

        existing = _rows(conn, "SELECT id, status, details FROM approvals WHERE kind = ? AND ref_id = ? "
                               "AND status IN ('pending', 'approved')", [kind, ref_id])
        # an invoice can only be requested once; rent once per due period
        dup = [d for d in existing if kind == "invoice"
               or json.loads(d["details"] or "{}").get("period_due") == details["period_due"]]
        if dup:
            return _refused(f"There is already a {kind} request for {ref_id} (approval {dup[0]['id']}, "
                            f"status {dup[0]['status']}).", approval_id=dup[0]["id"])
        if (bad := _cash_check(conn, account, amount)):
            return bad

        pending_before = _pending_total(conn, account)
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, amount, account, details, reason, "
            "requested_by, requested_at, status) VALUES (?,?,?,?,?,?,?,?,?, 'pending')",
            [kind, ref_id, ticket_id, amount, account, json.dumps(details), reason.strip(),
             requested_by.strip(), today],
        )
        balance = _rows(conn, "SELECT balance FROM cash_accounts WHERE name = ?", [account])[0]["balance"]
        result = {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "kind": kind,
                  "ref_id": ref_id, "amount": amount, "account": account, "details": details,
                  "cash_balance": balance, "pending_total_including_this": round(pending_before + amount, 2),
                  "message": "Waiting for human approval. No money has moved."}
        if pending_before + amount > balance:
            result["warning"] = ("Approving every pending request would overdraw the account; "
                                 "a human must choose which to approve first.")
        return result


@mcp.tool
def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int, requested_by: str,
                           reason: str, ticket_id: int | None = None, account: str = "checking") -> dict:
    """Ask a human to approve a restock purchase order. NO money moves here.

    Cost = qty x pricing.unit_cost (from the database). The SKU and size must already be
    in inventory, qty must be 1-100, and the cost must fit the cash on hand. If the vendor
    has an open invoice the request is saved but marked blocked: it cannot be paid until
    that invoice is paid, because the vendor will not ship.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if not requested_by.strip() or not reason.strip():
        return _refused("requested_by and reason are required.")
    if not 1 <= qty <= MAX_PO_QTY:
        return _refused(f"qty must be between 1 and {MAX_PO_QTY} for a single purchase order.")
    with _write_tx() as conn:
        today = _shop_today(conn)
        vendor = _rows(conn, "SELECT * FROM vendors WHERE id = ?", [vendor_id])
        if not vendor:
            return _refused(f"Vendor {vendor_id} is not in the vendors table.")
        vendor = vendor[0]
        item = _rows(conn, """SELECT i.sku, i.name, i.size, i.qty, p.unit_cost FROM inventory i
                              LEFT JOIN pricing p ON p.sku = i.sku
                              WHERE UPPER(i.sku) = ? AND UPPER(i.size) = ?""", [sku, size])
        if not item:
            return _refused(f"{sku} size {size} is not in the inventory table; only reorder items the shop carries.")
        item = item[0]
        if item["unit_cost"] is None:
            return _refused(f"No pricing row for {sku}, so the cost cannot be computed.")
        amount = round(qty * item["unit_cost"], 2)
        if (bad := _cash_check(conn, account, amount)):
            return bad
        blocked_by = [i["id"] for i in _open_invoices_for_vendor(conn, vendor_id)]
        details = {"vendor_name": vendor["name"], "vendor_specialty": vendor["specialty"],
                   "lead_days": vendor["lead_days"], "sku": item["sku"], "name": item["name"],
                   "size": item["size"], "qty": qty, "unit_cost": item["unit_cost"],
                   "on_hand_now": item["qty"], "blocked_by_open_invoices": blocked_by,
                   "arrives_if_paid_today": (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()}
        pending_before = _pending_total(conn, account)
        cur = conn.execute(
            "INSERT INTO approvals (kind, ref_id, ticket_id, amount, account, details, reason, "
            "requested_by, requested_at, status) VALUES ('purchase_order',?,?,?,?,?,?,?,?, 'pending')",
            [vendor_id, ticket_id, amount, account, json.dumps(details), reason.strip(),
             requested_by.strip(), today],
        )
        result = {"ok": True, "approval_id": cur.lastrowid, "status": "pending", "kind": "purchase_order",
                  "amount": amount, "account": account, "details": details,
                  "pending_total_including_this": round(pending_before + amount, 2),
                  "message": "Waiting for human approval. No money has moved."}
        if blocked_by:
            result["warning"] = (f"{vendor['name']} will not ship while invoice(s) {blocked_by} are unpaid; "
                                 "this order cannot be paid until they are.")
        return result


@mcp.tool
def list_approvals(status: Literal["pending", "approved", "rejected", "all"] = "pending") -> dict:
    """List payment and purchase-order requests in the human approval queue (default: pending)."""
    if not _table_exists("approvals"):
        return {"count": 0, "approvals": [], "message": "No approval requests yet."}
    if status == "all":
        rows = _query("SELECT * FROM approvals ORDER BY id")
    else:
        rows = _query("SELECT * FROM approvals WHERE status = ? ORDER BY id", [status])
    return {"count": len(rows), "total": round(sum(r["amount"] for r in rows), 2),
            "approvals": [_approval_out(r) for r in rows]}


@mcp.tool
def save_customer_draft(ticket_id: int, subject: str, body: str, created_by: str) -> dict:
    """Save a message to the ticket's requester as a DRAFT on the board. It is never sent.

    The recipient is always tickets.requester for that ticket.
    """
    if not subject.strip() or not body.strip() or not created_by.strip():
        return _refused("subject, body and created_by are required.")
    with _write_tx() as conn:
        ticket = _rows(conn, "SELECT id, requester FROM tickets WHERE id = ?", [ticket_id])
        if not ticket:
            return _refused(f"Ticket {ticket_id} is not in the tickets table.")
        today = _shop_today(conn)
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, to_name, subject, body, created_by, created_at) VALUES (?,?,?,?,?,?)",
            [ticket_id, ticket[0]["requester"], subject.strip(), body.strip(), created_by.strip(), today],
        )
        return {"ok": True, "draft_id": cur.lastrowid, "ticket_id": ticket_id,
                "to_name": ticket[0]["requester"], "status": "draft",
                "message": "Saved as a draft on the board. Nothing was sent."}


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> dict:
    """List customer message drafts on the board, optionally for one ticket."""
    if not _table_exists("drafts"):
        return {"count": 0, "drafts": []}
    if ticket_id is None:
        rows = _query("SELECT * FROM drafts ORDER BY id")
    else:
        rows = _query("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", [ticket_id])
    return {"count": len(rows), "drafts": rows}


@mcp.tool
def update_ticket(ticket_id: int, status: Literal["open", "in_progress", "waiting_approval", "resolved"],
                  note: str, updated_by: str) -> dict:
    """Set a ticket's status and append a dated note to tickets.notes (the original notes are kept).

    A ticket cannot be marked resolved while it still has a pending approval.
    """
    if not note.strip() or not updated_by.strip():
        return _refused("note and updated_by are required.")
    if status not in TICKET_STATUSES:
        return _refused(f"status must be one of {TICKET_STATUSES}.")
    with _write_tx() as conn:
        ticket = _rows(conn, "SELECT id, status, notes FROM tickets WHERE id = ?", [ticket_id])
        if not ticket:
            return _refused(f"Ticket {ticket_id} is not in the tickets table.")
        if status == "resolved":
            pending = _rows(conn, "SELECT id FROM approvals WHERE ticket_id = ? AND status = 'pending'", [ticket_id])
            if pending:
                return _refused(f"Ticket {ticket_id} still has pending approval(s) {[p['id'] for p in pending]}; "
                                "it cannot be resolved until a human decides them.")
        today = _shop_today(conn)
        notes = (ticket[0]["notes"] or "").rstrip()
        notes = f"{notes}\n[{today} {updated_by.strip()}] {note.strip()}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", [status, notes, ticket_id])
        return {"ok": True, "ticket_id": ticket_id, "old_status": ticket[0]["status"],
                "new_status": status, "notes": notes}


# --- HUMAN-ONLY tools: never given to an agent ---------------------------
# The backend calls these when a person clicks Approve / Reject on the dashboard.

@mcp.tool
def approve_and_pay(approval_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve one pending request and pay it, in a single transaction.

    Refuses if: the approver is an agent; the request is not pending; cash would go
    negative; the invoice is no longer open; the rent period was already paid; or a
    purchase-order vendor still has an unpaid invoice. On success it writes a payments
    row (approved_by = the human), lowers cash_accounts.balance, and updates the source
    table: invoices.status -> 'paid', or leases.next_due -> one month later.
    """
    approver = approved_by.strip()
    if not approver:
        return _refused("approved_by (the human's name) is required.")
    if approver.lower() in AGENT_NAMES:
        return _refused("Payments must be approved by a human, not an agent.")
    with _write_tx() as conn:
        rows = _rows(conn, "SELECT * FROM approvals WHERE id = ?", [approval_id])
        if not rows:
            return _refused(f"Approval {approval_id} does not exist.")
        appr = _approval_out(rows[0])
        if appr["status"] != "pending":
            return _refused(f"Approval {approval_id} is already {appr['status']}.")
        if (bad := _cash_check(conn, appr["account"], appr["amount"])):
            return bad
        today = _shop_today(conn)
        updated = {}
        if appr["kind"] == "invoice":
            inv = _rows(conn, "SELECT status FROM invoices WHERE id = ?", [appr["ref_id"]])
            if not inv or inv[0]["status"] != "open":
                return _refused(f"Invoice {appr['ref_id']} is not open any more; nothing to pay.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", [appr["ref_id"]])
            updated["invoices"] = {"id": appr["ref_id"], "status": "paid"}
        elif appr["kind"] == "rent":
            lease = _rows(conn, "SELECT next_due FROM leases WHERE id = ?", [appr["ref_id"]])
            if not lease or lease[0]["next_due"] != appr["details"].get("period_due"):
                return _refused(f"Rent for lease {appr['ref_id']} due {appr['details'].get('period_due')} "
                                "was already paid or the lease changed.")
            new_due = _add_month(lease[0]["next_due"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", [new_due, appr["ref_id"]])
            updated["leases"] = {"id": appr["ref_id"], "next_due": new_due}
        elif appr["kind"] == "purchase_order":
            still_open = [i["id"] for i in _open_invoices_for_vendor(conn, appr["ref_id"])]
            if still_open:
                return _refused(f"Vendor {appr['details'].get('vendor_name')} will not ship while invoice(s) "
                                f"{still_open} are unpaid. Pay those first.")
            updated["purchase_order"] = {"expected_arrival": (date.fromisoformat(today) + timedelta(
                days=appr["details"]["lead_days"])).isoformat()}
        else:
            return _refused(f"Unknown approval kind '{appr['kind']}'.")

        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
            [appr["kind"], appr["id"] if appr["kind"] == "purchase_order" else appr["ref_id"],
             appr["amount"], appr["account"], today, approver],
        )
        conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                     [appr["amount"], today, appr["account"]])
        conn.execute("UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, payment_id = ? "
                     "WHERE id = ?", [approver, today, pay.lastrowid, approval_id])
        balance = _rows(conn, "SELECT balance FROM cash_accounts WHERE name = ?", [appr["account"]])[0]["balance"]
        return {"ok": True, "approval_id": approval_id, "payment_id": pay.lastrowid, "kind": appr["kind"],
                "amount": appr["amount"], "approved_by": approver, "paid_at": today,
                "new_balance": balance, "updated": updated}


@mcp.tool
def reject_approval(approval_id: int, rejected_by: str, reason: str) -> dict:
    """HUMAN ONLY. Reject one pending request. No money moves."""
    who = rejected_by.strip()
    if not who or not reason.strip():
        return _refused("rejected_by (the human's name) and reason are required.")
    if who.lower() in AGENT_NAMES:
        return _refused("Only a human can reject an approval request.")
    with _write_tx() as conn:
        rows = _rows(conn, "SELECT status FROM approvals WHERE id = ?", [approval_id])
        if not rows:
            return _refused(f"Approval {approval_id} does not exist.")
        if rows[0]["status"] != "pending":
            return _refused(f"Approval {approval_id} is already {rows[0]['status']}.")
        conn.execute("UPDATE approvals SET status = 'rejected', decided_by = ?, decided_at = ?, decision_note = ? "
                     "WHERE id = ?", [who, _shop_today(conn), reason.strip(), approval_id])
        return {"ok": True, "approval_id": approval_id, "status": "rejected", "rejected_by": who}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument("--http", action="store_true",
                        help="Serve Streamable HTTP on port 8001 instead of stdio")
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()
