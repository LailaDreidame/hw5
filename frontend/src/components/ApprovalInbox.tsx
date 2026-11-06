import { useState } from 'react'
import type { Approval } from '../api'
import { metaFor, money } from '../team'

const KIND_LABEL = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' } as const

function payee(a: Approval): string {
  const d = a.details as Record<string, string | number | undefined>
  if (a.kind === 'rent') return String(d.landlord ?? 'Landlord')
  return String(d.vendor_name ?? `Vendor ${a.ref_id}`)
}

function memo(a: Approval): string {
  const d = a.details as Record<string, string | number | undefined>
  if (a.kind === 'invoice') return `Invoice ${a.ref_id}${d.description ? ` — ${d.description}` : ''}${d.days_overdue ? ` · ${d.days_overdue} days overdue` : ''}`
  if (a.kind === 'rent') return `${d.space_name ?? 'Shop space'} · due ${d.period_due ?? '?'}`
  return `${d.qty} × ${d.sku} size ${d.size} @ ${money(Number(d.unit_cost))} · arrives ${d.lead_days} days after it's paid`
}

/** A purchase order whose vendor still has an unpaid invoice can't be paid yet. */
function blockedBy(a: Approval, all: Approval[]): number[] {
  if (a.kind !== 'purchase_order') return []
  const ids = (a.details.blocked_by_open_invoices as number[] | undefined) ?? []
  return ids.filter(id => !all.some(x => x.kind === 'invoice' && x.ref_id === id && x.status === 'approved'))
}

interface Props {
  approvals: Approval[]
  approver: string
  setApprover: (s: string) => void
  onApprove: (a: Approval) => Promise<void>
  onReject: (a: Approval) => Promise<void>
}

export function ApprovalInbox({ approvals, approver, setApprover, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const pending = approvals.filter(a => a.status === 'pending')
  const decided = approvals.filter(a => a.status !== 'pending').slice().reverse()
  const act = async (a: Approval, fn: (a: Approval) => Promise<void>) => {
    setBusy(a.id)
    try { await fn(a) } finally { setBusy(null) }
  }
  return (
    <section className="panel inbox">
      <div className="panel-head">
        <h2>Needs your signature</h2>
        <span className={`count-pill ${pending.length ? 'hot' : ''}`}>{pending.length}</span>
      </div>
      <label className="signer">
        Signing as
        <input value={approver} onChange={e => setApprover(e.target.value)} placeholder="Your name" />
      </label>
      {pending.length === 0 && <p className="empty-note">Nothing to sign. Agents can only prepare payments — they land here for you.</p>}
      {pending.map(a => {
        const blocked = blockedBy(a, approvals)
        const who = metaFor(a.requested_by)
        return (
          <article key={a.id} className={`cheque ${blocked.length ? 'blocked' : ''}`}>
            <header>
              <span className="cheque-kind">{KIND_LABEL[a.kind]}</span>
              <span className="cheque-no">No. {String(a.id).padStart(4, '0')}{a.ticket_id ? ` · ticket #${a.ticket_id}` : ''}</span>
            </header>
            <div className="cheque-pay">
              <span>Pay to</span>
              <b>{payee(a)}</b>
              <strong>{money(a.amount)}</strong>
            </div>
            <p className="cheque-memo">{memo(a)}</p>
            <p className="cheque-by" style={{ color: who.color }}>Prepared by {who.name}: “{a.reason}”</p>
            {blocked.length > 0 && <p className="cheque-warn">Vendor won't ship until invoice {blocked.join(', ')} is paid — sign that first.</p>}
            <div className="cheque-actions">
              <button className="btn ghost" disabled={busy === a.id} onClick={() => act(a, onReject)}>Reject</button>
              <button className="btn sign" disabled={busy === a.id || !approver.trim()} onClick={() => act(a, onApprove)}>
                {busy === a.id ? 'Signing…' : `Approve & pay ${money(a.amount)}`}
              </button>
            </div>
          </article>
        )
      })}
      {decided.length > 0 && (
        <details className="history">
          <summary>Signed & rejected ({decided.length})</summary>
          <ul>
            {decided.map(a => (
              <li key={a.id} className={a.status}>
                <span>{KIND_LABEL[a.kind]} · {payee(a)}</span>
                <span>{money(a.amount)}</span>
                <em>{a.status === 'approved' ? `paid · ${a.decided_by}` : `rejected · ${a.decided_by}`}</em>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
