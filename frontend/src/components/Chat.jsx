import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { deleteConversation, fetchConversationMessages, fetchConversations } from '../api'

// ── helpers ──────────────────────────────────────────────────────────────────

function timeAgo(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

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

// ── Sidebar ───────────────────────────────────────────────────────────────────

function Sidebar({ convList, activeId, onSelect, onNew, onDelete, loading }) {
  const [hovered, setHovered] = useState(null)

  return (
    <aside style={{
      width: 240,
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--r)',
      overflow: 'hidden',
    }}>
      {/* New chat button */}
      <div style={{ padding: '0.65rem 0.75rem', borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={onNew}
          className="btn btn-primary"
          style={{ width: '100%', fontSize: '0.82rem', padding: '0.5rem 0.75rem', justifyContent: 'center' }}
        >
          + New Chat
        </button>
      </div>

      {/* Conversations list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.35rem 0' }}>
        {loading && (
          <div style={{ padding: '1rem', color: 'var(--text3)', fontSize: '0.8rem', textAlign: 'center' }}>
            Loading…
          </div>
        )}
        {!loading && convList.length === 0 && (
          <div style={{ padding: '1rem', color: 'var(--text3)', fontSize: '0.8rem', textAlign: 'center' }}>
            No conversations yet
          </div>
        )}
        {convList.map(conv => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv)}
            onMouseEnter={() => setHovered(conv.id)}
            onMouseLeave={() => setHovered(null)}
            style={{
              padding: '0.5rem 0.75rem',
              cursor: 'pointer',
              background: conv.id === activeId ? 'rgba(99,102,241,0.12)' : hovered === conv.id ? 'var(--surface2)' : 'transparent',
              borderLeft: conv.id === activeId ? '2px solid var(--accent)' : '2px solid transparent',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.4rem',
              transition: 'background 0.12s',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: '0.8rem',
                color: conv.id === activeId ? 'var(--text)' : 'var(--text2)',
                fontWeight: conv.id === activeId ? 600 : 400,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                lineHeight: 1.4,
              }}>
                {conv.title || 'Untitled'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: 2 }}>
                {timeAgo(conv.last_active || conv.created_at)}
                {conv.msg_count > 0 && ` · ${conv.msg_count} msgs`}
              </div>
            </div>
            {/* Delete button — show on hover */}
            {hovered === conv.id && (
              <button
                onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text3)', fontSize: '0.85rem', padding: '0 2px',
                  lineHeight: 1, flexShrink: 0, marginTop: 1,
                }}
                title="Delete conversation"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </aside>
  )
}

// ── Main Chat component ───────────────────────────────────────────────────────

const SUGGESTIONS = [
  'What tools do you have available?',
  'List open issues on my repos',
  'Summarize my uploaded documents',
]

export default function Chat() {
  // Conversations list
  const [convList, setConvList] = useState([])
  const [convLoading, setConvLoading] = useState(true)

  // Active conversation
  const [convId, setConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [messagesLoading, setMessagesLoading] = useState(false)

  // Chat input / streaming
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [toolMsg, setToolMsg] = useState('')
  const [error, setError] = useState('')

  const bottomRef = useRef()
  const inputRef  = useRef()
  const abortRef  = useRef(null)

  // Load conversations on mount
  useEffect(() => {
    loadConvList()
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, toolMsg])

  async function loadConvList() {
    try {
      const data = await fetchConversations()
      setConvList(data)
    } catch {}
    setConvLoading(false)
  }

  async function selectConversation(conv) {
    if (conv.id === convId) return
    setConvId(conv.id)
    setError('')
    setToolMsg('')
    setMessagesLoading(true)
    try {
      const msgs = await fetchConversationMessages(conv.id)
      setMessages(msgs.map(m => ({ role: m.role, content: m.content })))
    } catch {
      setMessages([])
    }
    setMessagesLoading(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  function newChat() {
    setConvId(null)
    setMessages([])
    setError('')
    setToolMsg('')
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  async function handleDelete(id) {
    try {
      await deleteConversation(id)
      setConvList(prev => prev.filter(c => c.id !== id))
      if (convId === id) newChat()
    } catch {}
  }

  // Refresh conv list (called after title is auto-generated)
  const scheduleRefresh = useCallback(() => {
    setTimeout(loadConvList, 3000) // wait 3s for LLM title to be written
  }, [])

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

    const isNew = !convId
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
            const newId = p.conversation_id
            setConvId(newId)
            if (isNew) {
              // Optimistically add to sidebar with user message as placeholder title
              setConvList(prev => [
                { id: newId, title: text.slice(0, 50), created_at: new Date().toISOString(), msg_count: 0, last_active: null },
                ...prev.filter(c => c.id !== newId),
              ])
            }
          } else if (p.event === 'tool') {
            setToolMsg(p.name)
            setMessages(prev => { const n = [...prev]; n[n.length - 1] = { role: 'assistant', content: '' }; return n })
          } else if (p.event === 'token') {
            setToolMsg('')
            appendToken(p.text)
          } else if (p.event === 'error') {
            setError(p.detail || 'Error')
          } else if (p.event === 'done') {
            if (isNew) scheduleRefresh() // pick up the LLM-generated title
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

  const lastIsEmptyAssistant =
    messages.length > 0 &&
    messages[messages.length - 1].role === 'assistant' &&
    !messages[messages.length - 1].content

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 4.5rem)', gap: '0.85rem' }}>

      {/* ── Left sidebar: conversation history ── */}
      <Sidebar
        convList={convList}
        activeId={convId}
        onSelect={selectConversation}
        onNew={newChat}
        onDelete={handleDelete}
        loading={convLoading}
      />

      {/* ── Right: chat area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexShrink: 0 }}>
          <div>
            <div className="page-title">
              {convList.find(c => c.id === convId)?.title || 'Chat'}
            </div>
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
          {messagesLoading && (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text3)', fontSize: '0.85rem' }}>
              Loading messages…
            </div>
          )}

          {!messagesLoading && messages.length === 0 && (
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

          {!messagesLoading && messages.map((m, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: '0.65rem',
              justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
              padding: '0.35rem 0',
            }}>
              {m.role === 'assistant' && <Avatar />}
              <div style={{
                maxWidth: '74%',
                background: m.role === 'user' ? 'var(--accent)' : 'var(--surface2)',
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

          {error && <div className="error" style={{ margin: '0.5rem 0' }}>{error}</div>}
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
    </div>
  )
}
