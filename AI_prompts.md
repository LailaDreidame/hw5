# AI Prompts Log — HW5: Campus Customs Multi-Agent Operations

---

## Problem 1 — Vibe coder prompts

**Prompt:**
> Okay. So the scenario is for this homework, campus customs multi-agent operations is the agentic team that runs the shop. We open the tickets, land on a board. Customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. I will build three pieces that talk to each other. An MCP server, a fast API backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests. Your agent team has full connectivity. Any agent may delegate tasks to any other agent for help. In this assignment, we will build these agents. Here are the agents as follows. Number one, boss. The boss reads each ticket, decides who should work on it, and makes final calls. Number two, inventory. Checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock. Number three, accounting. Watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval. Four, facilities. Handles the shop space side, leases, rent, etc. And number five, customer service. Drafts messages, forward customers. Data. We already downloaded the data.zip and unzipped it so we have data /campus_customs.db. That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash, accounts, payments, and invoices. Our tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point the MCP server and backend at that working copy. Keep campus_customs.db untouched so we can reset it when we want to start resolving the tickets. Rules of this shop. The field desk.date_today is today for the shop. Use this date to determine what is overdue. Vendor lead times come from the vendor's table. A vendor will not ship new products while they still haven't unpaid invoice. Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table. If there's not enough cash, the pay tool must refuse. No negative balances. Cash only goes out in this homework. We did not model revenue, so no money comes in. Before a full run to resolve the tickets, make sure to reset the database for to the original values. Do not email customers or call real vendors. Drafts stay on the board. We have to use our port API key for AI calls. For this assignment, use only GPT-6 Luna through port key for every agent. Multi-agent chats burn tokens fast. Points will be deducted if any other model shows up in our code or runs. We're going to work one problem at a time. Together as my vibe coder. We're going to type each problem in our own words, and we do not paste this homework URL. So let's start. With problem one, vibe coder prompts. Let's create an AI_prompts.md at the start of the assignment and keep it updated as we work. This file is a log of what we type to the vibe coder. We're going to describe each problem in our own words. We're going to put one section for each problem. Each section must include the problem number and title, at least one prompt I typed, and my own words as much as possible, one follow-up prompt if needed, and one sentence on what was lacking after the first.

**Follow-up:** None needed.

---

## Problem 2 — Study the Campus Customs database

**Prompt:**
> Okay, problem two is about study the campus customs database. This is worth 8 points. We're going to open the data /campus_customs.db file and look through every table and its fields. Copy the original file to data/campus_customs_new.db. Later, problems update that working copy. Study the three open tickets so we can see how they link to other tables.

**Follow-up:**
> Thanks. So we're going to start output /harness.md. For each table, we're going to list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems.

**What was lacking after the first:** My first prompt only asked to study the tables and tickets, so I followed up to have the findings written into output/harness.md with each table's fields and why it matters for the agents.

---

## Problem 3 — Build the MCP server

**Prompt:**
> Okay. Problem three is build the MCP server. This is where 12 points. I want us to really be diligent and deliberate in this work. We're going to write an MCP server in MCP underscore server using fastmcp. It will talk to data /campus_customs_new.db. You do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. You will add more tools to it later. For now, write three tools you know you will need for the tickets in the database. Keep the names clear. Never ever never ever invent any data. Only use information in the database. I repeat, only use information in the database. Then in output, /harness.md, lists each of your three MCP tools. For every tool, include which table it reads, which ticket it helps unlock, (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Vague lines like reads inventory, score low. Tie the tool to the ticket. Do not be vague. Be very clear. Be concise. And be specific. Also add a short MCP_server/readme.md file that explains what the MCP server is for. Which database file it uses, and the three tools it has.

**Follow-up:** None needed.

---

## Problem 4 — Add the MCP server to vibe coder and test each tool

