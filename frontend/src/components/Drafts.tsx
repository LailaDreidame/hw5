import type { Draft } from '../api'

export function Drafts({ drafts, ticketId }: { drafts: Draft[]; ticketId: number | null }) {
  const mine = ticketId == null ? drafts : drafts.filter(d => d.ticket_id === ticketId)
  return (
    <section className="panel drafts">
      <div className="panel-head">
        <h2>Drafts on the board</h2>
        <span className="muted">{ticketId ? `ticket #${ticketId}` : 'all tickets'}</span>
      </div>
      {mine.length === 0 && <p className="empty-note">No customer drafts yet. Customer Service writes them; nobody ever hits send.</p>}
      {mine.map(d => (
        <article key={d.id} className="postcard">
          <span className="postmark">Draft · not sent</span>
          <div className="pc-to">To <b>{d.to_name}</b></div>
          <div className="pc-subject">{d.subject}</div>
          <p className="pc-body">{d.body}</p>
          <div className="pc-foot">written by {d.created_by.replace('_', ' ')} · {d.created_at}</div>
        </article>
      ))}
    </section>
  )
}
