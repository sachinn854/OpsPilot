import { useEffect, useState } from 'react'
import { fetchRuns } from '../api'

function Badge({ status }) {
  return (
    <span className={`badge ${status}`}>
      <span className="bdot" />
      {status.replace('_', ' ')}
    </span>
  )
}

export default function RunList({ onSelect, onNew }) {
  const [runs, setRuns]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    fetchRuns()
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text3)', marginTop: '2rem' }}>
      <div className="spinner" /> Loading runs…
    </div>
  )

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div className="page-title">Runs</div>
          <div className="page-subtitle">{runs.length} total run{runs.length !== 1 ? 's' : ''}</div>
        </div>
        <button className="btn btn-primary" onClick={onNew} style={{ marginTop: '0.15rem' }}>
          + New Run
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {!runs.length && !error && (
        <div className="empty">
          <div className="empty-icon">▷</div>
          <div className="empty-text">No runs yet — click New Run to get started</div>
        </div>
      )}

      {runs.map(r => (
        <div key={r.id} className="card" onClick={() => onSelect(r.id)}>
          <div className="run-header">
            <Badge status={r.status} />
            {r.confidence != null && (
              <span className="muted">
                conf&nbsp;
                <strong style={{ color: r.confidence >= 0.7 ? 'var(--green)' : 'var(--yellow)' }}>
                  {r.confidence.toFixed(2)}
                </strong>
              </span>
            )}
            <span className="spacer" />
            <span className="muted mono" style={{ fontSize: '0.68rem' }}>{r.id.slice(0, 8)}</span>
          </div>
          <div className="run-goal">{r.goal}</div>
          <div className="run-meta">
            <span>{r.attempts} attempt{r.attempts !== 1 ? 's' : ''}</span>
            <span>·</span>
            <span className="mono" style={{ fontSize: '0.7rem' }}>{new Date(r.created_at).toLocaleString()}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
