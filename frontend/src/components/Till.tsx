import { useEffect, useRef, useState } from 'react'
import type { Cash } from '../api'
import { money } from '../team'

/** Smoothly count from the old balance to the new one (the first real value just appears). */
function useTween(target: number | null, ms = 1100) {
  const [value, setValue] = useState<number | null>(target)
  const from = useRef<number | null>(target)
  useEffect(() => {
    if (target == null) return
    if (from.current == null) { from.current = target; setValue(target); return }
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min((now - start) / ms, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      setValue(a + (target - a) * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    // Browsers pause animation frames in background tabs; always land on the real number.
    const settle = setTimeout(() => { setValue(target); from.current = target }, ms + 100)
    return () => { cancelAnimationFrame(raf); clearTimeout(settle); from.current = target }
  }, [target, ms])
  return value
}

export function Till({ cash }: { cash: Cash | null }) {
  const balance = cash?.balance ?? 0
  const shown = useTween(cash ? cash.balance : null)
  const prev = useRef<number | null>(null)
  const [delta, setDelta] = useState<{ amount: number; key: number } | null>(null)

  useEffect(() => {
    if (cash == null) return
    if (prev.current != null && cash.balance !== prev.current) {
      setDelta({ amount: cash.balance - prev.current, key: Date.now() })
    }
    prev.current = cash.balance
  }, [cash])

  const pending = cash?.pending_approvals_total ?? 0
  const after = cash?.available_after_pending ?? 0
  const pendPct = balance > 0 ? Math.min(pending / balance, 1) * 100 : 0

  return (
    <section className="panel till">
      <div className="panel-head">
        <h2>The till</h2>
        <span className="muted">checking · as of {cash?.as_of ?? '—'}</span>
      </div>
      <div className="balance-wrap">
        <div className={`balance ${delta ? 'bumped' : ''}`} key={`balance-${delta?.key ?? 0}`}>{shown == null ? money(null) : money(Math.round(shown * 100) / 100)}</div>
        {delta && (
          <div key={`delta-${delta.key}`} className={`delta ${delta.amount < 0 ? 'down' : 'up'}`}>
            {delta.amount < 0 ? '−' : '+'}{money(Math.abs(delta.amount))}
          </div>
        )}
      </div>
      <div className="till-bar" title="Share of cash already waiting for your signature">
        <span className="till-pending" style={{ width: `${pendPct}%` }} />
      </div>
      <dl className="till-rows">
        <div><dt>Waiting for your signature</dt><dd>{money(pending)}</dd></div>
        <div className={after < 0 ? 'neg' : ''}><dt>Left if you sign everything</dt><dd>{money(after)}</dd></div>
      </dl>
      <p className="till-note">Cash only goes out in this shop. Nothing leaves the till until a person signs.</p>
    </section>
  )
}