**Prompt:**
> Okay, for problem four, we're going to add the MCP server to the Vibe Coder and test each tool. This is worth 8 points. So in the Vibe Coder, we're going to add the MCP server to this project so the Vibe Coder can call the tools. Save the connection JSON text in .mcp.json folder at the project root, or however you save local MCP server lists. With the Vibe Coder connected, test each of our three MCP tools. Save the evidence in /mcp_smoke.json folder. For every tool, you need to include in a very clear and specific and concise way the prompt I asked you to do, the tool name, the tool output must match values in data/campus_customs_new.db.

**Test questions I typed to the connected vibe coder:**
> Okay, for three questions. I would like to know, for stock about an item size, if there's an extra large in the Yale Bulldog tee. For ticket 101, then for invoice 501, I'm curious about the vendor's invoice . What's in there? And then for ticket 102, I'm wondering what the terms are for the shop's lease and if there's any actions I need to take in the next month or two to ensure that we are in good standing with our lease.

**Follow-up:**
> Okay, good. You went above and beyond in these questions. And just going to ask for good measure, for ticket 101, I want to make sure that there's a small in the bulldog T. And good job.

> Yes, use size S

**What was lacking after the first:** I wanted to make sure there were other sizes I could test, so I had a little fun and asked for the extra large first, then asked the real question about the small, and we used the small question as the prompt for ticket 101.

---

## Problem 5 — Build the agent team and grow the MCP tools

**Prompt:**
> Okay, let's do problem 5. Which is build the agent team and grow the MCP tools. This is worth 15 points. We need to get it really right. So let's build the energetic team for campus customs using pedantic AI. We're going to have a boss, we're going to have inventory, we're going to have accounting, we're going to have facilities, and we're going to have customer service. We need to include prompts, models, and agent loops so they can delegate work to each other with full connectivity. We've got to put the agent prompts in backend, /prompts/folder. This is one file per agent. Remember, one file per agent. Put data types in backend, /models.py. And the agents file under backend, /. Your layout can vary as long as the five roles are clear. And as a reminder, the five roles are boss, inventory, accounting, facilities, and customer service. We're going to use our port key and only GPT-6 Luna for every agent. We will write each prompt in my own words. With the shop rules, the agent needs more detailed prompts that cover all aspects of the agent's works and scope, score higher than a short generic prompt. So no generic prompts. If you feel like it's generic, flag it and we'll make it not generic. We're going to add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over data /campus_customs_new.db. Do not invent a second shop tools layer that bypasses MCP. Why are the agents so they append to output /audit_trail.json as they run? For each agent loop step, record enough to audit later. Append to this file. Do not wipe it, wipe each run. Do not wipe each run. In output/harness.md file, list each agent and each MCP tool, including ones you add in this problem. Along with which table the tool uses. Also add a short safety section. The guardrails are real business would want when agents touch real customers and real money. Plus limits that keep token use in check. Update the file MCP_server/readme.md so the tool list matches what we have now.

**Follow-up:**
> What if we added if the vendor's blocks say which invoice blocks it, and make sure that accounting knows

**What was lacking after the first:** The Inventory prompt only reported a blocked vendor back to the Boss, so I asked for it to name the blocking invoice and tell Accounting directly, and for Accounting to check that invoice against cash and answer.

---

## Problem 6 — Plan the three tickets

**Prompt:**
> Okay, so problem 6 we have to plan the 3 tickets. This problem is worth 8 points. Before you, wire the backend, write down what you expect the team to do on each open ticket. We're going to build output /desk_tickets.html file. A page you can double-click with one tab per ticket, (101, 102, and 103). Also add empty cache and reflection tabs for later problems. Leave them blank or with a shortcoming later note for now. On each ticket tab, fill an expected section only . Leave room for an actual section . We will fill after we run the agents.

**Follow-up:**
> For each ticket's expected section, write in my own words who the boss should call first and why, all the agent delegations I expect, not boss calls everyone, which MCP tools I expect that run to use. Plans that send every specialist on every ticket score low. We need to compare this plan to what actually happens when agents resolve the three tickets.

