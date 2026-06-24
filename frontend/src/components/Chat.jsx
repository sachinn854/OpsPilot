import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const SUGGESTIONS = [
  'What tools do you have available?',
  'List open issues on sachinn854/OpsPilot',
  'Summarize my uploaded documents',
]

function Avatar() {
  return (
    <div style={{
      width: 28, height: 28, borderRadius: 7,
      background: 'var(--accent)', color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.02em',
      flexShrink: 0,
    }}>AI</div>
  )
}

function Markdown({ text }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])  // {role, content}
  const [input, setInput]       = useState('')
  const [streaming, setStreaming] = useState(false)
  const [toolMsg, setToolMsg]   = useState('')   // "Running tool: X"
  const [convId, setConvId]     = useState(null)
  const [error, setError]       = useState('')
  const bottomRef               = useRef()
  const inputRef                = useRef()
  const abortRef                = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, toolMsg])

  async function handleSend(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || streaming) return
    if (text.length > 4000) {
      setError('Message too long (max 4000 characters).')
      return
    }

    setInput('')
    setError('')
    setToolMsg('')
    setMessages(prev => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '' },
    ])
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch('/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: convId }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(j.detail || 'Request failed')
      }

      const reader = res.body.getReader()
      const dec    = new TextDecoder()
      let buf      = ''

      const appendToken = (t) => {
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = {
            role: 'assistant',
            content: next[next.length - 1].content + t,
          }
          return next
        })
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n'); buf = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          let p
          try { p = JSON.parse(line.slice(5).trim()) } catch { continue }

          if (p.event === 'start') {
            setConvId(p.conversation_id)
          } else if (p.event === 'tool') {
            // A tool turn — discard any pre-tool partial text, show indicator.
            setToolMsg(p.name)
            setMessages(prev => {
              const next = [...prev]
              next[next.length - 1] = { role: 'assistant', content: '' }
              return next
            })
          } else if (p.event === 'token') {
            setToolMsg('')
            appendToken(p.text)
          } else if (p.event === 'error') {
            setError(p.detail || 'Error')
          } else if (p.event === 'done') {
            setConvId(p.conversation_id)
          }
        }
      }
    } catch (e) {
      setError(e.message)
      // Drop the empty assistant bubble on hard failure.
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last && last.role === 'assistant' && !last.content) return prev.slice(0, -1)
        return prev
      })
    } finally {
      abortRef.current = null
      setStreaming(false)
      setToolMsg('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  function stopStream() {
    abortRef.current?.abort()
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(e) }
  }

  function clearChat() {
    setMessages([]); setConvId(null); setError(''); setToolMsg('')
  }

  const lastIsEmptyAssistant =
    messages.length > 0 &&
    messages[messages.length - 1].role === 'assistant' &&
    !messages[messages.length - 1].content

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 4.5rem)' }}>
      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'1rem', flexShrink:0 }}>
        <div>
          <div className="page-title">Chat</div>
          <div className="page-subtitle">Conversational assistant — uses tools + your documents</div>
        </div>
        <div style={{ display:'flex', gap:'0.5rem' }}>
          {streaming && (
            <button className="btn btn-ghost" style={{ padding:'0.4rem 0.8rem', fontSize:'0.78rem', color:'var(--red)' }} onClick={stopStream}>
              ◼ Stop
            </button>
          )}
          {messages.length > 0 && !streaming && (
            <button className="btn btn-ghost" style={{ padding:'0.4rem 0.8rem', fontSize:'0.78rem' }} onClick={clearChat}>
              ↺ New chat
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', paddingRight:'0.25rem' }}>
        {messages.length === 0 && (
          <div style={{ height:'100%', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:'0.85rem' }}>
            <div style={{ fontSize:'1.8rem', color:'var(--text3)' }}>◎</div>
            <div style={{ fontSize:'0.88rem', color:'var(--text3)', textAlign:'center', maxWidth:380, lineHeight:1.6 }}>
              Ask anything — I can search your documents, check GitHub issues &amp; PRs, and more.
            </div>
            <div style={{ display:'flex', flexWrap:'wrap', gap:'0.4rem', justifyContent:'center', marginTop:'0.25rem' }}>
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="suggestion" onClick={() => setInput(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{
            display:'flex',
            gap:'0.65rem',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
            padding:'0.35rem 0',
          }}>
            {m.role === 'assistant' && <Avatar />}
            <div style={{
              maxWidth:'74%',
              background: m.role === 'user' ? 'var(--accent)' : 'var(--surface2)',
              color: m.role === 'user' ? '#fff' : 'var(--text)',
              border: m.role === 'user' ? 'none' : '1px solid var(--border)',
              borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '4px 14px 14px 14px',
              padding:'0.7rem 0.95rem',
              fontSize:'0.88rem',
              lineHeight:1.65,
            }}>
              {m.role === 'user'
                ? <span style={{ whiteSpace:'pre-wrap' }}>{m.content}</span>
                : (m.content
                    ? <Markdown text={m.content} />
                    : (i === messages.length - 1 && (toolMsg || streaming))
                      ? <ToolIndicator toolMsg={toolMsg} />
                      : null)
              }
            </div>
          </div>
        ))}

        {error && <div className="error" style={{ margin:'0.5rem 0' }}>{error}</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} style={{
        display:'flex', gap:'0.5rem',
        paddingTop:'0.85rem', borderTop:'1px solid var(--border)', flexShrink:0,
      }}>
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message…  (Enter to send, Shift+Enter for new line)"
          disabled={streaming}
          style={{
            flex:1,
            background:'var(--surface2)',
            border:'1px solid var(--border2)',
            borderRadius:'var(--r-sm)',
            color:'var(--text)',
            padding:'0.65rem 0.9rem',
            fontSize:'0.88rem',
            fontFamily:'Inter, sans-serif',
            resize:'none', lineHeight:1.55,
            maxHeight:140, overflowY:'auto',
          }}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={streaming || !input.trim()}
          style={{ flexShrink:0, alignSelf:'flex-end', padding:'0.65rem 1rem' }}
        >
          {streaming ? <div className="spinner" style={{ borderTopColor:'#fff' }} /> : '↑'}
        </button>
      </form>
    </div>
  )
}

function ToolIndicator({ toolMsg }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:'0.55rem', color:'var(--text3)' }}>
      {toolMsg ? (
        <>
          <div className="spinner" style={{ width:13, height:13, borderWidth:2 }} />
          <span style={{ fontSize:'0.82rem' }}>
            Running tool <span className="mono" style={{ color:'var(--orange)' }}>{toolMsg}</span>…
          </span>
        </>
      ) : (
        <span style={{ display:'flex', gap:'4px', alignItems:'center' }}>
          {[0,1,2].map(n => (
            <span key={n} style={{
              width:6, height:6, borderRadius:'50%', background:'var(--text3)',
              animation:`typing-dot 1.2s ${n*0.2}s infinite`, display:'inline-block',
            }} />
          ))}
        </span>
      )}
    </div>
  )
}
