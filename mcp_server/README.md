# Campus Customs MCP server

**What it is for:** the shared toolbox for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Every agent reaches the shop's data through these tools instead of writing its own SQL, so all agents see the same facts. Tools only return what is in the database (plus simple math on it, like days overdue or qty × unit cost) and say "not found" rather than guess.

**Database:** `data/campus_customs_new.db` — the working copy. The original `data/campus_customs.db` is never touched, so it can be copied back to reset the shop. "Today" is always `desk.date_today`, not the computer clock. The server adds two tables to the working copy when first needed: `approvals` (the human approval queue) and `drafts` (customer messages on the board).

## Tools (20)

**Tickets and date**
| Tool | Reads / writes | What it does |
|---|---|---|
| `get_shop_today()` | desk | The shop's today and desk notes. |
| `list_tickets()` | tickets | Every ticket, open and resolved (the desk board). |
| `list_open_tickets()` | tickets | Every ticket not yet resolved. |
| `get_ticket(ticket_id)` | tickets | One ticket in full. |
| `update_ticket(ticket_id, status, note, updated_by)` | writes tickets | Sets status, appends a dated note; won't resolve a ticket with pending approvals. |

**Stock, pricing, vendors**
| Tool | Reads / writes | What it does |
|---|---|---|
| `check_stock(sku, size, qty_needed=0)` | inventory, pricing | On hand, shortfall and restock cost for one SKU + size. |
| `check_margin(sku, unit_price, qty=1)` | pricing | Discount off list, margin per unit and total, below-cost flag. |
| `list_vendors()` | vendors, invoices | Specialty, lead days, open invoices, and whether each vendor will ship. |

**Money and the shop space**
| Tool | Reads / writes | What it does |
|---|---|---|
| `get_invoice(invoice_id)` | invoices, vendors | Amount, due date, days overdue, vendor, `vendor_will_ship`. |
| `list_open_invoices()` | invoices, vendors | Every unpaid invoice with days overdue. |
| `get_lease(lease_id)` | leases | Rent, landlord, next due date, days until due. |
| `get_cash_balance()` | cash_accounts, approvals | Cash on hand and the total already waiting for approval. |
| `list_payments()` | payments | Payments made and who approved them. |
| `request_payment(kind, ref_id, ...)` | writes approvals | Pending request to pay an invoice or rent; amount read from the DB. No money moves. |
| `request_purchase_order(vendor_id, sku, size, qty, ...)` | writes approvals | Pending restock order; cost = qty × unit cost; blocked if the vendor has an unpaid invoice. No money moves. |
| `list_approvals(status="pending")` | approvals | The human approval queue. |

**Customer drafts**
| Tool | Reads / writes | What it does |
|---|---|---|
| `save_customer_draft(ticket_id, subject, body, created_by)` | writes drafts | Draft to the ticket's requester; never sent. |
| `list_drafts(ticket_id=None)` | drafts | Drafts on the board. |

**Human only (never given to an agent)**
| Tool | Reads / writes | What it does |
|---|---|---|
| `approve_and_pay(approval_id, approved_by)` | writes payments, cash_accounts, invoices / leases, approvals | Pays one approved request in a single transaction; refuses agents, overdrafts, blocked vendors and double payments. |
| `reject_approval(approval_id, rejected_by, reason)` | writes approvals | Rejects a pending request; no money moves. |

## Run

From `hw5/`:

```bash
.venv/bin/python mcp_server/server.py          # stdio
.venv/bin/python mcp_server/server.py --http   # http://127.0.0.1:8001/mcp
```

Install: `pip install -r mcp_server/requirements.txt`. Set `CAMPUS_CUSTOMS_DB` to point at a scratch copy for testing (the original database is always refused).
