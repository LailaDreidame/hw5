import type { AgentEvent } from './api'

export type AgentKey = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface AgentMeta {
  key: AgentKey
  name: string
  title: string
  color: string
  tint: string
  voice: string // how this desk "talks" on the board
}

export const AGENTS: AgentMeta[] = [
  { key: 'boss', name: 'Boss', title: 'Reads tickets · makes the call', color: '#1f4fa3', tint: '#e6eefb', voice: 'decides' },
  { key: 'inventory', name: 'Inventory', title: 'Stock · sizes · vendors', color: '#0f766e', tint: '#e2f4f1', voice: 'counts' },
  { key: 'accounting', name: 'Accounting', title: 'Cash · bills · margins', color: '#b45309', tint: '#fbefdf', voice: 'tallies' },
  { key: 'facilities', name: 'Facilities', title: 'Lease · rent · the space', color: '#6d28d9', tint: '#efe7fd', voice: 'checks' },
  { key: 'customer_service', name: 'Customer Service', title: 'Drafts replies · never sends', color: '#be185d', tint: '#fbe6f0', voice: 'writes' },
]

export const AGENT_BY_KEY: Record<string, AgentMeta> = Object.fromEntries(AGENTS.map(a => [a.key, a]))

export const HUMAN: AgentMeta = {
  key: 'boss', name: 'You', title: 'Human on the desk', color: '#15803d', tint: '#e5f4ea', voice: 'signs',
}

export function metaFor(agent: string | null | undefined): AgentMeta {
  if (agent === 'human') return HUMAN
  return AGENT_BY_KEY[agent ?? ''] ?? { ...HUMAN, name: agent ?? 'System', color: '#64748b', tint: '#eef1f5' }
}

// What each MCP tool call looks like in plain words on the board.
export const TOOL_VERBS: Record<string, string> = {
  get_ticket: 'Reading the ticket',
  get_shop_today: "Checking today's date",
  list_tickets: 'Scanning the board',
  list_open_tickets: 'Scanning open tickets',
  check_stock: 'Counting stock on the shelf',
  check_margin: 'Running the margin math',
  list_vendors: 'Looking up vendors',
  get_invoice: 'Pulling the invoice',
  list_open_invoices: 'Reviewing unpaid bills',
  get_lease: 'Reading the lease',
  get_cash_balance: 'Checking the till',
  list_payments: 'Reviewing past payments',
  request_payment: 'Preparing a payment for your signature',
  request_purchase_order: 'Preparing a purchase order for your signature',
  list_approvals: 'Checking the approval queue',
  save_customer_draft: 'Writing a draft reply',
  list_drafts: 'Checking drafts on the board',
  update_ticket: 'Updating the ticket',
  ask_agent: 'Asking a teammate',
}

export const verb = (tool: string) => TOOL_VERBS[tool] ?? tool.replace(/_/g, ' ')

export type LiveState = 'idle' | 'working' | 'done' | 'not_called'

export interface AgentLive {
  state: LiveState
  line: string
  tools: string[]
}

/** What each agent is doing right now (or did last) in this run. */
export function liveStates(runEvents: AgentEvent[], running: boolean): Record<AgentKey, AgentLive> {
  const out = {} as Record<AgentKey, AgentLive>
  for (const a of AGENTS) {
    // run_start / run_end are bookkeeping rows logged under the Boss; they aren't anything an agent said.
    const mine = runEvents.filter(e => e.agent === a.key && e.event !== 'run_start' && e.event !== 'run_end')
    const tools = [...new Set(mine.flatMap(e => e.tools).filter(t => t !== 'ask_agent'))]
    if (mine.length === 0) {
      out[a.key] = { state: running || runEvents.length === 0 ? 'idle' : 'not_called', line: '', tools }
      continue
    }
    const last = mine[mine.length - 1]
    let line = ''
    if (last.event === 'delegation') line = `Asking ${metaFor(last.to_agent).name}: ${last.said ?? ''}`
    else if (last.event === 'delegation_refused') line = `Couldn't hand off: ${last.said ?? ''}`
    else if (last.step === 'end' || last.event === 'run_end') line = last.said ?? 'Done.'
    else if (last.step === 'task_received') line = `Got a task: ${last.said ?? ''}`
    else if (last.step === 'model_response' && last.tools.length)
      line = last.tools.map(verb).join(' · ') + '…'
    else if (last.step === 'model_request' && last.tool_results.length)
      line = `Reading results from ${last.tool_results.map(r => r.tool).join(', ')}`
    else line = last.said ?? 'Thinking…'
    // An agent can be asked more than once in a run, so only its latest step decides done vs working.
    const isDone = last.step === 'end'
    out[a.key] = { state: isDone || !running ? 'done' : 'working', line, tools }
  }
  return out
}

export interface AgentSummary {
  agent: AgentMeta
  called: boolean
  askedBy: string[]
  delegatedTo: string[]
  tools: string[]
  modelCalls: number
  tokens: number
  final: string | null
}

/** Short per-agent report of what each one did on the ticket's latest run. */
export function summarize(runEvents: AgentEvent[]): AgentSummary[] {
  return AGENTS.map(a => {
    const mine = runEvents.filter(e => e.agent === a.key)
    const end = [...mine].reverse().find(e => e.step === 'end')
    return {
      agent: a,
      called: mine.length > 0,
      askedBy: [...new Set(runEvents.filter(e => e.event === 'delegation' && e.to_agent === a.key).map(e => metaFor(e.from_agent).name))],
      delegatedTo: [...new Set(mine.filter(e => e.event === 'delegation').map(e => metaFor(e.to_agent).name))],
      tools: [...new Set(mine.flatMap(e => e.tools).filter(t => t !== 'ask_agent'))],
      modelCalls: mine.filter(e => e.step === 'model_response').length,
      tokens: mine.reduce((s, e) => s + (e.usage?.input_tokens ?? 0) + (e.usage?.output_tokens ?? 0), 0),
      final: end?.said ?? null,
    }
  })
}

export function AgentIcon({ agent, size = 22 }: { agent: string | null | undefined; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (agent) {
    case 'boss':
      return <svg {...common}><path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z" /></svg>
    case 'inventory':
      return <svg {...common}><path d="M3.5 7.5L12 3l8.5 4.5v9L12 21l-8.5-4.5z" /><path d="M3.5 7.5L12 12l8.5-4.5M12 12v9" /></svg>
    case 'accounting':
      return <svg {...common}><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></svg>
    case 'facilities':
      return <svg {...common}><path d="M4 21V9l8-5 8 5v12" /><path d="M9 21v-6h6v6M4 21h16" /></svg>
    case 'customer_service':
      return <svg {...common}><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9.5h8M8 12.5h5" /></svg>
    default:
      return <svg {...common}><path d="M5 20c1.2-3.6 4-5.5 7-5.5s5.8 1.9 7 5.5" /><circle cx="12" cy="8.5" r="3.8" /></svg>
  }
}

export const money = (n: number | undefined | null) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: n % 1 ? 2 : 0 })

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Discount request',
}
