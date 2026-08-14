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
import Tour from './components/Tour'
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

const PAGE_LABELS = {
  chat:      'Chat',
  runs:      'Runs',
  new:       'New Run',
  detail:    'Run Detail',
  approvals: 'Approvals',
  documents: 'Documents',
  tools:     'Tools',
  slack:     'Slack',
  settings:  'Settings',
}

const NAV_WORKSPACE = [
  { id: 'runs',      icon: '▶', label: 'Runs'      },
  { id: 'approvals', icon: '◈', label: 'Approvals' },
  { id: 'documents', icon: '⊡', label: 'Documents' },
]

const NAV_SYSTEM = [
  { id: 'tools',    icon: '⊙', label: 'Tools'    },
  { id: 'slack',    icon: '#', label: 'Slack'     },
  { id: 'settings', icon: '⚙', label: 'Settings' },
]

export default function App() {
  const [page, setPage]                   = useState('chat')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [online, setOnline]               = useState(null)
  const [showTour, setShowTour]           = useState(false)
  const [user, setUser]                   = useState(null)
  const [authChecked, setAuthChecked]     = useState(false)
  const [convList, setConvList]           = useState([])
  const [activeConvId, setActiveConvId]   = useState(null)
  const [hoveredConv, setHoveredConv]     = useState(null)

  useEffect(() => {
    const token = getToken()
    if (!token) { setAuthChecked(true); return }
    authMe()
      .then(u => { setUser(u); setAuthChecked(true) })
      .catch(() => { clearAuth(); setAuthChecked(true) })
  }, [])

  function handleLogin(u) {
    setUser(u)
    if (!localStorage.getItem('opspilot_tour_done')) setShowTour(true)
  }
  function handleLogout() { clearAuth(); setUser(null); setConvList([]); setActiveConvId(null) }

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const r = await fetch(`${import.meta.env.VITE_API_URL || ''}/health`, { signal: AbortSignal.timeout(5000) })
        if (!cancelled) setOnline(r.ok)
      } catch { if (!cancelled) setOnline(false) }
    }
    check()
    const t = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  useEffect(() => { loadConvList() }, [])

  async function loadConvList() {
    try { setConvList(await fetchConversations()) } catch {}
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
    setTimeout(loadConvList, 3000)
  }

  function nav(p) { setPage(p); setSelectedRunId(null) }
  const activePage = page === 'detail' || page === 'new' ? 'runs' : page
  const activeConv = convList.find(c => c.id === activeConvId)
  const isChat = page === 'chat'

  const userInitial = ((user?.name || user?.email || '?')[0]).toUpperCase()
  const userName    = user?.name || user?.email?.split('@')[0] || ''

  if (!authChecked) return null
  if (!user) return <Login onLogin={handleLogin} />

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">

        {/* Logo */}
        <div className="sidebar-head">
          <div className="logo">
            <div className="logo-mark">OP</div>
            <div>
              <div className="logo-name">OpsPilot</div>
              <div className="logo-tag">AI Copilot</div>
            </div>
          </div>
        </div>

        {/* Chat + conversation list */}
        <div className="sidebar-chat-section">
          <button
            id="tour-chat"
            className={`nav-item${activePage === 'chat' ? ' active' : ''}`}
            onClick={() => nav('chat')}
          >
            <span className="nav-icon">◎</span>
            Chat
          </button>

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
                      <span className="conv-meta">{timeAgo(conv.last_active || conv.created_at)}</span>
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
                  <div style={{ padding: '0.5rem 0.6rem', fontSize: '0.7rem', color: 'var(--text3)' }}>
                    No conversations yet
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Nav groups */}
        <nav className="sidebar-nav">
          <span className="nav-group-label">Workspace</span>
          {NAV_WORKSPACE.map(n => (
            <button
              key={n.id}
              id={`tour-${n.id}`}
              className={`nav-item${activePage === n.id ? ' active' : ''}`}
              onClick={() => nav(n.id)}
            >
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </button>
          ))}

          <span className="nav-group-label">System</span>
          {NAV_SYSTEM.map(n => (
            <button
              key={n.id}
              id={`tour-${n.id}`}
              className={`nav-item${activePage === n.id ? ' active' : ''}`}
              onClick={() => nav(n.id)}
            >
              <span className="nav-icon">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>

        {/* Tour */}
        <button className="tour-link" onClick={() => setShowTour(true)}>
          ⊙ Take a tour
        </button>

        {/* User footer */}
        <div className="sidebar-foot">
          <div className="user-avatar">{userInitial}</div>
          <div className="user-meta">
            <span className="user-name">{userName}</span>
            <span className="user-email">{user.email}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Sign out">⏻</button>
        </div>
      </aside>

      {showTour && <Tour onComplete={() => setShowTour(false)} />}

      {/* ── Content ── */}
      <main className="content">

        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="topbar-title">
              {PAGE_LABELS[page] || PAGE_LABELS[activePage] || 'OpsPilot'}
            </span>
            {isChat && activeConv?.title && (
              <span className="topbar-conv">— {activeConv.title}</span>
            )}
          </div>
          <div className="topbar-right">
            {online !== null && (
              <span className={`status-pill${online ? '' : ' offline'}`}>
                {online ? 'Online' : 'Offline'}
              </span>
            )}
            <div className="topbar-user" onClick={handleLogout} title="Sign out">
              <div className="user-avatar" style={{ width: 22, height: 22, fontSize: '0.58rem' }}>
                {userInitial}
              </div>
              <span className="topbar-user-name">{userName}</span>
            </div>
          </div>
        </header>

        {/* Page content */}
        {isChat ? (
          <div className="chat-outer">
            <Chat
              activeConvId={activeConvId}
              setActiveConvId={setActiveConvId}
              convTitle={activeConv?.title || null}
              onConvCreated={handleConvCreated}
              onRefreshConvList={handleRefreshConvList}
            />
          </div>
        ) : (
          <div className="page-body">
            {page === 'runs' && (
              <RunList
                onSelect={id => { setSelectedRunId(id); setPage('detail') }}
                onNew={() => setPage('new')}
              />
            )}
            {page === 'detail' && selectedRunId && <RunDetail runId={selectedRunId} onBack={() => nav('runs')} />}
            {page === 'new'       && <NewRun onDone={id => { setSelectedRunId(id); setPage('detail') }} onBack={() => nav('runs')} />}
            {page === 'approvals' && <ApprovalPanel />}
            {page === 'documents' && <Documents />}
            {page === 'tools'     && <ToolsPanel />}
            {page === 'slack'     && <SlackFeatures />}
            {page === 'settings'  && <Settings />}
          </div>
        )}
      </main>
    </div>
  )
}
