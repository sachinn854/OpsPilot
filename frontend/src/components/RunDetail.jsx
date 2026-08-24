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
  return <span className={`badge ${status}`}><span className="bdot" />{status.replace('_',' ')}</span>
}
const POLL_INTERVALS = [2000,4000,8000,15000,30000]
const TERMINAL = new Set(['completed','failed'])

export default function RunDetail({ runId, onBack }) {
  const [run, setRun]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [copied, setCopied]   = useState(false)
  const pollRef               = useRef(null)
  const attemptRef            = useRef(0)

  useEffect(()=>{
    let cancelled=false
    async function poll(){
      try{
        const r = await fetchRun(runId)
        if(cancelled) return
        setRun(r); setLoading(false)
        if(!TERMINAL.has(r.status)){
          const delay = POLL_INTERVALS[Math.min(attemptRef.current, POLL_INTERVALS.length-1)]
          attemptRef.current+=1
          pollRef.current=setTimeout(poll, delay)
        }
      }catch(e){ if(!cancelled) setError(e.message); setLoading(false) }
    }
    poll()
    return ()=>{ cancelled=true; clearTimeout(pollRef.current) }
  },[runId])

  async function copyId(){
    try{ await navigator.clipboard.writeText(run.id); setCopied(true); setTimeout(()=>setCopied(false),1400) }catch{}
  }

  if(loading) return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back to runs</button>
      <div style={{ display:'flex', flexDirection:'column', gap:'0.6rem', marginTop:'1rem' }}>
        <div className="skeleton" style={{ height:22, width:'50%' }} />
        <div className="skeleton" style={{ height:14, width:'75%' }} />
        <div className="skeleton" style={{ height:120, width:'100%' }} />
      </div>
    </div>
  )
  if(error)  return <><button className="back-btn" onClick={onBack}>← Back</button><div className="error">{error}</div></>
  if(!run)   return null

  const planSteps = (()=>{ try{ return JSON.parse(run.plan||'[]') }catch{ return [] } })()

  return (
    <div>
      <button className="back-btn" onClick={onBack}>← Back to runs</button>

      <div style={{
        background:'linear-gradient(180deg, rgba(124,124,255,0.06), transparent 55%), var(--surface)',
        border:'1px solid var(--border)', borderRadius:14, padding:'1rem 1.1rem', marginBottom:'1rem',
        boxShadow:'var(--shadow-sm)',
      }}>
        <div className="row" style={{ marginBottom:'0.55rem', flexWrap:'wrap' }}>
          <Badge status={run.status} />
          <span className="mono" style={{
            fontSize:'0.70rem', color:'var(--text3)', background:'var(--surface2)', border:'1px solid var(--border)',
            borderRadius:999, padding:'0.18rem 0.55rem', display:'inline-flex', alignItems:'center', gap:'0.35rem',
          }}>
            {run.id}
            <button onClick={copyId} style={{
              background: copied ? 'var(--green-dim)' : 'var(--surface3)', border:'1px solid var(--border2)', borderRadius:6,
              color: copied ? 'var(--green)' : 'var(--text3)', fontSize:'0.66rem', padding:'1px 5px', cursor:'pointer',
              fontFamily:'JetBrains Mono, monospace',
            }}>{copied?'Copied':'Copy'}</button>
          </span>
          {!TERMINAL.has(run.status) && (
            <span style={{
              marginLeft:'auto', display:'inline-flex', alignItems:'center', gap:'0.35rem',
              fontSize:'0.72rem', color:'var(--amber)', background:'var(--amber-dim)', border:'1px solid var(--amber-brd)',
              borderRadius:999, padding:'0.2rem 0.6rem', fontWeight:600,
            }}>
              <span className="spinner" style={{ width:11, height:11, borderWidth:2 }} /> Live — auto-refreshing
            </span>
          )}
        </div>
        <div style={{ fontSize:'1.02rem', fontWeight:700, color:'var(--text)', lineHeight:1.45, letterSpacing:'-0.02em' }}>{run.goal}</div>
      </div>

      <div className="stats-row">
        {run.confidence!=null && (
          <div className="stat-chip">
            Confidence <strong style={{ color: run.confidence>=0.7 ? 'var(--green)' : 'var(--amber)' }}>{run.confidence.toFixed(2)}</strong>
            <span style={{ width:56, height:6, borderRadius:999, background:'var(--surface3)', overflow:'hidden', display:'inline-block' }}>
              <span style={{ display:'block', height:'100%', width:`${Math.round(run.confidence*100)}%`, background: run.confidence>=0.7?'var(--green)':'var(--amber)', borderRadius:999 }} />
            </span>
          </div>
        )}
        <div className="stat-chip">Attempts <strong>{run.attempts}</strong></div>
        {planSteps.length>0 && <div className="stat-chip">Steps <strong>{planSteps.length}</strong></div>}
        {run.tool_calls?.length>0 && <div className="stat-chip">Tool calls <strong>{run.tool_calls.length}</strong></div>}
      </div>

      {planSteps.length>0 && (
        <>
          <div className="section-label">Pipeline</div>
          <div className="timeline">
            {Object.entries(NODE_META).map(([key, meta])=>{
              if(key==='security') return null
              if(key==='planner' && !planSteps.length) return null
              if(key==='execution' && !run.tool_calls?.length) return null
              if(key==='critic' && run.confidence==null) return null
              if(key==='reporting' && !run.report) return null
              return (
                <div key={key} className={`tl-item ${meta.cls}`}>
                  <div className="tl-vline" />
                  <div className="tl-icon">{meta.icon}</div>
                  <div className="tl-body">
                    <div className="tl-label">{meta.label}</div>
                    {key==='planner' && (
                      <div className="plan-steps">
                        {planSteps.map((s,i)=>(
                          <div key={i} className="plan-step">
                            <span className="plan-num">{i+1}</span>
                            <span className={`plan-kind ${s.kind}`}>{s.kind}</span>
                            <span>{s.description}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {key==='execution' && run.tool_calls?.map((tc,i)=>(
                      <div key={i} className="tool-call">
                        <span className={`tc-status ${tc.ok?'ok':'err'}`}>{tc.ok?'✓':'✗'}</span>
                        <span className="tc-name">{tc.tool_name}</span>
                        {tc.error && <span style={{ marginLeft:'auto', fontSize:'0.72rem', color:'var(--red)' }}>{String(tc.error).slice(0,80)}</span>}
                      </div>
                    ))}
                    {key==='critic' && run.confidence!=null && (
                      <div className="tl-detail">Score <strong style={{ color: run.confidence>=0.7?'var(--green)':'var(--amber)' }}>{run.confidence.toFixed(2)}</strong></div>
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
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:'0.5rem' }}>
              <button
                onClick={async()=>{ try{ await navigator.clipboard.writeText(run.report) }catch{} }}
                style={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:8, color:'var(--text3)', fontSize:'0.70rem', padding:'0.3rem 0.6rem', cursor:'pointer', fontFamily:'JetBrains Mono, monospace' }}
              >Copy report</button>
            </div>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{run.report}</ReactMarkdown>
          </div>
        </>
      )}
      {run.error && <div className="error" style={{ marginTop:'1rem' }}>{run.error}</div>}
    </div>
  )
}
