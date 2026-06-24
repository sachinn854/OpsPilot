import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askDocument, fetchDocuments, uploadDocument } from '../api'

export default function Documents() {
  const [docs, setDocs]         = useState([])
  const [uploading, setUploading] = useState(false)
  const [question, setQuestion] = useState('')
  const [asking, setAsking]     = useState(false)
  const [answer, setAnswer]     = useState(null)
  const [error, setError]       = useState('')
  const fileRef                 = useRef()

  function loadDocs() {
    fetchDocuments().then(setDocs).catch(() => {})
  }

  useEffect(() => { loadDocs() }, [])

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true); setError('')
    try {
      await uploadDocument(file)
      loadDocs()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function handleAsk(e) {
    e.preventDefault()
    if (!question.trim() || asking) return
    setAsking(true); setAnswer(null); setError('')
    try {
      const res = await askDocument(question.trim())
      setAnswer(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setAsking(false)
    }
  }

  const EXT_COLOR = { pdf: '#dc2626', md: '#0891b2', txt: '#059669', py: '#d97706', js: '#d97706' }

  function extColor(filename) {
    const ext = filename.split('.').pop().toLowerCase()
    return EXT_COLOR[ext] || 'var(--text3)'
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Documents</div>
        <div className="page-subtitle">Upload files and ask questions from them</div>
      </div>

      {/* Upload */}
      <div className="card static" style={{ marginBottom:'1.5rem' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom: docs.length ? '1rem' : 0 }}>
          <span style={{ fontSize:'0.82rem', color:'var(--text2)', fontWeight:500 }}>
            {docs.length} document{docs.length !== 1 ? 's' : ''} uploaded
          </span>
          <div style={{ display:'flex', gap:'0.5rem', alignItems:'center' }}>
            {uploading && <div className="spinner" />}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md,.py,.js,.ts,.json"
              style={{ display:'none' }}
              onChange={handleUpload}
            />
            <button
              className="btn btn-primary"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
              style={{ padding:'0.45rem 0.9rem' }}
            >
              {uploading ? 'Uploading…' : '+ Upload file'}
            </button>
          </div>
        </div>

        {docs.length > 0 && (
          <div style={{ display:'flex', flexDirection:'column', gap:'0.35rem' }}>
            {docs.map(d => (
              <div key={d.id} style={{
                display:'flex', alignItems:'center', gap:'0.65rem',
                padding:'0.5rem 0.7rem',
                background:'var(--surface2)', border:'1px solid var(--border)',
                borderRadius:'var(--r-xs)',
              }}>
                <span style={{
                  fontFamily:'JetBrains Mono, monospace',
                  fontSize:'0.65rem', fontWeight:700,
                  color: extColor(d.filename),
                  textTransform:'uppercase',
                  width:28, textAlign:'center',
                  flexShrink:0,
                }}>
                  {d.filename.split('.').pop().toUpperCase()}
                </span>
                <span style={{ fontSize:'0.83rem', color:'var(--text)', flex:1, fontFamily:'JetBrains Mono, monospace' }}>
                  {d.filename}
                </span>
                <span style={{ fontSize:'0.72rem', color:'var(--text3)' }}>
                  {d.num_chunks} chunk{d.num_chunks !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        )}

        {docs.length === 0 && !uploading && (
          <div className="empty" style={{ padding:'2rem 1rem' }}>
            <div className="empty-icon" style={{ fontSize:'1.5rem' }}>⊡</div>
            <div className="empty-text">No documents yet — upload a PDF, TXT, or MD file</div>
          </div>
        )}
      </div>

      {/* Ask */}
      <div className="section-label">Ask your documents</div>

      <div style={{ maxWidth:600 }}>
        <form onSubmit={handleAsk} style={{ display:'flex', gap:'0.5rem', marginBottom:'1rem' }}>
          <div className="field" style={{ flex:1, marginBottom:0 }}>
            <input
              type="text"
              placeholder="e.g. What is the leave policy?"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              disabled={asking || !docs.length}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={asking || !question.trim() || !docs.length}
            style={{ flexShrink:0, alignSelf:'flex-end', marginBottom:'1.1rem' }}
          >
            {asking ? <><div className="spinner" style={{ borderTopColor:'#fff' }} /> Asking…</> : 'Ask'}
          </button>
        </form>

        {!docs.length && (
          <div style={{ fontSize:'0.78rem', color:'var(--text3)', marginBottom:'0.5rem' }}>
            Upload a document first to ask questions.
          </div>
        )}

        {error && <div className="error" style={{ marginBottom:'1rem' }}>{error}</div>}

        {answer && (
          <div>
            <div className="report-block md" style={{ marginBottom:'0.75rem' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer.answer}</ReactMarkdown>
            </div>

            {answer.sources?.length > 0 && (
              <div style={{ display:'flex', flexDirection:'column', gap:'0.3rem' }}>
                {answer.sources.map(s => (
                  <div key={s.ref} style={{
                    display:'flex', alignItems:'center', gap:'0.5rem',
                    fontSize:'0.75rem', color:'var(--text3)',
                  }}>
                    <span style={{
                      background:'var(--surface2)', border:'1px solid var(--border)',
                      borderRadius:3, padding:'0.05rem 0.35rem',
                      fontFamily:'JetBrains Mono, monospace', fontSize:'0.68rem',
                      color:'var(--text2)',
                    }}>[{s.ref}]</span>
                    <span className="mono">{s.source}</span>
                    <span>· chunk {s.chunk_index}</span>
                    <span>· score {(s.score * 100).toFixed(0)}%</span>
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
