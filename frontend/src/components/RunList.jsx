import { useEffect, useMemo, useState } from 'react'
import { fetchRuns } from '../api'

function Badge({ status }) {
  return <span className={`badge ${status}`}><span className="bdot" />{status.replace('_',' ')}</span>
}
function SkeletonCard() {
  return (
    <div className="card static" style={{ display:'flex', flexDirection:'column', gap:'0.6rem' }}>
      <div className="skeleton" style={{ height:18, width:'40%' }} />
      <div className="skeleton" style={{ height:14, width:'85%' }} />
      <div className="skeleton" style={{ height:12, width:'55%' }} />
    </div>
  )
}

export default function RunList({ onSelect, onNew }) {
  const [runs, setRuns]       = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [q, setQ]             = useState('')
  const [filter, setFilter]   = useState('all')

  useEffect(() => {
    fetchRuns().then(setRuns).catch(e=>setError(e.message)).finally(()=>setLoading(false))
  }, [])

  const filtered = useMemo(()=>{
    return runs.filter(r=>{
      if (filter!=='all' && r.status!==filter) return false
      if (q && !r.goal.toLowerCase().includes(q.toLowerCase())) return false
      return true
    })
  }, [runs,q,filter])

  const counts = useMemo(()=>{
    const m={}; for(const r of runs) m[r.status]=(m[r.status]||0)+1; return m
  },[runs])

  if (loading) return (
    <div>
      <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem' }}>
        <div><div className="page-title">Runs</div><div className="page-subtitle">Loading…</div></div>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem', marginTop:'1rem' }}>
        <SkeletonCard/><SkeletonCard/><SkeletonCard/>
      </div>
    </div>
  )

  return (
    <div>
      <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'0.6rem' }}>
            <div className="page-title">Runs</div>
            <span style={{
              background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:999,
              padding:'0.18rem 0.55rem', fontSize:'0.70rem', color:'var(--text2)', fontFamily:'JetBrains Mono, monospace', fontWeight:700,
            }}>{runs.length} total</span>
          </div>
          <div className="page-subtitle">Multi-agent goals — planned, executed, and verified</div>
        </div>
        <button className="btn btn-primary" onClick={onNew}>＋ New Run</button>
      </div>

      {/* Toolbar */}
      <div style={{
        display:'flex', gap:'0.5rem', alignItems:'center', flexWrap:'wrap',
        background:'var(--surface)', border:'1px solid var(--border)', borderRadius:12,
        padding:'0.55rem', marginBottom:'1rem',
      }}>
        <div style={{ position:'relative', flex:1, minWidth:180 }}>
          <span style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text3)', fontSize:'0.82rem' }}>⌕</span>
          <input
            value={q} onChange={e=>setQ(e.target.value)} placeholder="Search goals…"
            style={{
              width:'100%', background:'var(--surface2)', border:'1px solid var(--border2)', borderRadius:9,
              color:'var(--text)', padding:'0.52rem 0.8rem 0.52rem 1.7rem', fontSize:'0.84rem', fontFamily:'Inter, sans-serif',
            }}
          />
        </div>
        <div style={{ display:'flex', gap:'0.35rem', flexWrap:'wrap' }}>
          {['all','completed','running','awaiting_approval','failed'].map(s=>(
            <button
              key={s}
              onClick={()=>setFilter(s)}
              style={{
                padding:'0.38rem 0.65rem', borderRadius:999, fontSize:'0.72rem', fontWeight:650, cursor:'pointer',
                fontFamily:'JetBrains Mono, monospace', textTransform:'uppercase', letterSpacing:'0.04em',
                background: filter===s ? 'var(--accent)' : 'var(--surface2)',
                color: filter===s ? '#fff' : 'var(--text2)',
                border: `1px solid ${filter===s ? 'rgba(124,124,255,0.30)' : 'var(--border2)'}`,
              }}
            >
              {s==='all'?'All':s.replace('_',' ')} {s!=='all' && (counts[s]||0) ? `· ${counts[s]}` : ''}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error" style={{ marginBottom:'0.75rem' }}>{error}</div>}

      {!filtered.length && !error && (
        <div className="empty" style={{
          background:'linear-gradient(180deg, rgba(255,255,255,0.015), transparent), var(--surface)',
          border:'1px solid var(--border)', borderRadius:14, padding:'2.2rem 1rem',
        }}>
          <div style={{
            width:52, height:52, borderRadius:14, margin:'0 auto 0.8rem',
            display:'grid', placeItems:'center',
            background:'radial-gradient(120% 120% at 30% 20%, rgba(124,124,255,0.18), rgba(124,124,255,0.04))',
            border:'1px solid rgba(124,124,255,0.14)', color:'var(--accent)', fontSize:'1.1rem',
          }}>▶</div>
          <div className="empty-text" style={{ color:'var(--text)', fontWeight:600 }}>No runs match filters</div>
          <div style={{ fontSize:'0.78rem', color:'var(--text3)', marginTop:'0.25rem' }}>Try clearing filters or create a new run</div>
          <button className="btn btn-ghost" style={{ marginTop:'0.9rem' }} onClick={onNew}>＋ Create run</button>
        </div>
      )}

      {filtered.map(r=>(
        <div key={r.id} className="card" onClick={()=>onSelect(r.id)} style={{ position:'relative', overflow:'hidden' }}>
          <div style={{
            position:'absolute', left:0, top:0, bottom:0, width:3,
            background: r.status==='completed' ? 'var(--green)' : r.status==='failed' ? 'var(--red)' : r.status==='awaiting_approval' ? 'var(--amber)' : 'var(--accent)',
            opacity:0.9,
          }} />
          <div className="run-header">
            <Badge status={r.status} />
            {r.confidence!=null && (
              <span className="muted" style={{ display:'inline-flex', alignItems:'center', gap:'0.3rem' }}>
                conf <strong style={{ color: r.confidence>=0.7 ? 'var(--green)' : 'var(--amber)', fontFamily:'JetBrains Mono, monospace' }}>{r.confidence.toFixed(2)}</strong>
              </span>
            )}
            <span className="spacer" />
            <span className="mono" style={{ fontSize:'0.68rem', color:'var(--text3)', background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:6, padding:'0.1rem 0.4rem' }}>{r.id.slice(0,8)}</span>
          </div>
          <div className="run-goal">{r.goal}</div>
          <div className="run-meta">
            <span>{r.attempts} attempt{r.attempts!==1?'s':''}</span>
            <span style={{ opacity:0.5 }}>·</span>
            {r.created_at && <span>{new Date(r.created_at).toLocaleString()}</span>}
            <span style={{ marginLeft:'auto', color:'var(--accent)', fontWeight:600 }}>View →</span>
          </div>
        </div>
      ))}
    </div>
  )
}
