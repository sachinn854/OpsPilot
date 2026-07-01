import { useEffect, useRef, useState } from 'react'
import { BASE, getToken } from '../api'

const NODE_META = {
  run_created:  { icon: '⊕', label: 'Run created',       cls: 'tl-created'   },
  security:     { icon: '⊘', label: 'Security check',    cls: 'tl-security'  },
  planner:      { icon: '⊕', label: 'Planner',           cls: 'tl-planner'   },
  research:     { icon: '⊙', label: 'Research',          cls: 'tl-research'  },
  execution:    { icon: '▶', label: 'Execution',         cls: 'tl-execution' },
  critic:       { icon: '◈', label: 'Critic',            cls: 'tl-critic'    },
  reporting:    { icon: '◉', label: 'Report',            cls: 'tl-reporting' },
  hitl:         { icon: '◎', label: 'Awaiting approval', cls: 'tl-hitl'      },
  run_complete: { icon: '✓', label: 'Completed',         cls: 'tl-done'      },
  run_paused:   { icon: '◎', label: 'Needs approval',    cls: 'tl-hitl'      },
  run_failed:   { icon: '✕', label: 'Failed',            cls: 'tl-failed'    },
}

const SUGGESTIONS = [
  'List all available tools and summarize capabilities',
  'List closed PRs for sachinn854/CortexTutor',
  'Restart the production web server service',
]

export default function NewRun({ onDone, onBack }) {
  const [goal, setGoal]       = useState('')
  const [running, setRunning] = useState(false)
  const [events, setEvents]   = useState([])
  const [error, setError]     = useState('')
  const abortRef              = useRef(null)

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!goal.trim() || running) return
    setRunning(true); setEvents([]); setError('')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${BASE}/runs/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-User-Role': 'operator', 'Authorization': `Bearer ${getToken()}` },
        body: JSON.stringify({ goal: goal.trim() }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(j.detail || 'Request failed')
      }

      const reader = res.body.getReader()
      const dec    = new TextDecoder()
      let buf      = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n'); buf = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          try {
            const p = JSON.parse(line.slice(5).trim())
            setEvents(prev => [...prev, p])
            if (p.event === 'run_complete' || p.event === 'run_paused') {
              setTimeout(() => onDone(p.run_id), 600)
              return
            }
            if (p.event === 'run_failed') { setError(p.error || 'Run failed'); return }
          } catch { /* skip malformed */ }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      abortRef.current = null
      setRunning(false)
    }
  }

  return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back to runs</button>

      <div className="page-header">
        <div className="page-title">New Run</div>
        <div className="page-subtitle">Describe a goal — the copilot plans and executes it</div>
      </div>

      {/* When to use Runs guide */}
      <div style={{
        maxWidth: 600,
        marginBottom: '1.5rem',
        background: 'var(--surface2)',
        border: '1px solid var(--border2)',
        borderRadius: 10,
        padding: '1rem 1.2rem',
      }}>
        <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ color: 'var(--accent)' }}>⊙</span> When to use Runs vs Chat
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <div style={{ background: 'var(--surface3)', borderRadius: 8, padding: '0.75rem 0.9rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--green)', marginBottom: '0.4rem' }}>▶ Use Run when…</div>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {[
                'Goal needs multiple steps or tools',
                'You want planning + verification',
                'Action needs human approval (HITL)',
                'Cross-service workflows (GitHub → Slack → Jira)',
                'Complex research + action combined',
              ].map((t, i) => (
                <li key={i} style={{ fontSize: '0.75rem', color: 'var(--text2)', lineHeight: 1.5 }}>{t}</li>
              ))}
            </ul>
          </div>
          <div style={{ background: 'var(--surface3)', borderRadius: 8, padding: '0.75rem 0.9rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--cyan)', marginBottom: '0.4rem' }}>💬 Use Chat when…</div>
            <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {[
                'Quick single question or lookup',
                'List issues, PRs, emails, events',
                'Simple one-tool actions',
                'Conversational back-and-forth',
                'Fast response needed',
              ].map((t, i) => (
                <li key={i} style={{ fontSize: '0.75rem', color: 'var(--text2)', lineHeight: 1.5 }}>{t}</li>
              ))}
            </ul>
          </div>
        </div>
        <div style={{ marginTop: '0.75rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border)', fontSize: '0.73rem', color: 'var(--text3)', lineHeight: 1.6 }}>
          💡 Examples: <span style={{ color: 'var(--text2)' }}>"Find root cause of prod outage, create Jira ticket, notify Slack"</span> → Run &nbsp;·&nbsp; <span style={{ color: 'var(--text2)' }}>"Show my open PRs"</span> → Chat
        </div>
      </div>

      <div style={{ maxWidth: 600 }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Goal</label>
            <textarea
              rows={4}
              placeholder="e.g. Summarise open GitHub issues and check recent commits…"
              value={goal}
              onChange={e => setGoal(e.target.value)}
              disabled={running}
            />
          </div>

          {!running && !events.length && (
            <div className="suggestions">
              {SUGGESTIONS.map((s, i) => (
                <button key={i} type="button" className="suggestion" onClick={() => setGoal(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {error && <div className="error" style={{ marginBottom: '1rem' }}>{error}</div>}

          <button type="submit" className="btn btn-primary" disabled={running || !goal.trim()}>
            {running
              ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Running…</>
              : '▶  Start Run'}
          </button>
        </form>

        {events.length > 0 && (
          <div style={{ marginTop: '2rem' }}>
            <div className="section-label">Live Progress</div>
            <div className="timeline">
              {events.map((ev, i) => {
                const k    = ev.event === 'node_done' ? ev.node : ev.event
                const meta = NODE_META[k] || { icon: '·', label: k, cls: 'tl-pending' }
                const det  = ev.detail || (ev.run_id ? ev.run_id.slice(0, 16) : '') || ev.error || ''
                return (
                  <div key={i} className={`tl-item ${meta.cls}`}>
                    <div className="tl-vline" />
                    <div className="tl-icon">{meta.icon}</div>
                    <div className="tl-body">
                      <div className="tl-label">{meta.label}</div>
                      {det && <div className="tl-detail">{det}</div>}
                    </div>
                  </div>
                )
              })}
              {running && (
                <div className="tl-item tl-pending">
                  <div className="tl-icon">
                    <div className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} />
                  </div>
                  <div className="tl-body">
                    <div className="tl-label" style={{ color: 'var(--text3)' }}>Working…</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