**What was lacking after the first:** My first prompt set up the page and tabs but didn't say what goes in each Expected section, so I added the Boss's first call and why, the specific delegations (not every specialist), and the MCP tools.

---

## Problem 7 — Backend routes

**Prompt:**
> Okay, that looked really good. Good job. Let's go to problem 7, backend routes. Our React frontend dashboard . The next problem needs a backend. It can call. In backend/main.py, use fast API and add routes that do the following. Return the 3 tickets and whether each is open or resolved. Take a ticket ID and run the agent team on that ticket. Return recent agent events, what each agent said and which tools they used. So the board can refresh. Approve a payment or purchase after a human clicks approve. Agents only prepare the pay. This route is what actually changes cash. Return the current checking balance from cash_accounts. Reset the database to the original values when you want to try a fresh run. Then from the backend/folder, start the server with uvicorn main:app --reload --port 8000 this turns on our backend at http://localhost:8000. So the front-end dashboard can call those routes. In folder, output /harness.md, lists each route in one line. What URL, and what it does.

**Follow-up:** None needed.

---

## Problem 8 — Agent dashboard

**Prompt:**
> Okay, so problem 8 is the agent dashboard. This is worth 12 points. We're going to build the front-end dashboard in the folder front-end /. With React plus VITE plus TypeScript. The page should call the routes you built in problem 7. At minimum, the board should list all 3 tickets, let us pick one ticket and start the agent team on it, show each agent and what they are saying, doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on the ticket, let a human approve a pay or purchase when asked, show the checking balance. It should drop after an approved pay, make the dashboard look good, be creative with the layout and feel. This is a real desk, people. Would want to sit at, so put thought into how it looks.

**Follow-up:**
> Also, tell the front end to talk to your back end at http://localhost:8000. On the back end, allow the VITE page origin usually http://localhost:5173 so the browser is allowed to call those routes. Start the board with npm run dev this opens the React desk in our browser so we can pick tickets and watch agents. Write output://design.md with what you chose for the dashboard look. Layout, how agents read differently, how resolve tickets and cache show up, and why, including the creative choices that make it feel special and something humans would actually enjoy using. And these are humans today in the year 2026. Thank you.

**What was lacking after the first:** My first prompt described what the board must do and look like, but not how it connects to the backend (localhost:8000 and the CORS origin), how to start it, or the design.md write-up explaining the look.

---

## Problem 9 — Resolve the tickets

**Prompt:**
> Okay, problem 9. Resolve the tickets. Before testing the agents on a full run over the 3 tickets, reset the working database data /campus_customs_new.db again so you can start clean. Note the starting checking balance. Then run all 3 tickets on the board, 101, 102, 103, until each is resolved. Open output /desk_tickets.html from problem 6. On each ticket tab, fill the actual section from this run. Which agents worked, what they delegated, and which tools they used. Keep your expected section so you can compare the two. Then on the cache tab of the same folder, output /desk_tickets.html itemize the money. Starting checking balance after the reset, for each ticket, how cash changed when the ticket resolved, and why, which pay purchase dollar amount, ending checking balance, it must match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. So make sure there is the right cash math. Also, save output /resolved_tickets.json for each ticket. ID final status short outcome what each agent contributed and any human approvals. And there should be human approvals. Output /resolved_board.html a page you can double check a page you can double click with a screenshot of your React board for each resolved ticket (101, 102, and 103). Append real runs to output /audit_trail.json finish output /harness.md so it covers tables MCP tools the 5 agents API routes, the dashboard, and safety rules.

**Follow-up:**
> All 3 resolved

**What was lacking after the first:** The first prompt asked for the reset and the write-ups, but the runs and approvals had to be done by me on the board, so I followed up once all three tickets were resolved so the actual results could be recorded.

---

## Problem 10 — Reflection

