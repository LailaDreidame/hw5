import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_BASE, type AgentEvent, type Approval, type Cash, type Draft, type Run, type Ticket } from './api'
import { liveStates, money, TYPE_LABEL } from './team'
import { TicketQueue } from './components/TicketQueue'
import { AgentFloor } from './components/AgentFloor'
import { Transcript } from './components/Transcript'
import { RunReport } from './components/RunReport'
import { Till } from './components/Till'
import { ApprovalInbox } from './components/ApprovalInbox'
import { Drafts } from './components/Drafts'

type Toast = { id: number; text: string; tone: 'good' | 'bad' | 'info' }

const STATUS_WORDS: Record<string, string> = {
  open: 'Open — nobody has worked it yet',
  in_progress: 'In progress',
  waiting_approval: 'Waiting for your signature',
  resolved: 'Resolved',
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [model, setModel] = useState('')
  const [online, setOnline] = useState(true)
  const [selected, setSelected] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const [approver, setApprover] = useState(() => localStorage.getItem('cc-approver') ?? 'Laila')
  const [toasts, setToasts] = useState<Toast[]>([])
  const since = useRef(0)
  const inFlight = useRef(false)

  useEffect(() => { localStorage.setItem('cc-approver', approver) }, [approver])

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, text, tone }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000)
  }, [])

  const refresh = useCallback(async () => {
    if (inFlight.current) return
    inFlight.current = true
    try {
      const [h, t, c, a, d, r, ev] = await Promise.all([
        api.health(), api.tickets(), api.cash(), api.approvals(), api.drafts(), api.runs(), api.events(since.current),
      ])
      setModel(h.model)
      setTickets(t.tickets)
      setCash(c)
      setApprovals(a.approvals)
      setDrafts(d.drafts)
      setRuns(r)
      if (ev.next_since < since.current) {           // audit file was replaced: reload everything
        since.current = 0
        setEvents([])
      } else {
        if (ev.events.length) setEvents(prev => [...prev, ...ev.events])
        since.current = ev.next_since
      }
      setOnline(true)
    } catch {
      setOnline(false)
    } finally {
      inFlight.current = false
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 1500)
    return () => clearInterval(id)
  }, [refresh])

  // Pick the first open ticket once the board loads.
  useEffect(() => {
    if (selected == null && tickets.length) setSelected((tickets.find(t => !t.resolved) ?? tickets[0]).id)
  }, [tickets, selected])

  const activeRun = runs.find(r => r.status === 'running' || r.status === 'starting') ?? null
  const runningTicket = activeRun?.ticket_id ?? null
  const ticket = tickets.find(t => t.id === selected) ?? null

  // The selected ticket's most recent team run.
  const runEvents = useMemo(() => {
    const starts = events.filter(e => e.event === 'run_start' && e.ticket_id === selected)
    const runId = starts.length ? starts[starts.length - 1].run_id : null
    return runId ? events.filter(e => e.run_id === runId) : []
  }, [events, selected])

  const isRunningHere = runningTicket != null && runningTicket === selected
  const live = useMemo(() => liveStates(runEvents, isRunningHere), [runEvents, isRunningHere])

  const pendingByTicket = useMemo(() => {
    const m: Record<number, number> = {}
    approvals.filter(a => a.status === 'pending' && a.ticket_id != null).forEach(a => { m[a.ticket_id!] = (m[a.ticket_id!] ?? 0) + 1 })
    return m
  }, [approvals])

  const elapsed = useElapsed(activeRun?.started_at)

  async function startRun() {
    if (!ticket) return
    setStarting(true)
    try {
      await api.runTicket(ticket.id)
      toast(`Ticket #${ticket.id} handed to the Boss. Watch the floor.`, 'info')
      await refresh()
    } catch (e) {
      toast((e as Error).message, 'bad')
    } finally {
      setStarting(false)
    }
  }

  async function approve(a: Approval) {
    try {
      const r = await api.approve(a.id, approver.trim())
      toast(`Signed. Paid ${money(r.amount)} — the till now holds ${money(r.new_balance)}.`, 'good')
      if (r.ticket_resolved) toast(`Ticket #${a.ticket_id} is resolved — nothing left to sign.`, 'good')
    } catch (e) {
      toast(`Not paid: ${(e as Error).message}`, 'bad')
    }
    await refresh()
  }

  async function reject(a: Approval) {
    const reason = window.prompt(`Why reject ${money(a.amount)}?`, 'Not now — hold this payment.')
    if (!reason) return
    try {
      await api.reject(a.id, approver.trim() || 'Desk', reason)
      toast(`Rejected request ${a.id}. No money moved.`, 'info')
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
    await refresh()
  }

  async function resolveTicket() {
    if (!ticket) return
    try {
      await api.resolve(ticket.id, approver.trim() || 'Desk')
      toast(`Ticket #${ticket.id} marked resolved.`, 'good')
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
    await refresh()
  }

  async function reset() {
    if (!window.confirm('Reset the shop to its original data? Approvals, drafts and payments go away; the audit trail stays.')) return
    try {
      await api.reset()
      toast('Shop reset to the original data. Fresh start.', 'info')
    } catch (e) {
      toast((e as Error).message, 'bad')
    }
    await refresh()
  }

  const pendingHere = ticket ? pendingByTicket[ticket.id] ?? 0 : 0
  const canRun = !!ticket && !ticket.resolved && runningTicket == null && !starting
  const shopDay = cash?.shop_today
    ? new Date(cash.shop_today + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
    : '—'

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">CC</span>
          <div>
            <h1>Campus Customs</h1>
            <p>Operations desk · Chapel Street, New Haven</p>
          </div>
        </div>
        <div className="topbar-mid">
          <span className="day"><small>Shop day</small>{shopDay}</span>
          {activeRun
            ? <span className="live-banner"><i />Team on ticket #{activeRun.ticket_id} · {elapsed}</span>
            : <span className="calm-banner">The floor is quiet</span>}
        </div>
        <div className="topbar-right">
          <span className="model-chip" title={`Backend ${API_BASE}`}>
            <i className={online ? 'ok' : 'down'} />{online ? (model || 'connecting…') : 'backend offline'} · Portkey
          </span>
          <button className="btn ghost light" onClick={reset} disabled={runningTicket != null}>Reset shop</button>
        </div>
      </header>

      {!online && (
        <div className="offline">Can't reach the backend at {API_BASE}. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.</div>
      )}

      <main className="grid">
        <TicketQueue tickets={tickets} selectedId={selected} runningTicket={runningTicket}
                     pendingByTicket={pendingByTicket} onSelect={setSelected} />

        <section className="center">
          {ticket && (
            <div className={`ticket-hero type-${ticket.type}`}>
              <div className="hero-left">
                <span className="hero-kicker">{TYPE_LABEL[ticket.type] ?? ticket.type} · from {ticket.requester}</span>
                <h2><span className="hero-no">#{ticket.id}</span> {ticket.subject}</h2>
                <span className={`hero-status s-${ticket.status}`}>{STATUS_WORDS[ticket.status] ?? ticket.status}
                  {pendingHere > 0 && ` · ${pendingHere} item${pendingHere > 1 ? 's' : ''} to sign`}</span>
              </div>
              <div className="hero-actions">
                {!ticket.resolved && pendingHere === 0 && runEvents.length > 0 && !isRunningHere && (
                  <button className="btn ghost" onClick={resolveTicket}>Mark resolved</button>
                )}
                <button className="btn primary" disabled={!canRun} onClick={startRun}>
                  {isRunningHere ? 'Team is working…' : starting ? 'Handing over…'
                    : ticket.resolved ? 'Resolved ✓' : runningTicket != null ? `Busy on #${runningTicket}` : 'Send to the team'}
                </button>
              </div>
            </div>
          )}

          <div className="section-title"><h3>The floor</h3><span className="muted">who's doing what, live</span></div>
          <AgentFloor live={live} running={isRunningHere} />

          <div className="split">
            <div className="col">
              <div className="section-title"><h3>Transcript</h3><span className="muted">every agent step, as it happens</span></div>
              <Transcript events={runEvents} running={isRunningHere} />
            </div>
            <div className="col">
              <RunReport events={runEvents} />
              {!runEvents.some(e => e.event === 'run_end') && (
                <div className="report placeholder">
                  <h3>Run report</h3>
                  <p className="muted">{isRunningHere ? 'Writing itself as the team finishes…' : 'Appears here when a run on this ticket finishes: the Boss’s call and what each agent did.'}</p>
                </div>
              )}
            </div>
          </div>
        </section>

        <div className="rail">
          <Till cash={cash} />
          <ApprovalInbox approvals={approvals} approver={approver} setApprover={setApprover}
                         onApprove={approve} onReject={reject} />
          <Drafts drafts={drafts} ticketId={selected} />
        </div>
      </main>

      <div className="toasts">
        {toasts.map(t => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  )
}

function useElapsed(startedAt?: string) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!startedAt) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [startedAt])
  if (!startedAt) return ''
  const s = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}
