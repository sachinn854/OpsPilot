import { useEffect, useState } from 'react'
import { fetchApprovals, decide } from '../api'

export default function ApprovalPanel() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [busy, setBusy]           = useState(null)

  function load(){
    setLoading(true)
    fetchApprovals().then(setApprovals).catch(e=>setError(e.message)).finally(()=>setLoading(false))
  }
  useEffect(()=>{ load() },[])

  async function handleDecide(id, approved, action){
    const verb=approved?'approve':'reject'
    if(!window.confirm(`Are you sure you want to ${verb} "${action}"?`)) return
    setBusy(id)
    try{ await decide(id, approved); load() }catch(e){ setError(e.message) }
    finally{ setBusy(null) }
  }

  return (
    <div>
      <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'0.6rem' }}>
            <div style={{ width:30, height:30, borderRadius:8, display:'grid', placeItems:'center', background:'linear-gradient(135deg, #f59e0b, #d97706)', color:'#fff', fontSize:'0.85rem' }}>◈</div>
            <div className="page-title">Approvals</div>
            {approvals.length>0 && (
              <span style={{
                background:'var(--amber-dim)', border:'1px solid var(--amber-brd)', color:'var(--amber)',
                borderRadius:999, padding:'0.16rem 0.55rem', fontSize:'0.70rem', fontWeight:700, fontFamily:'JetBrains Mono, monospace',
              }}>{approvals.filter(a=>a.status==='pending').length} pending</span>
            )}
          </div>
          <div className="page-subtitle">Sensitive actions awaiting human review — approve or reject to continue the run</div>
        </div>
        <button className="btn btn-ghost" onClick={load} style={{ padding:'0.45rem 0.8rem', fontSize:'0.78rem' }}>↻ Refresh</button>
      </div>

      {loading && (
        <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem', marginTop:'0.5rem' }}>
          <div className="skeleton" style={{ height:96 }} />
          <div className="skeleton" style={{ height:96 }} />
        </div>
      )}
      {error && <div className="error" style={{ marginBottom:'0.75rem' }}>{error}</div>}

      {!loading && !approvals.length && (
        <div className="empty" style={{
          background:'linear-gradient(180deg, rgba(255,255,255,0.015), transparent), var(--surface)',
          border:'1px solid var(--border)', borderRadius:14, padding:'2.4rem 1rem',
        }}>
          <div style={{
            width:52, height:52, borderRadius:14, margin:'0 auto 0.8rem', display:'grid', placeItems:'center',
            background:'radial-gradient(120% 120% at 30% 20%, rgba(16,185,129,0.14), rgba(16,185,129,0.02))',
            border:'1px solid rgba(16,185,129,0.14)', color:'var(--green)', fontSize:'1.15rem',
          }}>✓</div>
          <div style={{ fontWeight:650, color:'var(--text)', fontSize:'0.92rem' }}>All clear</div>
          <div className="empty-text" style={{ marginTop:'0.2rem' }}>No pending approvals — runs will appear here when they need your decision</div>
        </div>
      )}

      {approvals.map(a=>(
        <div key={a.id} className="approval-card">
          <div className="row" style={{ marginBottom:'0.45rem' }}>
            <span className={`badge ${a.status}`}><span className="bdot" />{a.status}</span>
            <span style={{ marginLeft:'auto', fontFamily:'JetBrains Mono, monospace', fontSize:'0.66rem', color:'var(--text3)', background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:6, padding:'0.1rem 0.4rem' }}>
              {new Date(a.created_at||Date.now()).toLocaleString()}
            </span>
          </div>
          <div className="approval-action">{a.action}</div>
          {a.reason && <div className="approval-reason">{a.reason}</div>}
          <div className="approval-id">run · <span style={{ color:'var(--accent)' }}>{a.run_id}</span></div>
          {a.status==='pending' && (
            <div className="approval-btns">
              <button className="btn btn-success" disabled={busy===a.id} onClick={()=>handleDecide(a.id,true,a.action)} style={{ padding:'0.52rem 1rem' }}>
                {busy===a.id ? <><span className="spinner" style={{ borderTopColor:'#fff', width:13, height:13 }} /> Working…</> : '✓ Approve'}
              </button>
              <button className="btn btn-danger" disabled={busy===a.id} onClick={()=>handleDecide(a.id,false,a.action)} style={{ padding:'0.52rem 1rem' }}>
                ✕ Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