**Prompt:**
> Okay, so problem 10 is actually a reflection. So we have to open folder output /desk_tickets.html. And fill the reflection tab. I'm going to answer on my own in a vibe and I'll be detailed and thorough. First question is, how would I evaluate the performance of the agents on each ticket and why? I think the agents did well. They're is a little bit of duplication of effort, so I'd like to fine-tune that. Second question is, for each ticket, how did actual compare to the expected plan you wrote earlier? I think it was good, to kind of work through it and process. And double check everything is working and then fine tune some of the issues I was finding. Question number 3, how or what would have been simpler as one agent with tools and why? I think what I'm noticing is maybe there are too many checkpoints. So I'm wondering if we could instead of using 6 delegations, we still need to do 4. So instead of having accounting and customer service each double check with inventory, just have accounting check with inventory. Also, we want to make sure that the boss, when he sends accounting task, itself, instead of facilities handing it off. I think instead of the boss handing it off to accounting, facilities can do that, and that also helps with the operation. I think that would be helpful. And then the next question, which I guess would be question 4 of problem 10, for my reflection, is describe 3 new problems campus customs might face that this agent team could solve with the tools you built. I think this is going to be so great for campus customs to quickly backfill any out-of-stock orders, keep their inventory up to date, make sure we have our books in line so understanding what money is going out, what money is coming in. I also think it's going to be very helpful for the boss to have some transparency into the operations and understanding where they need to step in or step back or fine-tune the operations engine. Making sure there's no duplication of efforts. Then question 5 of problem 10 for me to reflect on is, describe 3 new problems campus custom might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them. I believe when customers have questions, they need some sort of chat box or some place where they can talk to them. On the website we built a while back, there is a chat box. I think that can be improved, but I wonder if there's a way to connect to that so that as customers are asking in real time, they can also get the information from our inventory or facilities or customer service . So that would be cool. Another problem could be that when we know something's not coming back in stock, a way to flag that and make sure we communicate that. To the customer. And I'm sure that the customer service agent would do that, but the customer service agent needs to make sure they have the right information. Another new problem that could come up is there could be more questions around color or style . And so thinking about how we also test for that, I'm assuming it would be the same as size, but I want to make sure we think that through as well. So for example, if someone really wants a size small and the color blue instead of the heather gray, would it be possible for us to say, okay, well, we don't have the size small in a blue, but we do have the size small in heather gray. Would you want that instead? So continuing the possibility of a sale that would be really great. If there's ever like an overdraft, I think that's also a problem. If we how do we know when our we have our cash is too low, and when do we flag that? When do we need to make sure we look at those finances and what kind of message comes to the boss or to whomever needs to communicate that effectively to be able to respond effectively? And keep operations moving smoothly.

**Follow-up:**
> I've answered the reflection questions. I want you to then tie every answer to this app and the three tickets you ran. Use the ticket tabs in the cache tab on the same page as your evidence.

> So for question three, I think for any sort of sizing or inventory questions, we actually could just have the inventory agent handle that on their own as a single agent. Maybe there's an easy way to just see what's in facilities. And then for question five, I would need a tool or agent that could see if there would be any reorders of an item or if an item has been canceled or we know will not be in stock. So either I think a tool connected to inventory would help.

> That's definitely a tools . So I think we should add tools that also let us know about colors. And we should also see if there's not a t-shirt size version of that. Is there something similar that if we didn't have the item or we weren't going to get it in stock, could there be a tool that showed similar items that the customer may be interested based on their original choice? That they could purchase. And that is in stock.

> low-cache problem I would like there to be a tool that flags after less than a $1,000 if we need to re-up our account so that we can pay our bills. I'd like there to be a tool that immediately flags that for the boss. So they can act quickly.

**What was lacking after the first:** My answers gave my opinions but didn't point to specific tickets or numbers, and question 3 didn't say what one agent could do alone, nor did question 5 name the tools I'd need. So I asked for each answer to be tied to tickets 101, 102 and 103 and the Cash tab, then added the single-agent idea, the inventory reorder tool, and the color and similar-items tools, and a low-cash alert to the Boss myself.

---
