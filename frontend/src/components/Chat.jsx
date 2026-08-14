import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { fetchConversationMessages, getToken } from '../api'

const API_ROOT = import.meta.env.VITE_API_URL || ''

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
        <span style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, toolMsg])

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

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
    <div className="chat-root">

      {/* Messages */}
      <div className="chat-messages">
        <div className="chat-thread">

          {loading && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text3)', fontSize: '0.85rem' }}>
              <div className="spinner" style={{ marginRight: '0.5rem' }} /> Loading messages…
            </div>
          )}

          {!loading && messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-icon">◎</div>
              <div className="chat-empty-title">What can I help with?</div>
              <div className="chat-empty-desc">
                Ask anything — I can search your documents, check GitHub, call tools, and more.
              </div>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="suggestion" onClick={() => setInput(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {!loading && messages.map((m, i) => (
            <div key={i} className={`msg-row ${m.role}`}>
              {m.role === 'assistant' && (
                <div className="msg-avatar">AI</div>
              )}
              <div className={`msg-bubble ${m.role}`}>
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
      </div>

      {/* Input */}
      <div className="chat-bottom">
        <form className="chat-form" onSubmit={handleSend}>
          <textarea
            ref={inputRef}
            rows={1}
            className="chat-textarea"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message OpsPilot…"
            disabled={streaming}
          />
          {streaming ? (
            <button type="button" className="chat-stop" onClick={stopStream}>
              ◼ Stop
            </button>
          ) : (
            <button
              type="submit"
              className="chat-send"
              disabled={!input.trim()}
            >
              {streaming ? <div className="spinner" style={{ borderTopColor: '#fff', width: 16, height: 16 }} /> : '↑'}
            </button>
          )}
        </form>
        <div className="chat-hint">
          <span>Enter to send · Shift+Enter for new line</span>
          <span>{input.length > 0 ? `${input.length} / 4000` : ''}</span>
        </div>
      </div>

    </div>
  )
}
