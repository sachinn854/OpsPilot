import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchRun } from '../api'

const NODE_META = {
  planner:   { icon: '⊕', label: 'Planner',   cls: 'tl-planner'   },
  research:  { icon: '⊙', label: 'Research',  cls: 'tl-research'  },
  execution: { icon: '▶', label: 'Execution', cls: 'tl-execution' },
  critic:    { icon: '◈', label: 'Critic',    cls: 'tl-critic'    },
  reporting: { icon: '◉', label: 'Report',    cls: 'tl-reporting' },
  security:  { icon: '⊘', label: 'Security',  cls: 'tl-security'  },
}

function Badge({ status }) {
  return (
    <span className={`badge ${status}`}>
      <span className="bdot" />
      {status.replace('_', ' ')}
    </span>
  )
}

const POLL_INTERVALS = [2000, 4000, 8000, 15000, 30000]  // exponential backoff cap 30s
const TERMINAL = new Set(['completed', 'failed'])

export default function RunDetail({ runId, onBack }) {
  const [run, setRun]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const pollRef               = useRef(null)
  const attemptRef            = useRef(0)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const r = await fetchRun(runId)
        if (cancelled) return
        setRun(r)
        setLoading(false)
        if (!TERMINAL.has(r.status)) {
          const delay = POLL_INTERVALS[Math.min(attemptRef.current, POLL_INTERVALS.length - 1)]
          attemptRef.current += 1
          pollRef.current = setTimeout(poll, delay)
        }
      } catch (e) {
        if (!cancelled) setError(e.message)
        setLoading(false)
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(pollRef.current)
    }
  }, [runId])

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', color:'var(--text3)', marginTop:'3rem' }}>
      <div className="spinner" /> Loading run…
    </div>
  )
  if (error)  return <div className="error">{error}</div>
  if (!run)   return null

  const planSteps = (() => { try { return JSON.parse(run.plan || '[]') } catch { return [] } })()

  return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back to runs</button>

      <div className="page-header">
        <div className="row" style={{ marginBottom:'0.5rem' }}>
          <Badge status={run.status} />
          <span className="mono muted" style={{ fontSize:'0.7rem' }}>{run.id}</span>
        </div>
        <div className="page-title" style={{ fontSize:'1.1rem', lineHeight:1.45 }}>{run.goal}</div>
      </div>

      <div className="stats-row">
        {run.confidence != null && (
          <div className="stat-chip">
            Confidence&nbsp;
            <strong style={{ color: run.confidence >= 0.7 ? 'var(--green)' : 'var(--yellow)' }}>
              {run.confidence.toFixed(2)}
            </strong>
          </div>
        )}
        <div className="stat-chip">Attempts <strong>{run.attempts}</strong></div>
        {planSteps.length > 0 && <div className="stat-chip">Steps <strong>{planSteps.length}</strong></div>}
        {run.tool_calls?.length > 0 && <div className="stat-chip">Tool calls <strong>{run.tool_calls.length}</strong></div>}
      </div>

      {planSteps.length > 0 && (
        <>
          <div className="section-label">Pipeline</div>
          <div className="timeline">
            {Object.entries(NODE_META).map(([key, meta]) => {
              if (key === 'security')  return null
              if (key === 'planner'   && !planSteps.length) return null
              if (key === 'execution' && !run.tool_calls?.length) return null
              if (key === 'critic'    && run.confidence == null) return null
              if (key === 'reporting' && !run.report) return null

              return (
                <div key={key} className={`tl-item ${meta.cls}`}>
                  <div className="tl-vline" />
                  <div className="tl-icon">{meta.icon}</div>
                  <div className="tl-body">
                    <div className="tl-label">{meta.label}</div>

                    {key === 'planner' && (
                      <div className="plan-steps">
                        {planSteps.map((s, i) => (
                          <div key={i} className="plan-step">
                            <span className="plan-num">{i + 1}</span>
                            <span className={`plan-kind ${s.kind}`}>{s.kind}</span>
                            <span>{s.description}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {key === 'execution' && run.tool_calls?.map((tc, i) => (
                      <div key={i} className="tool-call">
                        <span className={`tc-status ${tc.ok ? 'ok' : 'err'}`}>
                          {tc.ok ? '✓' : '✗'}
                        </span>
                        <span className="tc-name">{tc.tool_name}</span>
                      </div>
                    ))}

                    {key === 'critic' && run.confidence != null && (
                      <div className="tl-detail">
                        Score&nbsp;
                        <strong style={{ color: run.confidence >= 0.7 ? 'var(--green)' : 'var(--yellow)' }}>
                          {run.confidence.toFixed(2)}
                        </strong>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {run.report && (
        <>
          <div className="section-label">Report</div>
          <div className="report-block md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{run.report}</ReactMarkdown>
          </div>
        </>
      )}

      {run.error && (
        <div className="error" style={{ marginTop:'1rem' }}>{run.error}</div>
      )}
    </div>
  )
}
