import { useEffect, useState } from 'react'
import { fetchRun } from '../api'

function AgentSteps({ plan, toolCalls }) {
  const steps = plan ? JSON.parse(plan) : []
  return (
    <div className="steps">
      {steps.length > 0 && (
        <div className="step planner">
          <div className="step-label">Planner</div>
          {steps.map((s, i) => (
            <div key={i} style={{ fontSize: '0.85rem', marginBottom: '0.25rem' }}>
              {i + 1}. [{s.kind}] {s.description}
            </div>
          ))}
        </div>
      )}

      {toolCalls && toolCalls.length > 0 && (
        <div className="step execution">
          <div className="step-label">Execution — Tool Calls ({toolCalls.length})</div>
          {toolCalls.map((tc, i) => (
            <div key={i} style={{ fontSize: '0.8rem', marginBottom: '0.35rem', padding: '0.35rem 0.5rem', background: '#1a1d27', borderRadius: 4 }}>
              <span style={{ color: '#f59e0b', fontWeight: 600 }}>{tc.tool_name}</span>
              {' '}
              <span className={tc.ok ? 'badge completed' : 'badge failed'} style={{ fontSize: '0.65rem' }}>
                {tc.ok ? 'ok' : 'err'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function RunDetail({ runId, onBack }) {
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchRun(runId)
      .then(setRun)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [runId])

  if (loading) return <p className="muted">Loading…</p>
  if (error)   return <p className="error">{error}</p>
  if (!run)    return null

  return (
    <div>
      <span className="back" onClick={onBack}>← Back to runs</span>
      <div className="row" style={{ marginBottom: '1rem' }}>
        <h1 style={{ marginBottom: 0 }}>Run</h1>
        <span className={`badge ${run.status}`}>{run.status}</span>
        {run.confidence != null && (
          <span className="muted">confidence: {run.confidence.toFixed(2)}</span>
        )}
        <span className="muted">attempts: {run.attempts}</span>
      </div>

      <div className="card no-hover">
        <div className="step-label">Goal</div>
        <p style={{ fontSize: '0.9rem', marginTop: '0.35rem' }}>{run.goal}</p>
      </div>

      <h2>Agent Steps</h2>
      <AgentSteps plan={run.plan} toolCalls={run.tool_calls} />

      {run.report && (
        <>
          <h2 style={{ marginTop: '1.25rem' }}>Report</h2>
          <div className="report-block">{run.report}</div>
        </>
      )}

      {run.error && (
        <p className="error" style={{ marginTop: '1rem' }}>Error: {run.error}</p>
      )}
    </div>
  )
}
