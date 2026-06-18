import { useEffect, useState } from 'react'
import { fetchApprovals, decide } from '../api'

export default function ApprovalPanel() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null) // approval id being decided

  function load() {
    setLoading(true)
    fetchApprovals()
      .then(setApprovals)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleDecide(id, approved) {
    setBusy(id)
    try {
      await decide(id, approved)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <p className="muted">Loading…</p>
  if (error)   return <p className="error">{error}</p>

  return (
    <div>
      <h1>Pending Approvals</h1>
      {!approvals.length && <p className="muted">No pending approvals.</p>}
      {approvals.map(a => (
        <div key={a.id} className="card no-hover">
          <div className="row">
            <span className={`badge ${a.status}`}>{a.status}</span>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{a.action}</span>
          </div>
          {a.reason && <p className="muted" style={{ marginTop: '0.4rem', fontSize: '0.85rem' }}>{a.reason}</p>}
          <p className="muted" style={{ fontSize: '0.75rem', marginTop: '0.35rem' }}>Run: {a.run_id}</p>
          {a.status === 'pending' && (
            <div className="row" style={{ marginTop: '0.75rem' }}>
              <button
                className="btn btn-success"
                disabled={busy === a.id}
                onClick={() => handleDecide(a.id, true)}
              >Approve</button>
              <button
                className="btn btn-danger"
                disabled={busy === a.id}
                onClick={() => handleDecide(a.id, false)}
              >Reject</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
