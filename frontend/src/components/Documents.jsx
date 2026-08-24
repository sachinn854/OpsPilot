import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askDocument, fetchDocuments, uploadDocument } from '../api'

const EXT_COLOR = { pdf: '#ef4444', md: '#06b6d4', txt: '#10b981', py: '#f59e0b', js: '#f59e0b', json: '#a78bfa' }
function extColor(fn){ const ext=(fn.split('.').pop()||'').toLowerCase(); return EXT_COLOR[ext]||'var(--text3)' }

export default function Documents() {
  const [docs, setDocs]         = useState([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [question, setQuestion] = useState('')
  const [asking, setAsking]     = useState(false)
  const [answer, setAnswer]     = useState(null)
  const [error, setError]       = useState('')
  const fileRef                 = useRef()

  function loadDocs(){ fetchDocuments().then(setDocs).catch(()=>{}) }
  useEffect(()=>{ loadDocs() },[])

  async function doUpload(file){
    if(!file) return
    setUploading(true); setError('')
    try{ await uploadDocument(file); loadDocs() }catch(e){ setError(e.message) }
    finally{ setUploading(false) }
  }
  function handleFileInput(e){
    const f=e.target.files?.[0]; e.target.value=''
    doUpload(f)
  }
  function handleDrop(e){
    e.preventDefault(); setDragOver(false)
    const f=e.dataTransfer.files?.[0]
    doUpload(f)
  }
  async function handleAsk(e){
    e.preventDefault()
    if(!question.trim()||asking) return
    setAsking(true); setAnswer(null); setError('')
    try{ const res=await askDocument(question.trim()); setAnswer(res) }catch(e){ setError(e.message) }
    finally{ setAsking(false) }
  }

  return (
    <div>
      <div className="page-header" style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'0.6rem' }}>
            <div style={{ width:30, height:30, borderRadius:8, display:'grid', placeItems:'center', background:'linear-gradient(135deg, #06b6d4, #0891b2)', color:'#fff', fontSize:'0.85rem' }}>⊡</div>
            <div className="page-title">Documents</div>
            <span style={{ background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:999, padding:'0.16rem 0.55rem', fontSize:'0.70rem', color:'var(--text2)', fontFamily:'JetBrains Mono, monospace', fontWeight:700 }}>{docs.length} file{docs.length!==1?'s':''}</span>
          </div>
          <div className="page-subtitle">Upload files and ask grounded questions — answers are cited from your docs</div>
        </div>
      </div>

      {/* Upload dropzone */}
      <div
        onDragOver={e=>{e.preventDefault(); setDragOver(true)}}
        onDragLeave={()=>setDragOver(false)}
        onDrop={handleDrop}
        className="card static"
        style={{
          marginBottom:'1.2rem',
          border: dragOver ? '1px solid rgba(124,124,255,0.35)' : '1px solid var(--border)',
          background: dragOver
            ? 'linear-gradient(180deg, rgba(124,124,255,0.08), transparent 60%), var(--surface)'
            : 'linear-gradient(180deg, rgba(255,255,255,0.015), transparent 55%), var(--surface)',
          boxShadow: dragOver ? '0 8px 24px rgba(124,124,255,0.14)' : 'var(--shadow-sm)',
          transition:'all 0.14s',
        }}
      >
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:'1rem', flexWrap:'wrap' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'0.7rem' }}>
            <div style={{
              width:36, height:36, borderRadius:10, display:'grid', placeItems:'center',
              background: dragOver ? 'var(--accent-dim)' : 'var(--surface2)',
              border:`1px solid ${dragOver?'rgba(124,124,255,0.22)':'var(--border2)'}`,
              color: dragOver ? 'var(--accent)' : 'var(--text3)', fontSize:'1rem',
              transition:'all 0.14s',
            }}>⤒</div>
            <div>
              <div style={{ fontSize:'0.84rem', fontWeight:650, color:'var(--text)' }}>
                {dragOver ? 'Drop file to upload' : 'Drag & drop or browse'}
              </div>
              <div style={{ fontSize:'0.72rem', color:'var(--text3)' }}>PDF, TXT, MD, JSON, code files — max 20 MB</div>
            </div>
          </div>
          <div style={{ display:'flex', gap:'0.5rem', alignItems:'center' }}>
            {uploading && <span style={{ display:'inline-flex', alignItems:'center', gap:'0.4rem', fontSize:'0.78rem', color:'var(--text2)' }}><span className="spinner" /> Uploading…</span>}
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.py,.js,.ts,.json" style={{ display:'none' }} onChange={handleFileInput} />
            <button className="btn btn-primary" disabled={uploading} onClick={()=>fileRef.current?.click()} style={{ padding:'0.52rem 0.95rem' }}>
              {uploading ? 'Uploading…' : '＋ Browse files'}
            </button>
          </div>
        </div>

        {docs.length>0 ? (
          <div style={{ display:'flex', flexDirection:'column', gap:'0.35rem', marginTop:'1rem' }}>
            {docs.map(d=>(
              <div key={d.id} style={{
                display:'flex', alignItems:'center', gap:'0.65rem',
                padding:'0.58rem 0.7rem',
                background:'var(--surface2)', border:'1px solid var(--border)', borderRadius:10,
                transition:'border-color 0.12s',
              }}>
                <span style={{
                  fontFamily:'JetBrains Mono, monospace', fontSize:'0.62rem', fontWeight:800,
                  color:'#fff', background: extColor(d.filename), borderRadius:6,
                  padding:'0.18rem 0.38rem', textTransform:'uppercase', letterSpacing:'0.04em',
                  minWidth:36, textAlign:'center',
                }}>{d.filename.split('.').pop().toUpperCase().slice(0,4)}</span>
                <span style={{ fontSize:'0.84rem', color:'var(--text)', flex:1, fontFamily:'JetBrains Mono, monospace', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{d.filename}</span>
                <span style={{ fontSize:'0.70rem', color:'var(--text3)', background:'var(--surface3)', border:'1px solid var(--border)', borderRadius:999, padding:'0.14rem 0.5rem', fontFamily:'JetBrains Mono, monospace', whiteSpace:'nowrap' }}>
                  {d.num_chunks} chunk{d.num_chunks!==1?'s':''}
                </span>
              </div>
            ))}
          </div>
        ) : !uploading && (
          <div style={{
            marginTop:'1rem', border:'1px dashed var(--border2)', borderRadius:10,
            padding:'1.4rem 1rem', textAlign:'center', color:'var(--text3)',
          }}>
            <div style={{ fontSize:'1.2rem', marginBottom:'0.35rem' }}>⊡</div>
            <div style={{ fontSize:'0.82rem', color:'var(--text2)', fontWeight:500 }}>No documents yet</div>
            <div style={{ fontSize:'0.72rem', color:'var(--text3)', marginTop:'0.2rem' }}>Upload a PDF, TXT, or MD file to start asking questions</div>
          </div>
        )}
      </div>

      {/* Ask */}
      <div className="section-label">Ask your documents</div>
      <div style={{ maxWidth:640 }}>
        <form onSubmit={handleAsk} style={{
          display:'flex', gap:'0.5rem', marginBottom:'0.85rem',
          background:'var(--surface)', border:'1px solid var(--border)', borderRadius:12, padding:'0.5rem',
        }}>
          <input
            type="text"
            placeholder="e.g. What is the leave policy?"
            value={question} onChange={e=>setQuestion(e.target.value)}
            disabled={asking||!docs.length}
            style={{
              flex:1, background:'var(--surface2)', border:'1px solid var(--border2)', borderRadius:9,
              color:'var(--text)', padding:'0.58rem 0.8rem', fontSize:'0.86rem', fontFamily:'Inter, sans-serif',
            }}
          />
          <button
            type="submit" className="btn btn-primary"
            disabled={asking||!question.trim()||!docs.length}
            style={{ flexShrink:0, padding:'0.52rem 0.95rem' }}
          >
            {asking ? <><span className="spinner" style={{ borderTopColor:'#fff', width:13, height:13 }} /> Asking…</> : 'Ask'}
          </button>
        </form>
        {!docs.length && <div style={{ fontSize:'0.76rem', color:'var(--text3)', marginBottom:'0.6rem', fontFamily:'JetBrains Mono, monospace' }}>Upload a document first to ask questions.</div>}
        {error && <div className="error" style={{ marginBottom:'0.85rem' }}>{error}</div>}
        {answer && (
          <div style={{ animation:'pageIn 0.25s ease' }}>
            <div className="report-block md" style={{ marginBottom:'0.7rem' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.answer}</ReactMarkdown>
            </div>
            {answer.sources?.length>0 && (
              <div style={{
                background:'var(--surface)', border:'1px solid var(--border)', borderRadius:10, padding:'0.6rem 0.7rem',
                display:'flex', flexDirection:'column', gap:'0.32rem',
              }}>
                <div style={{ fontSize:'0.68rem', fontWeight:700, color:'var(--text3)', fontFamily:'JetBrains Mono, monospace', letterSpacing:'0.06em', textTransform:'uppercase', marginBottom:'0.15rem' }}>Sources</div>
                {answer.sources.map(s=>(
                  <div key={s.ref} style={{ display:'flex', alignItems:'center', gap:'0.5rem', fontSize:'0.74rem', color:'var(--text3)', flexWrap:'wrap' }}>
                    <span style={{ background:'var(--surface2)', border:'1px solid var(--border2)', borderRadius:6, padding:'0.08rem 0.38rem', fontFamily:'JetBrains Mono, monospace', fontSize:'0.68rem', color:'var(--accent)' }}>[{s.ref}]</span>
                    <span className="mono" style={{ color:'var(--text2)' }}>{s.source}</span>
                    <span>· chunk {s.chunk_index}</span>
                    <span style={{
                      marginLeft:'auto', background: s.score>0.7 ? 'var(--green-dim)' : 'var(--surface3)',
                      color: s.score>0.7 ? 'var(--green)' : 'var(--text3)',
                      border:`1px solid ${s.score>0.7?'var(--green-brd)':'var(--border2)'}`,
                      borderRadius:999, padding:'0.06rem 0.45rem', fontSize:'0.66rem', fontWeight:700, fontFamily:'JetBrains Mono, monospace',
                    }}>{(s.score*100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
