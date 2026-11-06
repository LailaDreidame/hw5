# Campus Customs Operations Desk — design notes

The board is a desk, not a dashboard. In 2026 most of us already have an AI agent doing *something* for us, and the hard part is no longer getting agents to work — it's being the person who stays in charge of them. So I designed for a shop manager who sits down with a coffee, sends tickets to the team, watches them work, and signs off on money. Everything on the screen answers one of three questions: **What needs doing? What is the team doing right now? What needs my signature?**

## Layout: three columns, left to right like the work flows
- **Left — Ticket queue.** The incoming work. Each ticket is a paper stub with a colored band by type (navy = customer order, violet = rent notice, rose = discount request), a perforated tear line, and a big serif ticket number you can read from across the room.
- **Center — The floor.** The selected ticket sits on top with one big button, **Send to the team**. Under it, five agent desks in a row, then a live transcript and the run report side by side. This is where the eye goes while a run is going.
- **Right — The till and the signature tray.** Money lives on its own column so it is never buried: the checking balance, the approvals waiting for me, and the customer drafts. The right column and the queue stay pinned while the center scrolls.
- The header carries the shop's day (from `desk.date_today`, not the real calendar), a live banner with a timer when the team is working ("Team on ticket #101 · 0:18"), the model chip (gpt-6-luna · Portkey) with a green/red connection dot, and **Reset shop**. On narrow screens the columns stack and the floor becomes a single column.

## How agents read differently
- **One color and one icon per agent, everywhere.** Boss = Yale blue star, Inventory = teal box, Accounting = amber coin stack, Facilities = violet building, Customer Service = rose speech bubble. The same color is used on their desk, their transcript lines, their report row and the cheques they prepare, so you can follow an agent without reading a name.
- **Desks light up.** A working desk lifts slightly, gets a glowing ring in its color and typing dots. A finished desk says *Done* in green. An agent the Boss didn't need fades to *Not called* — that makes "the Boss didn't call everyone" visible at a glance.
- **Speech bubbles in plain English.** Tool calls are translated: `check_stock` shows as "Counting stock on the shelf", `request_payment` as "Preparing a payment for your signature", `ask_agent` as "Asking Inventory: …". The raw tool names still appear as small code chips for anyone who wants the detail.
- **The transcript is indented by delegation depth**, so a hand-off (Boss → Inventory → Accounting) reads like a conversation thread. Hand-offs get a tinted row with an arrow, tool results show in small monospace, and each agent's final answer gets a solid bar in its color.

## How resolved tickets show up
- Tickets get **rubber stamps**: OPEN (grey outline), AWAITING SIGNATURE (amber), RESOLVED (green, tilted a little more like a real stamp). A resolved stub dims so the open work stands out.
- A green **"N to sign"** chip on a ticket means money is waiting on me for that ticket.
- When the last approval for a ticket is signed, the backend resolves it and the board says so in a toast: "Ticket #102 is resolved — nothing left to sign." If I want to close a ticket myself, **Mark resolved** appears once nothing is pending.
- When a run ends, a **Run report** appears: the Boss's call (summary, decision, next steps for me), then one row per agent — who asked them, who they handed off to, what they concluded, which tools they used, and how many model calls it took. The header of the report shows the run's total model calls and tokens.

## How cash shows up
- **The till** shows the checking balance as a big serif number. When I approve a payment it **counts down** to the new balance with a little "thud" and a red "−$2,400" that floats up and fades. That moment is the whole point of human approval, so I made it something you feel.
- An amber striped bar shows how much of the balance is already **waiting for my signature**, and the line under it says what would be **left if I sign everything** (it turns red if that would go negative).
- **Approvals look like cheques**: "Pay to Elm City Properties — $2,400", a memo line with the invoice or lease details, who prepared it and why, and two buttons: *Reject* and *Approve & pay $2,400*. I sign as a name I type once ("Signing as Laila", in italic like a signature), so every payment records a real person. A purchase order from a vendor with an unpaid invoice shows as an **amber, blocked cheque** with "sign that invoice first" — and if I try anyway the backend refuses and a red toast explains why.
- A footnote on the till says it plainly: cash only goes out, and nothing leaves until a person signs.

## Drafts
Customer messages are **postcards** with a dashed rose postmark that says *Draft · not sent*. It is impossible to mistake a draft for something that went to a customer.

## Why these choices
- **Trust.** Agents touch real customers and real money. The design keeps the human's job — signing — physically separate (its own column, its own green color, cheque metaphor) and makes every agent action visible and traceable.
- **Calm, then alive.** Idle, the desk is quiet: warm paper background with a faint dot grid, soft cards, "The floor is quiet". When the team works, motion appears only where something is happening — glowing desks, typing dots, a ticking timer — so attention goes to the right place. Motion turns off for people who prefer reduced motion.
- **Familiar objects.** Tickets, stamps, a till, cheques, postcards — everyone already knows what these mean, so nobody needs training to use the board.
- **Readable from a distance.** Serif display type (Iowan Old Style / Palatino) for numbers and headings, a clean system sans for text, monospace for money and tool names, and high-contrast Yale navy and gold for the header.
