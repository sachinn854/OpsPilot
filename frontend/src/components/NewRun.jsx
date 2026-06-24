import { useState } from 'react'

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

export default function NewRun({ onDone }) {
  const [goal, setGoal]       = useState('')
  const [running, setRunning] = useState(false)
  const [events, setEvents]   = useState([])
  const [error, setError]     = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!goal.trim() || running) return
    setRunning(true); setEvents([]); setError('')

    try {
      const res = await fetch('/v1/runs/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-User-Role': 'operator' },
        body: JSON.stringify({ goal: goal.trim() }),
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
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">New Run</div>
        <div className="page-subtitle">Describe a goal — the copilot plans and executes it</div>
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

          {error && <div className="error" style={{ marginBottom:'1rem' }}>{error}</div>}

          <button type="submit" className="btn btn-primary" disabled={running || !goal.trim()}>
            {running
              ? <><div className="spinner" style={{ borderTopColor:'#fff' }} /> Running…</>
              : '▶  Start Run'}
          </button>
        </form>

        {events.length > 0 && (
          <div style={{ marginTop:'2rem' }}>
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
                    <div className="spinner" style={{ width:13, height:13, borderWidth:2 }} />
                  </div>
                  <div className="tl-body">
                    <div className="tl-label" style={{ color:'var(--text3)' }}>Working…</div>
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
