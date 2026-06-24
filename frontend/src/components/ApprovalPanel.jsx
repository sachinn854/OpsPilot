import { useEffect, useState } from 'react'
import { fetchApprovals, decide } from '../api'

export default function ApprovalPanel() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [busy, setBusy]           = useState(null)

  function load() {
    setLoading(true)
    fetchApprovals()
      .then(setApprovals)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  async function handleDecide(id, approved, action) {
    const verb = approved ? 'approve' : 'reject'
    if (!window.confirm(`Are you sure you want to ${verb} "${action}"?`)) return
    setBusy(id)
    try { await decide(id, approved); load() }
    catch (e) { setError(e.message) }
    finally { setBusy(null) }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Approvals</div>
        <div className="page-subtitle">Sensitive actions awaiting human review</div>
      </div>

      {loading && (
        <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', color:'var(--text3)' }}>
          <div className="spinner" /> Loading…
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {!loading && !approvals.length && (
        <div className="empty">
          <div className="empty-icon">◎</div>
          <div className="empty-text">No pending approvals</div>
        </div>
      )}

      {approvals.map(a => (
        <div key={a.id} className="approval-card">
          <div className="row" style={{ marginBottom:'0.5rem' }}>
            <span className={`badge ${a.status}`}>
              <span className="bdot" />{a.status}
            </span>
          </div>
          <div className="approval-action">{a.action}</div>
          {a.reason && <div className="approval-reason">{a.reason}</div>}
          <div className="approval-id">run · {a.run_id}</div>

          {a.status === 'pending' && (
            <div className="approval-btns">
              <button
                className="btn btn-success"
                disabled={busy === a.id}
                onClick={() => handleDecide(a.id, true, a.action)}
              >
                {busy === a.id
                  ? <><div className="spinner" style={{ borderTopColor:'#fff', width:13, height:13 }} /> Working…</>
                  : '✓ Approve'}
              </button>
              <button className="btn btn-danger" disabled={busy === a.id} onClick={() => handleDecide(a.id, false, a.action)}>
                ✕ Reject
              </button>
              <button className="btn btn-ghost" onClick={load}>↻ Refresh</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
