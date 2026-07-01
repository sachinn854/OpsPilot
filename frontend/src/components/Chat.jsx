import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchConversationMessages, getToken } from '../api'

const API_ROOT = import.meta.env.VITE_API_URL || ''

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

function ToolIndicator({ toolMsg }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', color: 'var(--text3)' }}>
      {toolMsg ? (
        <>
          <div className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} />
          <span style={{ fontSize: '0.82rem' }}>
            Running <span className="mono" style={{ color: 'var(--orange)' }}>{toolMsg}</span>…
          </span>
        </>
      ) : (
        <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[0, 1, 2].map(n => (
            <span key={n} style={{
              width: 6, height: 6, borderRadius: '50%', background: 'var(--text3)',
              animation: `typing-dot 1.2s ${n * 0.2}s infinite`, display: 'inline-block',
            }} />
          ))}
        </span>
      )}
    </div>
  )
}

const SUGGESTIONS = [
  'What tools do you have available?',
  'List open issues on my repos',
  'Summarize my uploaded documents',
]

export default function Chat({ activeConvId, setActiveConvId, convTitle, onConvCreated, onRefreshConvList }) {
  const [messages, setMessages]   = useState([])
  const [loading, setLoading]     = useState(false)
  const [input, setInput]         = useState('')
  const [streaming, setStreaming] = useState(false)
  const [toolMsg, setToolMsg]     = useState('')
  const [error, setError]         = useState('')

  const bottomRef = useRef()
  const inputRef  = useRef()
  const abortRef  = useRef(null)

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConvId) {
      setMessages([])
      setError('')
      setToolMsg('')
      return
    }
    setLoading(true)
    setMessages([])
    fetchConversationMessages(activeConvId)
      .then(msgs => setMessages(msgs.map(m => ({ role: m.role, content: m.content }))))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false))
  }, [activeConvId])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, toolMsg])

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  // Focus input on mount and when active conv changes
  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [activeConvId])

  async function handleSend(e) {
    e?.preventDefault()
    const text = input.trim()
    if (!text || streaming) return
    if (text.length > 4000) { setError('Message too long (max 4000 characters).'); return }

    setInput('')
    setError('')
    setToolMsg('')
    setMessages(prev => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '' },
    ])
    setStreaming(true)

    const isNew = !activeConvId
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${API_ROOT}/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ message: text, conversation_id: activeConvId }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const j = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(j.detail || 'Request failed')
      }

      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      let newConvId = null

      const appendToken = t => {
        setMessages(prev => {
          const next = [...prev]
          next[next.length - 1] = { role: 'assistant', content: next[next.length - 1].content + t }
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
          let p; try { p = JSON.parse(line.slice(5).trim()) } catch { continue }

          if (p.event === 'start') {
            newConvId = p.conversation_id
            setActiveConvId(p.conversation_id)
            if (isNew) onConvCreated?.(p.conversation_id, text.slice(0, 50))
          } else if (p.event === 'tool') {
            setToolMsg(p.name)
            setMessages(prev => { const n = [...prev]; n[n.length - 1] = { role: 'assistant', content: '' }; return n })
          } else if (p.event === 'token') {
            setToolMsg('')
            appendToken(p.text)
          } else if (p.event === 'error') {
            setError(p.detail || 'Error')
          } else if (p.event === 'done') {
            if (isNew) onRefreshConvList?.()
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message)
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant' && !last.content) return prev.slice(0, -1)
        return prev
      })
    } finally {
      abortRef.current = null
      setStreaming(false)
      setToolMsg('')
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  function stopStream() { abortRef.current?.abort() }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 4.5rem)' }}>

      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '1rem', flexShrink: 0,
      }}>
        <div>
          <div className="page-title">{convTitle || 'Chat'}</div>
          <div className="page-subtitle">Conversational assistant — uses tools + your documents</div>
        </div>
        {streaming && (
          <button
            className="btn btn-ghost"
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.78rem', color: 'var(--red)' }}
            onClick={stopStream}
          >
            ◼ Stop
          </button>
        )}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: '0.25rem' }}>
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text3)', fontSize: '0.85rem' }}>
            Loading messages…
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div style={{
            height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: '0.85rem',
          }}>
            <div style={{ fontSize: '1.8rem', color: 'var(--text3)' }}>◎</div>
            <div style={{ fontSize: '0.88rem', color: 'var(--text3)', textAlign: 'center', maxWidth: 380, lineHeight: 1.6 }}>
              Ask anything — I can search your documents, check GitHub issues & PRs, and more.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', justifyContent: 'center', marginTop: '0.25rem' }}>
              {SUGGESTIONS.map((s, i) => (
                <button key={i} className="suggestion" onClick={() => setInput(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {!loading && messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            gap: '0.65rem',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
            padding: '0.35rem 0',
          }}>
            {m.role === 'assistant' && <Avatar />}
            <div style={{
              maxWidth: '74%',
              background: m.role === 'user' ? '#2563eb' : 'var(--surface2)',
              color: m.role === 'user' ? '#fff' : 'var(--text)',
              border: m.role === 'user' ? 'none' : '1px solid var(--border)',
              borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '4px 14px 14px 14px',
              padding: '0.7rem 0.95rem',
              fontSize: '0.88rem',
              lineHeight: 1.65,
            }}>
              {m.role === 'user'
                ? <span style={{ whiteSpace: 'pre-wrap' }}>{m.content}</span>
                : (m.content
                  ? <Markdown text={m.content} />
                  : (i === messages.length - 1 && (toolMsg || streaming))
                    ? <ToolIndicator toolMsg={toolMsg} />
                    : null)
              }
            </div>
          </div>
        ))}

        {error && (
          <div className="error" style={{ margin: '0.5rem 0' }}>
            {error}
            {error.toLowerCase().includes('api key') && (
              <span>
                {' — '}
                <a href="#settings" style={{ color: '#f87171', textDecoration: 'underline' }}
                  onClick={e => { e.preventDefault(); window.location.hash = 'settings' }}>
                  Go to Settings
                </a>
              </span>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSend}
        style={{
          display: 'flex', gap: '0.5rem',
          paddingTop: '0.85rem', borderTop: '1px solid var(--border)', flexShrink: 0,
        }}
      >
        <textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message…  (Enter to send, Shift+Enter for new line)"
          disabled={streaming}
          style={{
            flex: 1,
            background: 'var(--surface2)',
            border: '1px solid var(--border2)',
            borderRadius: 'var(--r-sm)',
            color: 'var(--text)',
            padding: '0.65rem 0.9rem',
            fontSize: '0.88rem',
            fontFamily: 'Inter, sans-serif',
            resize: 'none', lineHeight: 1.55,
            maxHeight: 140, overflowY: 'auto',
          }}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={streaming || !input.trim()}
          style={{ flexShrink: 0, alignSelf: 'flex-end', padding: '0.65rem 1rem' }}
        >
          {streaming ? <div className="spinner" style={{ borderTopColor: '#fff' }} /> : '↑'}
        </button>
      </form>
    </div>
  )
}
