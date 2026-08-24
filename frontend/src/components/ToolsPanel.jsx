import { useEffect, useMemo, useState } from 'react'
import { fetchMcpTools } from '../api'

const SERVER_COLORS = {
  github:'#2563eb', ops:'#ef4444', rag:'#06b6d4', slack:'#10b981',
  search:'#f59e0b', monitoring:'#7c3aed', jira:'#0052cc', linear:'#5e6ad2',
  google:'#ea4335', notion:'#ffffff', confluence:'#0052cc', pagerduty:'#06ac38', hubspot:'#ff7a59',
}
const SERVER_ICON = {
  github:'⬢', ops:'⚙', rag:'⊡', slack:'#', search:'⌕', monitoring:'◈',
  jira:'⊞', linear:'⊕', google:'⊗', notion:'◻', confluence:'⊟', pagerduty:'⚠', hubspot:'⊛',
}

export default function ToolsPanel(){
  const [tools,setTools]=useState([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [q,setQ]=useState('')
  const [onlySensitive,setOnlySensitive]=useState(false)

  useEffect(()=>{ fetchMcpTools().then(setTools).catch(e=>setError(e.message)).finally(()=>setLoading(false)) },[])

  const filtered = useMemo(()=>{
    return tools.filter(t=>{
      if(onlySensitive && !t.sensitive) return false
      if(q && !`${t.name} ${t.description} ${t.server}`.toLowerCase().includes(q.toLowerCase())) return false
      return true
    })
  },[tools,q,onlySensitive])

  const servers = [...new Set(filtered.map(t=>t.server))]

  return (
    <div>
      <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'0.6rem' }}>
            <div style={{ width:30, height:30, borderRadius:8, display:'grid', placeItems:'center', background:'linear-gradient(135deg, #7c7cff, #6366f1)', color:'#fff', fontSize:'0.82rem' }}>⊙</div>
            <div className="page-title">Tool Registry</div>
            <span style={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:999, padding:'0.16rem 0.55rem', fontSize:'0.70rem', color:'var(--text2)', fontFamily:'JetBrains Mono, monospace', fontWeight:700 }}>
              {tools.length} tools · {[...new Set(tools.map(t=>t.server))].length} servers
            </span>
          </div>
          <div className="page-subtitle">Every capability the copilot can call — grouped by MCP server</div>
        </div>
      </div>

      <div style={{
        display:'flex', gap:'0.5rem', alignItems:'center', flexWrap:'wrap',
        background:'var(--surface)', border:'1px solid var(--border)', borderRadius:12, padding:'0.55rem', marginBottom:'1rem',
      }}>
        <div style={{ position:'relative', flex:1, minWidth:180 }}>
          <span style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text3)', fontSize:'0.82rem' }}>⌕</span>
          <input
            value={q} onChange={e=>setQ(e.target.value)} placeholder="Search tools…"
            style={{ width:'100%', background:'var(--surface2)', border:'1px solid var(--border2)', borderRadius:9, color:'var(--text)', padding:'0.52rem 0.8rem 0.52rem 1.7rem', fontSize:'0.84rem', fontFamily:'Inter, sans-serif' }}
          />
        </div>
        <label style={{ display:'inline-flex', alignItems:'center', gap:'0.4rem', cursor:'pointer', fontSize:'0.78rem', color:'var(--text2)', whiteSpace:'nowrap', userSelect:'none' }}>
          <input type="checkbox" checked={onlySensitive} onChange={e=>setOnlySensitive(e.target.checked)} style={{ accentColor:'var(--amber)' }} />
          Sensitive only
        </label>
      </div>

      {loading && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(250px, 1fr))', gap:'0.55rem' }}>
          {[0,1,2,3,4,5].map(i=>(
            <div key={i} className="card static" style={{ display:'flex', flexDirection:'column', gap:'0.5rem' }}>
              <div className="skeleton" style={{ height:14, width:'55%' }} />
              <div className="skeleton" style={{ height:12, width:'90%' }} />
            </div>
          ))}
        </div>
      )}
      {error && <div className="error">{error}</div>}

      {!loading && servers.length===0 && (
        <div className="empty" style={{ background:'var(--surface)', border:'1px solid var(--border)', borderRadius:14, padding:'2rem 1rem' }}>
          <div className="empty-text">No tools match your filters</div>
        </div>
      )}

      {servers.map(server=>{
        const color=SERVER_COLORS[server]||'var(--text2)'
        const icon=SERVER_ICON[server]||'•'
        const sTools=filtered.filter(t=>t.server===server)
        return (
          <div key={server} style={{ marginBottom:'1.6rem' }}>
            <div className="server-header" style={{ borderBottom:`1px solid var(--border)` }}>
              <span style={{ width:22, height:22, borderRadius:6, display:'grid', placeItems:'center', background: `${color}14`, border:`1px solid ${color}26`, color, fontSize:'0.72rem', flexShrink:0 }}>{icon}</span>
              <span style={{ color }}>{server}</span>
              <span style={{ marginLeft:'auto', background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:999, padding:'0.1rem 0.45rem', fontSize:'0.66rem' }}>{sTools.length} tool{sTools.length!==1?'s':''}</span>
            </div>
            <div className="tools-grid">
              {sTools.map(t=>(
                <div key={t.name} className="tool-card">
                  <div className="row" style={{ marginBottom:'0.32rem', gap:'0.4rem' }}>
                    <div className="tool-card-name" style={{ flex:1 }}>{t.name}</div>
                    {t.sensitive && <span className="badge awaiting_approval" style={{ fontSize:'0.60rem' }}><span className="bdot" />sensitive</span>}
                  </div>
                  <div className="tool-card-desc">{t.description}</div>
                  {t.parameters && (
                    <div style={{ marginTop:'0.45rem', display:'flex', flexWrap:'wrap', gap:'0.28rem' }}>
                      {Object.keys(t.parameters.properties||{}).slice(0,4).map(k=>(
                        <span key={k} style={{ background:'var(--surface3)', border:'1px solid var(--border)', borderRadius:6, padding:'0.08rem 0.4rem', fontSize:'0.66rem', color:'var(--text3)', fontFamily:'JetBrains Mono, monospace' }}>{k}</span>
                      ))}
                      {Object.keys(t.parameters.properties||{}).length>4 && <span style={{ fontSize:'0.66rem', color:'var(--text3)' }}>+{Object.keys(t.parameters.properties).length-4} more</span>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
