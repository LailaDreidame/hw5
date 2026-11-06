// Talks to the FastAPI backend from Problem 7.
export const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000'

export type TicketStatus = 'open' | 'in_progress' | 'waiting_approval' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  resolved: boolean
  created_at: string
}

export interface ToolCall {
  tool: string
  call_id: string
  args: Record<string, unknown>
}

export interface AgentEvent {
  index: number
  time: string
  run_id: string | null
  ticket_id: number | null
  agent: string | null
  depth: number | null
  event: string
  step: string | null
  said: string | null
  tools: string[]
  tool_calls: ToolCall[]
  tool_results: { tool: string; result: string }[]
  from_agent: string | null
  to_agent: string | null
  output: Record<string, unknown> | null
  model: string | null
  usage: Record<string, number> | null
}

export interface Approval {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  ticket_id: number | null
  amount: number
  account: string
  details: Record<string, unknown>
  reason: string
  requested_by: string
  requested_at: string
  status: 'pending' | 'approved' | 'rejected'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  payment_id: number | null
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  shop_today: string
  pending_approvals_total: number
  available_after_pending: number
}

export interface Draft {
  id: number
  ticket_id: number
  to_name: string
  subject: string
  body: string
  created_by: string
  created_at: string
  status: string
}

export interface Run {
  run_id: string
  ticket_id: number
  status: string
  started_at: string
  finished_at?: string
  error?: string
  result?: { status: string; error: string | null; output: Record<string, unknown> | null; usage: Record<string, number> }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : res.statusText)
  }
  return body as T
}

const post = <T,>(path: string, data?: unknown) =>
  req<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) })

export const api = {
  health: () => req<{ ok: boolean; model: string; database: string; active_run: string | null }>('/api/health'),
  tickets: () => req<{ shop_today: string; tickets: Ticket[] }>('/api/tickets'),
  events: (since: number) => req<{ next_since: number; events: AgentEvent[] }>(`/api/events?since=${since}&limit=1000`),
  approvals: () => req<{ approvals: Approval[] }>('/api/approvals?status=all'),
  cash: () => req<Cash>('/api/cash'),
  drafts: () => req<{ drafts: Draft[] }>('/api/drafts'),
  runs: () => req<Run[]>('/api/runs'),
  runTicket: (id: number) => post<Run>(`/api/tickets/${id}/run`),
  approve: (id: number, approvedBy: string) =>
    post<{ ok: boolean; amount: number; new_balance: number; ticket_resolved: unknown }>(
      `/api/approvals/${id}/approve`, { approved_by: approvedBy }),
  reject: (id: number, rejectedBy: string, reason: string) =>
    post(`/api/approvals/${id}/reject`, { rejected_by: rejectedBy, reason }),
  resolve: (ticketId: number, resolvedBy: string) =>
    post(`/api/tickets/${ticketId}/resolve`, { resolved_by: resolvedBy, note: 'Closed by a person on the desk.' }),
  reset: () => post<{ ok: boolean }>('/api/reset'),
}
