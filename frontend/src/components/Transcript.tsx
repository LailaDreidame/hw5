import { useEffect, useRef, type CSSProperties } from 'react'
import type { AgentEvent } from '../api'
import { AgentIcon, metaFor, verb } from '../team'

/** One chip per tool, with a count when the model called it several times in one step. */
function toolCounts(tools: string[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const t of tools) if (t !== 'ask_agent') counts.set(t, (counts.get(t) ?? 0) + 1)
  return [...counts]
}

function line(e: AgentEvent): { text: string; kind: string } | null {
  if (e.event === 'run_start') return { text: 'Ticket handed to the team.', kind: 'system' }
  if (e.event === 'run_end') return { text: e.said ?? 'Run finished.', kind: 'system' }
  if (e.event === 'delegation') return { text: e.said ?? '', kind: 'handoff' }
  if (e.event === 'delegation_refused') return { text: `Hand-off refused — ${e.said ?? ''}`, kind: 'warn' }
  if (e.step === 'task_received') return e.depth ? null : { text: e.said ?? '', kind: 'task' }
  if (e.step === 'model_response') {
    if (e.tools.length) {
      const calls = toolCounts(e.tools)
      return calls.length ? { text: calls.map(([t, n]) => verb(t) + (n > 1 ? ` (${n}×)` : '')).join(' · '), kind: 'tool' } : null
    }
    return e.said ? { text: e.said, kind: 'say' } : null
  }
  if (e.step === 'model_request' && e.tool_results.length) {
    const rs = e.tool_results.filter(r => r.tool !== 'ask_agent')
    return rs.length ? { text: rs.map(r => `${r.tool} → ${r.result}`).join('\n'), kind: 'result' } : null
  }
  if (e.step === 'end') return { text: e.said ?? 'Done.', kind: 'final' }
  return null
}

export function Transcript({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  // Follow the newest step inside the transcript box only (never scroll the whole page).
  useEffect(() => {
    const el = box.current
    if (running && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, running])

  const rows = events.map(e => ({ e, l: line(e) })).filter(r => r.l)
  if (!rows.length) {
    return <div className="transcript empty">Nothing yet. Pick a ticket and send it to the team — every step shows up here.</div>
  }
  return (
    <div className="transcript" ref={box}>
      {rows.map(({ e, l }) => {
        const m = metaFor(e.agent)
        const time = e.time ? new Date(e.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''
        return (
          <div
            key={e.index}
            className={`tx tx-${l!.kind}`}
            style={{ '--agent': m.color, '--agent-tint': m.tint, '--depth': e.depth ?? 0 } as CSSProperties}
          >
            <span className="tx-avatar"><AgentIcon agent={e.agent} size={15} /></span>
            <div className="tx-main">
              <div className="tx-who">
                <b>{m.name}</b>
                {l!.kind === 'handoff' && <span className="handoff-to">→ {metaFor(e.to_agent).name}</span>}
                {toolCounts(e.tools).map(([t, n]) => <code key={t}>{t}{n > 1 ? ` ×${n}` : ''}</code>)}
                <time>{time}</time>
              </div>
              <div className="tx-text">{l!.text}</div>
            </div>
          </div>
        )
      })}
      {running && <div className="tx tx-pending"><span className="typing"><i /><i /><i /></span> the team is working…</div>}
    </div>
  )
}
