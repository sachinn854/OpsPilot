import { useEffect, useState } from 'react'
import { fetchRuns } from '../api'

export default function RunList({ onSelect }) {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchRuns()
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="muted">Loading runs…</p>
  if (error)   return <p className="error">{error}</p>
  if (!runs.length) return (
    <div>
      <h1>Runs</h1>
      <p className="muted">No runs yet. Create one from "New Run".</p>
    </div>
  )

  return (
    <div>
      <h1>Runs</h1>
      {runs.map(run => (
        <div key={run.id} className="card" onClick={() => onSelect(run.id)}>
          <div className="row">
            <span className={`badge ${run.status}`}>{run.status}</span>
            <span className="muted" style={{ fontSize: '0.75rem' }}>
              conf: {run.confidence != null ? run.confidence.toFixed(2) : '—'} &nbsp;|&nbsp; attempts: {run.attempts}
            </span>
          </div>
          <p style={{ marginTop: '0.5rem', fontSize: '0.9rem' }}>{run.goal}</p>
        </div>
      ))}
    </div>
  )
}
