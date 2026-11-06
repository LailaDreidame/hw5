# Campus Customs — Multi-Agent Operations (MGT 409, Homework 5)

An agent team runs a small Yale merch shop. Tickets land on a desk board: customer orders, rent notices, unpaid bills, discount requests. Five PydanticAI agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) work them using one shared **MCP server** over a SQLite database. A **FastAPI** backend runs the team, and a **React** desk lets a person watch the agents and **approve every payment**.

- Model: **gpt-6-luna** through **Portkey**, for every agent (hard-coded in `backend/agents/config.py`).
- Money only moves when a human clicks Approve on the board. Agents can only prepare requests.
- Every agent-loop step is appended to `output/audit_trail.json`.

## Layout

```
hw5/
├── AI_prompts.md            what I typed to my vibe coder, problem by problem
├── requirements.txt         Python packages (MCP server + backend)
├── .env.example             PORTKEY_API_KEY placeholder (copy to .env)
├── .mcp.json                registers the MCP server with Claude Code
├── data/
│   ├── campus_customs.db        original shop data, never modified
│   └── campus_customs_new.db    working copy the app reads and writes
├── mcp_server/
│   ├── server.py            FastMCP server, 20 tools
│   └── README.md
├── backend/
│   ├── main.py              FastAPI routes
│   ├── models.py            data types
│   ├── agents/              boss, inventory, accounting, facilities, customer_service (+ shared base, config, audit, team)
│   ├── prompts/             one prompt per agent
│   └── run_team.py          run the team from the command line
├── frontend/                React + Vite + TypeScript desk board
└── output/                  harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                             resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

## Setup (once)

Needs Python 3.12 and Node 20+.

```bash
cd hw5
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                      # then put your real PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

The backend also reads `PORTKEY_API_KEY` from your shell environment if it's already set there.

## Run it

### 1. Copy the original database to the working copy (whenever you want a clean run)

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

`campus_customs.db` is never changed. Everything the agents and approvals do happens in `campus_customs_new.db`, so copying the original back resets the shop: $3,400 in checking, tickets 101–103 open, no payments.

### 2. Start the MCP server

```bash
.venv/bin/python mcp_server/server.py           # stdio (what Claude Code uses via .mcp.json)
.venv/bin/python mcp_server/server.py --http    # or HTTP at http://127.0.0.1:8001/mcp
```

The backend attaches this same server in-process, so you don't need it running separately for the board. Start it on its own to call the tools from your vibe coder; `.mcp.json` registers it as `campus-customs`.

### 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

API at http://localhost:8000 (interactive docs at http://localhost:8000/docs).

### 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000` (change with `VITE_API_URL`, see `frontend/.env.example`).

### 5. Reset the database before a full three-ticket run

Click **Reset shop** on the board (top right), or:

```bash
curl -X POST http://localhost:8000/api/reset     # same as step 1, while the backend is running
```

Then work the tickets in order:
1. **#101:** select it, click **Send to the team**, wait for the run to finish, then sign the **$840 invoice** cheque first and the **$8 purchase order** second (the order is blocked until the invoice is paid).
2. **#102:** Send to the team, then sign the **$2,400 rent**.
3. **#103:** Send to the team. No money is needed. Read the Boss's call and the draft, then click **Mark resolved**.

Expected end state: all three tickets resolved and **$152.00** in checking (`$3,400 − $840 − $8 − $2,400`). My run's results are in `output/desk_tickets.html` (Expected vs Actual, Cash and Reflection tabs), `output/resolved_tickets.json` and `output/resolved_board.html`.

## Safety rules (summary)

- A human approves every payment. `approve_and_pay` and `reject_approval` are on no agent's tool list, and the server refuses approvers named like agents.
- Payment amounts come from the database (invoice amount, monthly rent, qty × unit cost), never from the model.
- No negative balances, no double payments, and no paying a vendor that still has an unpaid invoice.
- No real email or calls: customer messages are saved as drafts on the board.
- Token limits per run: 30 model calls, 60 tool calls, 250k tokens; 10 model calls per agent; delegation depth 2; 8 delegations.

Full details are in `output/harness.md`.
