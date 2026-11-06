import type { CSSProperties } from 'react'
import { AGENTS, AgentIcon, type AgentKey, type AgentLive } from '../team'

interface Props {
  live: Record<AgentKey, AgentLive>
  running: boolean
}

const STATE_LABEL = { idle: 'At desk', working: 'Working', done: 'Done', not_called: 'Not called' } as const

export function AgentFloor({ live, running }: Props) {
  return (
    <div className="floor">
      {AGENTS.map(a => {
        const s = live[a.key]
        return (
          <div
            key={a.key}
            className={`desk desk-${s.state}`}
            style={{ '--agent': a.color, '--agent-tint': a.tint } as CSSProperties}
          >
            <div className="desk-head">
              <span className="avatar"><AgentIcon agent={a.key} /></span>
              <span className="desk-id">
                <b>{a.name}</b>
                <small>{a.title}</small>
              </span>
            </div>
            <div className="desk-state">
              {s.state === 'working' && <span className="typing"><i /><i /><i /></span>}
              {STATE_LABEL[s.state]}
            </div>
            <div className="bubble">
              {s.line
                ? s.line
                : s.state === 'not_called'
                  ? 'Not needed on this ticket.'
                  : running ? 'Waiting to be asked…' : 'Ready.'}
            </div>
            {s.tools.length > 0 && (
              <div className="desk-tools">
                {s.tools.map(t => <code key={t}>{t}</code>)}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
