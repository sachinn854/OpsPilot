import { useEffect, useState } from 'react'
import RunList from './components/RunList'
import RunDetail from './components/RunDetail'
import ApprovalPanel from './components/ApprovalPanel'
import NewRun from './components/NewRun'
import ToolsPanel from './components/ToolsPanel'
import Documents from './components/Documents'
import Chat from './components/Chat'
import Settings from './components/Settings'
import SlackFeatures from './components/SlackFeatures'
import Login from './components/Login'
import { authMe, clearAuth, deleteConversation, fetchConversations, getToken, getUser } from './api'
import './App.css'

function timeAgo(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60)     return 'just now'
  if (diff < 3600)   return `${Math.floor(diff / 60)}m`
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h`
  if (diff < 604800) return `${Math.floor(diff / 86400)}d`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const NAV_BOTTOM = [
  { id: 'runs',      icon: '▶', label: 'Runs',      group: 'ops'  },
  { id: 'approvals', icon: '◈', label: 'Approvals', group: 'ops'  },
  { id: 'documents', icon: '⊡', label: 'Documents', group: 'ops'  },
  { id: 'tools',     icon: '⊙', label: 'Tools',     group: 'sys'  },
  { id: 'slack',     icon: '#', label: 'Slack',      group: 'sys'  },
  { id: 'settings',  icon: '⚙', label: 'Settings',  group: 'sys'  },
]

const GROUP_LABELS = { ops: 'Workspace', sys: 'System' }

export default function App() {
  const [page, setPage]                   = useState('chat')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [online, setOnline]               = useState(null)

  // Auth state
  const [user, setUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)

  // Conversation state — lives here so sidebar can render the list
  const [convList, setConvList]         = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [hoveredConv, setHoveredConv]   = useState(null)

  // Verify stored token on mount
  useEffect(() => {
    const token = getToken()
    if (!token) { setAuthChecked(true); return }
    authMe()
      .then(u => { setUser(u); setAuthChecked(true) })
      .catch(() => { clearAuth(); setAuthChecked(true) })
  }, [])

  function handleLogin(u) { setUser(u) }
  function handleLogout() { clearAuth(); setUser(null); setConvList([]); setActiveConvId(null) }

  // Health check
  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const r = await fetch('/v1/../health', { signal: AbortSignal.timeout(5000) })
        if (!cancelled) setOnline(r.ok)
      } catch { if (!cancelled) setOnline(false) }
    }
    check()
    const t = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  // Load conversation list on mount
  useEffect(() => { loadConvList() }, [])

  async function loadConvList() {
    try {
      const data = await fetchConversations()
      setConvList(data)
    } catch {}
  }

  async function handleDeleteConv(id) {
    try {
      await deleteConversation(id)
      setConvList(prev => prev.filter(c => c.id !== id))
      if (activeConvId === id) setActiveConvId(null)
    } catch {}
  }

  function handleConvCreated(id, title) {
    setActiveConvId(id)
    setConvList(prev => [
      { id, title, created_at: new Date().toISOString(), msg_count: 0, last_active: null },
      ...prev.filter(c => c.id !== id),
    ])
  }

  function handleRefreshConvList() {
    // Called 3s after a new conv is created so the LLM-generated title lands
    setTimeout(loadConvList, 3000)
  }

  function nav(p) { setPage(p); setSelectedRunId(null) }
  const activePage = page === 'detail' || page === 'new' ? 'runs' : page
  const groups = [...new Set(NAV_BOTTOM.map(n => n.group))]
  const activeConv = convList.find(c => c.id === activeConvId)

  // Show nothing while checking auth
  if (!authChecked) return null

  // Show login page if not authenticated
  if (!user) return <Login onLogin={handleLogin} />

  return (
    <div className="app">
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-mark">OP</div>
            <div className="logo-text">
              <div className="logo-name">OpsPilot</div>
              <div className="logo-tag">AI Copilot</div>
            </div>
          </div>
        </div>

        {/* Chat section — takes available space when on chat page */}
        <div className="sidebar-chat-section">
          {/* Chat nav item */}
          <button
            className={`nav-item${activePage === 'chat' ? ' active' : ''}`}
            onClick={() => nav('chat')}
          >
            <span className="nav-icon">◎</span>
            Chat
          </button>

          {/* Conversations list — only when on chat page */}
          {activePage === 'chat' && (
            <div className="conv-area">
              <button
                className="new-chat-btn"
                onClick={() => { setActiveConvId(null); nav('chat') }}
              >
                + New Chat
              </button>
              <div className="conv-list">
                {convList.map(conv => (
                  <div
                    key={conv.id}
                    className={`conv-item${conv.id === activeConvId ? ' active' : ''}`}
                    onClick={() => { setActiveConvId(conv.id); nav('chat') }}
                    onMouseEnter={() => setHoveredConv(conv.id)}
                    onMouseLeave={() => setHoveredConv(null)}
                  >
                    <div className="conv-item-inner">
                      <span className="conv-title">{conv.title || 'Untitled'}</span>
                      <span className="conv-meta">
                        {timeAgo(conv.last_active || conv.created_at)}
                      </span>
                    </div>
                    {hoveredConv === conv.id && (
                      <button
                        className="conv-delete"
                        onClick={e => { e.stopPropagation(); handleDeleteConv(conv.id) }}
                        title="Delete"
                      >×</button>
                    )}
                  </div>
                ))}
                {convList.length === 0 && (
                  <div style={{ padding: '0.5rem 0.6rem', fontSize: '0.72rem', color: 'var(--text3)' }}>
                    No conversations yet
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Bottom nav groups — Workspace + System */}
        <div className="nav-section">
          {groups.map(group => {
            const items = NAV_BOTTOM.filter(n => n.group === group)
            return (
              <div key={group}>
                <div className="nav-group-label">{GROUP_LABELS[group]}</div>
                {items.map(n => (
                  <button
                    key={n.id}
                    className={`nav-item${activePage === n.id ? ' active' : ''}`}
                    onClick={() => nav(n.id)}
                  >
                    <span className="nav-icon">{n.icon}</span>
                    {n.label}
                  </button>
                ))}
              </div>
            )
          })}
        </div>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text2)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.name || user.email}
            </div>
            <div style={{ fontSize: '0.67rem', color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.email}
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--text3)', fontSize: '0.8rem', padding: '2px 4px',
              borderRadius: 4, flexShrink: 0,
            }}
          >⏻</button>
        </div>

        <div style={{ padding: '0 0.75rem 0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>v0.7</span>
          <span className={`online-badge${online === false ? ' offline' : ''}`} style={{ fontSize: '0.65rem' }}>
            {online === null ? 'Connecting…' : online ? 'Online' : 'Offline'}
          </span>
        </div>
      </aside>

      <main className="content">
        {page === 'chat' && (
          <Chat
            activeConvId={activeConvId}
            setActiveConvId={setActiveConvId}
            convTitle={activeConv?.title || null}
            onConvCreated={handleConvCreated}
            onRefreshConvList={handleRefreshConvList}
          />
        )}
        {page === 'runs' && (
          <RunList
            onSelect={id => { setSelectedRunId(id); setPage('detail') }}
            onNew={() => setPage('new')}
          />
        )}
        {page === 'detail'    && selectedRunId && <RunDetail runId={selectedRunId} onBack={() => nav('runs')} />}
        {page === 'new'       && <NewRun onDone={id => { setSelectedRunId(id); setPage('detail') }} onBack={() => nav('runs')} />}
        {page === 'approvals' && <ApprovalPanel />}
        {page === 'documents' && <Documents />}
        {page === 'tools'     && <ToolsPanel />}
        {page === 'slack'     && <SlackFeatures />}
        {page === 'settings'  && <Settings />}
      </main>
    </div>
  )
}
