import type { Ticket } from '../api'
import { TYPE_LABEL } from '../team'

const STAMP: Record<string, { label: string; cls: string }> = {
  open: { label: 'Open', cls: 'stamp-open' },
  in_progress: { label: 'In progress', cls: 'stamp-progress' },
  waiting_approval: { label: 'Awaiting signature', cls: 'stamp-waiting' },
  resolved: { label: 'Resolved', cls: 'stamp-resolved' },
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  runningTicket: number | null
  pendingByTicket: Record<number, number>
  onSelect: (id: number) => void
}

export function TicketQueue({ tickets, selectedId, runningTicket, pendingByTicket, onSelect }: Props) {
  const open = tickets.filter(t => !t.resolved).length
  return (
    <aside className="panel queue">
      <div className="panel-head">
        <h2>Ticket queue</h2>
        <span className="count-pill">{open} open · {tickets.length - open} resolved</span>
      </div>
      <ul className="ticket-list">
        {tickets.map(t => {
          const stamp = STAMP[t.status] ?? STAMP.open
          const pending = pendingByTicket[t.id] ?? 0
          const item = t.sku ? `${t.sku} · ${t.size} × ${t.qty}` : t.lease_id ? `Lease ${t.lease_id}` : ''
          return (
            <li key={t.id}>
              <button
                className={`ticket type-${t.type} ${selectedId === t.id ? 'selected' : ''} ${t.resolved ? 'is-resolved' : ''}`}
                onClick={() => onSelect(t.id)}
              >
                <span className="ticket-band" />
                <span className="ticket-body">
                  <span className="ticket-top">
                    <span className="ticket-no">#{t.id}</span>
                    <span className="ticket-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                  </span>
                  <span className="ticket-subject">{t.subject}</span>
                  <span className="ticket-meta">{t.requester}</span>
                  {item && <span className="ticket-item">{item}</span>}
                  <span className="ticket-foot">
                    {runningTicket === t.id
                      ? <span className="live-chip"><i />Team working</span>
                      : <span className={`stamp ${stamp.cls}`}>{stamp.label}</span>}
                    {pending > 0 && <span className="sign-chip">{pending} to sign</span>}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}
