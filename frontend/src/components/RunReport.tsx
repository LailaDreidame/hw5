import type { CSSProperties } from 'react'
import type { AgentEvent } from '../api'
import { AgentIcon, summarize } from '../team'

interface BossOutput {
  summary?: string
  decision?: string
  approvals_waiting?: number[]
  drafts_saved?: number[]
  next_steps_for_human?: string[]
}

export function RunReport({ events }: { events: AgentEvent[] }) {
  const end = [...events].reverse().find(e => e.event === 'run_end')
  if (!end) return null
  const boss = (end.output ?? {}) as BossOutput
  const usage = end.usage ?? {}
  const rows = summarize(events)
  return (
    <section className="report">
      <div className="report-head">
        <h3>Run report</h3>
        <span className="muted">
          {usage.requests ?? 0} model calls · {(usage.total_tokens ?? 0).toLocaleString()} tokens · {rows.filter(r => r.called).length} of 5 agents
        </span>
      </div>
      {end.said && end.said !== 'Run done' && <div className="report-error">{end.said}</div>}
      {boss.decision && (
        <div className="verdict">
          <span className="verdict-label">Boss's call</span>
          <p className="verdict-summary">{boss.summary}</p>
          <p className="verdict-decision">{boss.decision}</p>
          {!!boss.next_steps_for_human?.length && (
            <ul className="next-steps">
              {boss.next_steps_for_human.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
        </div>
      )}
      <div className="report-grid">
        {rows.map(r => (
          <div
            key={r.agent.key}
            className={`report-row ${r.called ? '' : 'idle'}`}
            style={{ '--agent': r.agent.color, '--agent-tint': r.agent.tint } as CSSProperties}
          >
            <div className="report-who">
              <span className="avatar sm"><AgentIcon agent={r.agent.key} size={16} /></span>
              <b>{r.agent.name}</b>
            </div>
            {r.called ? (
              <>
                <div className="report-line">
                  {r.askedBy.length ? <>Asked by {r.askedBy.join(', ')}</> : <>Took the ticket</>}
                  {r.delegatedTo.length > 0 && <> · handed off to {r.delegatedTo.join(', ')}</>}
                  <span className="muted"> · {r.modelCalls} calls</span>
                </div>
                {r.final && <p className="report-final">{r.final}</p>}
                <div className="desk-tools">{r.tools.map(t => <code key={t}>{t}</code>)}</div>
              </>
            ) : (
              <div className="report-line muted">Not called on this ticket.</div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
