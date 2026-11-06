# Harness — HW5: Campus Customs Multi-Agent Operations

**Contents:** [Tables](#problem-2--database-tables) · [MCP tools](#mcp-tools-mcp_servermcp_serverpy-20-tools) · [The five agents](#agents) · [Safety rules](#safety) · [API routes](#problem-7--backend-routes) · [Dashboard](#problem-8--agent-dashboard) · [Problem 9 full run](#problem-9--full-run-on-the-three-tickets)

Final system: 9 shop tables (+ `approvals` and `drafts` in the working copy), a FastMCP server with 20 tools, 5 PydanticAI agents on gpt-6-luna via Portkey, a FastAPI backend (14 routes), and a React desk. Every agent step is appended to `output/audit_trail.json`.

## Problem 2 — Database tables

Database: `data/campus_customs.db` (original, kept untouched for resets).
Working copy: `data/campus_customs_new.db` (the MCP server and backend read and write this one).

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | `date_today` is the shop's "today" (2026-08-31); every agent uses it to decide what is overdue or due soon. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The Boss's work queue; the `sku`/`size`/`lease_id`/`invoice_id` fields tell it which agents and tables each ticket needs. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`) | Inventory agent checks stock by SKU and size here to spot shortfalls. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Accounting uses cost vs. list price to check margins on discounts and the cost of restocks. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Inventory picks which vendor can restock an item and uses `lead_days` to estimate when it arrives. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Facilities tracks rent amount and due date for the shop space. |
| `cash_accounts` | `name`, `balance`, `date` | Accounting checks the balance before any payment; the pay tool must refuse if it would go negative. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Record of every human-approved payment; `approved_by` proves a human signed off. Starts empty. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Accounting finds unpaid bills here; a vendor with an open invoice will not ship new products. |

### How the three open tickets link to the tables

- **#101 customer_order** — `sku` CC-TEE-WHITE, size S, qty 1 → `inventory` shows 0 in stock. `invoice_id` 501 → `invoices` ($840, due 2026-08-28, open, 3 days overdue) → `vendors` id 1, Bulldog Print Co (5-day lead). The invoice must be paid (human approval) before Bulldog will reprint.
- **#102 rent_notice** — `lease_id` 1 → `leases` Chapel Street shop, $2,400 due 2026-09-02 (2 days away). Paying it needs human approval and draws from `cash_accounts`.
- **#103 price_override** — `sku` CC-HOOD-NAVY, size M, qty 20 → `inventory` has 8 (12 short); `pricing` cost $22 / list $58 sets how much discount is possible.

**Cash constraint:** checking has $3,400. Invoice 501 + rent = $3,240, leaving $160 — not enough to also restock 12 hoodies at $22 ($264).

## Problem 3 — MCP tools

Server: `mcp_server/server.py` (FastMCP, read-only on `data/campus_customs_new.db`).

| Tool | Tables it reads | Ticket it unlocks | Why it is the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size, qty_needed)` | `inventory`, `pricing` | **101** (also 103) | Ticket 101 orders 1 CC-TEE-WHITE in size S, and this tool returns on hand = 0, shortfall = 1 for that exact SKU and size, proving the order must be restocked (for 103 it shows 8 of 20 hoodies in M plus the $22 cost and $58 list price behind any discount). |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | **101** | Ticket 101 links to invoice 501, and this tool shows that $840 bill to Bulldog Print Co is open and 3 days overdue as of desk.date_today, so `vendor_will_ship` is false and the tee cannot be reprinted until Accounting gets human approval to pay it. |
| `get_lease(lease_id)` | `leases`, `desk` | **102** | Ticket 102 links to lease 1, and this tool returns the $2,400 Chapel Street rent owed to Elm City Properties on 2026-09-02, 2 days after desk.date_today, giving Facilities the exact amount and deadline for a human-approved rent payment. |

## Problem 5 — Agent team, MCP tools and safety

Built with PydanticAI in `backend/` (`models.py` = data types, `agents/` = one file per agent + shared `base.py`, `config.py`, `audit.py`, `team.py`; `prompts/` = one prompt per agent). Every agent uses **gpt-6-luna through Portkey** (hard-coded in `agents/config.py`; Portkey reports it back as `gpt-6-luna-global`). Shop facts come only from the MCP server, attached in-process with PydanticAI's `MCPToolset`; there is no other shop-data layer.

### Agents

| Agent | Prompt | Job | MCP tools it may call |
|---|---|---|---|
| Boss | `prompts/boss.md` | Reads each ticket, delegates, makes the final call, sets ticket status. Returns `BossDecision`. | `get_shop_today`, `list_open_tickets`, `get_ticket`, `get_cash_balance`, `list_approvals`, `list_drafts`, `update_ticket` |
| Inventory | `prompts/inventory.md` | Stock by SKU + size, shortfalls, which vendor can restock and its lead time. | `get_shop_today`, `get_ticket`, `check_stock`, `list_vendors`, `get_invoice` |
| Accounting | `prompts/accounting.md` | Cash, invoices, margins; prepares payments and purchase orders **for human approval**. | `get_shop_today`, `get_ticket`, `get_cash_balance`, `list_open_invoices`, `get_invoice`, `check_margin`, `list_payments`, `list_approvals`, `request_payment`, `request_purchase_order` |
| Facilities | `prompts/facilities.md` | The shop space: lease, landlord, rent and due date. | `get_shop_today`, `get_ticket`, `get_lease` |
| Customer Service | `prompts/customer_service.md` | Drafts messages to the ticket's requester; drafts stay on the board. | `get_shop_today`, `get_ticket`, `save_customer_draft`, `list_drafts` |

**Full connectivity:** every agent also has `ask_agent(agent, task)` and can hand a task to any other agent (not itself).

### MCP tools (`mcp_server/server.py`, 20 tools)

| Tool | Tables it uses | Notes |
|---|---|---|
| `get_shop_today` | desk | The shop's today (`date_today`). |
| `list_tickets` *(P7)* | tickets, desk | Every ticket, open and resolved, for the board. Used by the backend; not on any agent's list. |
| `list_open_tickets` | tickets, desk | All tickets not resolved. |
| `get_ticket` | tickets, desk | One ticket in full. |
| `check_stock` *(P3)* | inventory, pricing | On hand, shortfall and restock cost for one SKU + size. |
| `check_margin` | pricing | Discount off list and margin at a proposed price; flags below cost. |
| `list_vendors` | vendors, invoices | Specialty, lead_days, open invoices, `will_ship`. |
| `get_invoice` *(P3)* | invoices, vendors, desk | Days overdue and whether the vendor will ship. |
| `list_open_invoices` | invoices, vendors, desk | Every unpaid invoice with days overdue. |
| `get_lease` *(P3)* | leases, desk | Rent, landlord, next due, days until due. |
| `get_cash_balance` | cash_accounts, approvals, desk | Cash on hand and what is already pending approval. |
| `list_payments` | payments | Payments made and who approved them. |
| `request_payment` | invoices or leases, vendors, cash_accounts, desk → **writes approvals** | Pending request only; amount read from the DB. |
| `request_purchase_order` | vendors, inventory, pricing, invoices, cash_accounts, desk → **writes approvals** | Pending request only; cost = qty × unit_cost; marked blocked if the vendor has an unpaid invoice. |
| `list_approvals` | approvals | The human approval queue. |
| `save_customer_draft` | tickets, desk → **writes drafts** | Recipient is always the ticket's requester; never sent. |
| `list_drafts` | drafts | Drafts on the board. |
| `update_ticket` | tickets, approvals, desk → **writes tickets** | Status + dated note; can't resolve with pending approvals. |
| `approve_and_pay` — **human only** | approvals, cash_accounts, invoices / leases / vendors, desk → **writes payments, cash_accounts, invoices.status or leases.next_due, approvals** | One transaction; refuses agents, overdrafts, blocked vendors, double pays. |
| `reject_approval` — **human only** | approvals → **writes approvals** | Closes a request; no money moves. |

`approvals` and `drafts` are new tables the server creates in the working copy only (`campus_customs_new.db`); resetting from the original removes them.

### Safety

**Guardrails for real customers and real money**
- **A human approves every payment.** Agents can only create *pending* requests. `approve_and_pay` and `reject_approval` are on no agent's tool list, a hook blocks them again if called, and the server refuses an approver named like an agent.
- **Amounts come from the database, not the model.** Invoice amount, monthly rent and qty × unit_cost are read by the tool; the agent never types a dollar figure.
- **No negative balances.** Requests and payments larger than cash on hand are refused; payment, cash update and invoice/lease update happen in one transaction or not at all. Duplicate requests and double payments are refused.
- **Shop rules in code, not just prompts:** a vendor with an unpaid invoice can't be paid for a new order; a ticket can't be resolved with pending approvals; purchase orders are capped at 100 units and only for items the shop carries.
- **Least privilege.** Each agent sees only its own tools (Facilities can't request money; only the Boss changes ticket status; only Customer Service writes drafts).
- **Who did what is enforced.** A hook overwrites `requested_by` / `created_by` / `updated_by` with the real agent's name, so no agent can sign as another.
- **No real contact.** No email, phone or vendor tools exist; customer messages are drafts on the board for a person to review.
- **No invented facts.** Tools return "not found" instead of guessing; prompts require every number to come from a tool.
- **Board-level guards (P7–P9).** Only one team run at a time, so two runs can't race for the same cash. The approve route is the only place money moves, and it refuses agent names and missing names. A ticket is resolved automatically only when a human has approved at least one request and nothing is left pending, checked both after each signature and when a run ends (a person may sign before the Boss finishes). Otherwise a person clicks Mark resolved, which is refused while approvals are pending. The browser may only call the API from the Vite page origin (CORS).
- **Full audit.** Every agent-loop step (task in, model response with tool calls and token usage, tool results, delegations, refusals, final output) is appended to `output/audit_trail.json`, which is never wiped.

**Limits that keep token use in check** (`backend/agents/config.py`)
- One model only (gpt-6-luna), reasoning effort set to low, max 8,000 output tokens per response.
- Per team run: max 30 model calls, 60 tool calls, 250,000 total tokens (shared across all agents).
- Per agent: max 10 model calls before it is stopped.
- Delegation: max depth 2 (Boss → worker → one more worker), max 8 delegations per run, no delegating to yourself.
- Tool results are compact JSON; audit previews are truncated; prompts tell agents not to repeat lookups.
- Live smoke test (read-only, ticket 102, scratch DB): Boss → Facilities, 6 model calls, about 12.7k tokens, about 15 seconds.

## Problem 7 — Backend routes

FastAPI app in `backend/main.py`. Start from `backend/` with `uvicorn main:app --reload --port 8000` → http://localhost:8000 (interactive docs at `/docs`). All shop data goes through the MCP server; added MCP tool `list_tickets` (reads tickets) so the board can show resolved tickets too (server now has 20 tools).

- `GET /api/health` — backend is up; model (gpt-6-luna) and database in use.
- `GET /api/agents` — the five agents and their roles.
- `GET /api/tickets` — every ticket with its status and `resolved` true/false.
- `POST /api/tickets/{ticket_id}/run` — run the agent team on that ticket (returns a `run_id` at once; `?wait=true` waits for the result). One run at a time; refuses resolved or unknown tickets.
- `GET /api/runs` / `GET /api/runs/{run_id}` — status and final Boss decision of team runs.
- `GET /api/events?since=&run_id=&ticket_id=` — recent agent events from the audit trail: what each agent said, which tools it called, delegations; poll with `since=next_since` to refresh the board.
- `GET /api/approvals?status=pending` — payments and purchase orders the agents prepared, waiting for a human.
- `POST /api/approvals/{approval_id}/approve` — body `{"approved_by": "<human name>"}`; a human clicked Approve, so pay it. **The only route that changes cash**; refuses agents, overdrafts, blocked vendors and double approvals (HTTP 409).
- `POST /api/approvals/{approval_id}/reject` — body `{"rejected_by", "reason"}`; reject a request, no money moves.
- `GET /api/cash` — current checking balance from cash_accounts, plus the total pending approval.
- `GET /api/drafts?ticket_id=` — customer message drafts on the board (never sent).
- `POST /api/tickets/{ticket_id}/resolve` — body `{"resolved_by"}`; a person marks a ticket resolved (refused while approvals are pending). *(added in Problem 8)*
- `POST /api/reset` — copy the original `campus_customs.db` over `campus_customs_new.db` for a fresh run (refused while a run is working; the audit trail is kept).

## Problem 8 — Agent dashboard

React + Vite + TypeScript app in `frontend/` (start with `npm run dev` → http://localhost:5173). It calls the backend at `http://localhost:8000` (`VITE_API_URL`, see `frontend/.env.example`); the backend allows the Vite origin through CORS. Design choices are in `output/design.md`.

- Polls `/api/tickets`, `/api/events`, `/api/approvals`, `/api/cash`, `/api/drafts` and `/api/runs` every 1.5 s, so agents' words and tool calls show up live while a run is going.
- Backend change: when a human approves the last pending item on a ticket that is `waiting_approval`, the approve route marks that ticket resolved (logged in the audit trail), plus a human `resolve` route.
- Verified in the browser against a scratch database: ran #102 and #101 live, watched desks light up, signed cheques (blocked purchase order refused until its invoice was paid), saw the till drop $3,400 → $1,000 → $160 → $152 and both tickets auto-resolve, then reset.

## Problem 9 — Full run on the three tickets

Reset `data/campus_customs_new.db` from the original (2026-11-06 04:57:42 UTC; starting checking **$3,400.00**), then ran 101 → 102 → 103 from the board. Details: `output/desk_tickets.html` (Expected vs Actual and Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html` (board screenshots), and every step in `output/audit_trail.json`.

| Ticket | Boss called first | Delegations | Human approvals | Cash change | Final |
|---|---|---|---|---|---|
| 101 tee S | Inventory (with Accounting and Customer Service in the same step) | 6 (3 agent-to-agent) + 2 refused at depth 2 | Laila: invoice 501 **$840**, then purchase order 1 × tee S **$8** | −$848.00 | resolved after the last signature |
| 102 rent | Facilities | 2 | Laila: rent for lease 1 **$2,400** | −$2,400.00 | resolved after the signature |
| 103 hoodies | Accounting (margins), then Inventory and Customer Service | 3 | none (no money needed) | $0.00 | Boss left it in_progress; Laila marked it resolved |

**Cash:** $3,400.00 − $840.00 − $8.00 − $2,400.00 = **$152.00**, which equals `cash_accounts.balance` (checking) in the working database. The `payments` table has 3 rows totaling $3,248.00, each `approved_by = Laila`. Invoice 501 is now `paid`; lease 1's `next_due` moved to 2026-10-02.

**Tokens:** 101 used 27 model calls / 71,688 tokens; 102 used 12 / 30,601; 103 used 13 / 32,813. That's about 135k for the full run, well under the 250k-per-run cap on each. Ticket 101 was the most expensive because Inventory was asked three times (by the Boss, Accounting and Customer Service). The depth-2 guardrail stopped two more loops back to Accounting. Runs 102 and 103 matched earlier identical runs token for token and finished in seconds: Portkey served the model replies from its cache, while every tool call still ran against the database (approval 3 and draft 2 exist).

**What the comparison taught me**
- The first calls matched my plan on 101 and 102. On 103 the Boss went to Accounting first, treating it as a pricing question.
- My 103 plan assumed invoice 501 was still unpaid. Because I signed it on 101 first, Bulldog was no longer blocked and that hand-off rightly didn't happen. The order of human approvals changes what later tickets see.
- Customer Service stayed cautious. The 103 draft doesn't quote the $50 price or offer size L, so a person should edit it before sending. That's the reason drafts stay on the board.
- Signing a cheque while a run was still finishing exposed a bug: the ticket never auto-resolved. It's fixed by also checking when the run ends.

**Coverage checklist:** tables → Problem 2 · MCP tools → Problems 3 and 5 (20 tools, each with its tables) · five agents → Problem 5 · API routes → Problem 7 (+ resolve route, P8) · dashboard → Problem 8 and `output/design.md` · safety rules and token limits → Problem 5 Safety.
