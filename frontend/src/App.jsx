import { useEffect, useRef, useState } from 'react'
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

// ── Inline SVG icons (no extra deps) ──
const Ico = {
  chat:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><rect x="2" y="3" width="12" height="8" rx="3" stroke="currentColor" strokeWidth="1.3"/><path d="M6 11l-1.5 2 2-1.2" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/></svg>,
  play:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M5 3.5l7 4.5-7 4.5z" fill="currentColor" opacity="0.95" stroke="currentColor" strokeWidth="0.9" strokeLinejoin="round"/></svg>,
  shield:     (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M8 2.2L3.2 4.3v3.7c0 2.55 1.55 4.35 4.8 5.8 3.25-1.45 4.8-3.25 4.8-5.8V4.3L8 2.2z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/><path d="M6.2 8l1.5 1.5 2.8-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  doc:        (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M5 2.5h5l3 3V13a1 1 0 01-1 1H5a1 1 0 01-1-1V3.5a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round"/><path d="M10 2.7v2.8H12.8" stroke="currentColor" strokeWidth="1.15" strokeLinejoin="round"/><path d="M6.5 9.5h3M6.5 7h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></svg>,
  grid:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><rect x="2.5" y="2.5" width="4.2" height="4.2" rx="1.2" stroke="currentColor" strokeWidth="1.25"/><rect x="9.3" y="2.5" width="4.2" height="4.2" rx="1.2" stroke="currentColor" strokeWidth="1.25"/><rect x="2.5" y="9.3" width="4.2" height="4.2" rx="1.2" stroke="currentColor" strokeWidth="1.25"/><rect x="9.3" y="9.3" width="4.2" height="4.2" rx="1.2" stroke="currentColor" strokeWidth="1.25"/></svg>,
  hash:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M6 2.5l-1 11M10 2.5l-1 11M3 6.5h10M3 9.5h10" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round"/></svg>,
  gear:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><circle cx="8" cy="8" r="2.6" stroke="currentColor" strokeWidth="1.25"/><path d="M8 2.2v1.6M8 12.2v1.6M2.2 8H3.8M12.2 8H13.8M4.1 4.1l1.15 1.15M10.75 10.75l1.15 1.15M11.9 4.1l-1.15 1.15M5.25 10.75L4.1 11.9" stroke="currentColor" strokeWidth="1.15" strokeLinecap="round"/></svg>,
  spark:      (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M8 2l1.2 3.2L12.5 6.5l-3.3 1.1L8 11l-1.2-3.4L3.5 6.5l3.3-1.3L8 2z" fill="currentColor" opacity="0.95"/><circle cx="13" cy="3" r="1" fill="currentColor"/><circle cx="3.2" cy="10.5" r="0.9" fill="currentColor" opacity="0.7"/></svg>,
  menu:       (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M3 5h10M3 8h10M3 11h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  close:      (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M4 4l8 8M12 4L4 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  logout:     (p) => <svg viewBox="0 0 16 16" fill="none" {...p}><path d="M6 3.5H4.2A1.2 1.2 0 003 4.7v6.6A1.2 1.2 0 004.2 12.5H6" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round"/><path d="M10.5 8H3.5M9 5.5L11.5 8 9 10.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round"/></svg>,
}

const NAV_WORKSPACE = [
  { id: 'runs',      label: 'Runs',      Icon: Ico.play   },
  { id: 'approvals', label: 'Approvals', Icon: Ico.shield },
  { id: 'documents', label: 'Documents', Icon: Ico.doc    },
]
const NAV_SYSTEM = [
  { id: 'tools',    label: 'Tools',    Icon: Ico.grid },
  { id: 'slack',    label: 'Slack',    Icon: Ico.hash },
  { id: 'settings', label: 'Settings', Icon: Ico.gear },
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
  const [sidebarOpen, setSidebarOpen]     = useState(false)
  const [userMenuOpen, setUserMenuOpen]   = useState(false)
  const menuRef = useRef(null)

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
  function handleRefreshConvList() { setTimeout(loadConvList, 3000) }

  function nav(p) { setPage(p); setSelectedRunId(null); setSidebarOpen(false) }
  const activePage = page === 'detail' || page === 'new' ? 'runs' : page
  const activeConv = convList.find(c => c.id === activeConvId)
  const isChat = page === 'chat'
  const userInitial = ((user?.name || user?.email || '?')[0]).toUpperCase()
  const userName    = user?.name || user?.email?.split('@')[0] || ''

  // close drawer/menu on Esc or outside click
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') { setSidebarOpen(false); setUserMenuOpen(false) } }
    function onDown(e) { if (menuRef.current && !menuRef.current.contains(e.target)) setUserMenuOpen(false) }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onDown)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('mousedown', onDown) }
  }, [])

  if (!authChecked) return (
    <div style={{ height: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg)', color: 'var(--text3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}><div className="spinner" /> Loading…</div>
    </div>
  )
  if (!user) return <Login onLogin={handleLogin} />

  const pageTitle = PAGE_LABELS[page] || PAGE_LABELS[activePage] || 'OpsPilot'

  return (
    <div className="app">
      {/* Mobile overlay */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      {/* ── Sidebar ── */}
      <aside className={`sidebar${sidebarOpen ? ' open' : ''}`}>
        <div className="sidebar-head">
          <div className="logo">
            <div className="logo-mark">OP</div>
            <div>
              <div className="logo-name">OpsPilot</div>
              <div className="logo-tag">AI Copilot</div>
            </div>
          </div>
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(v => !v)} aria-label="Toggle sidebar" title="Toggle">
            <span style={{ display: 'grid', placeItems: 'center', width: 14, height: 14 }}>{sidebarOpen ? <Ico.close /> : <Ico.menu />}</span>
          </button>
        </div>

        {/* Chat + conversation list */}
        <div className="sidebar-chat-section">
          <button
            id="tour-chat"
            className={`nav-item${activePage === 'chat' ? ' active' : ''}`}
            onClick={() => nav('chat')}
          >
            <span className="nav-icon"><Ico.chat /></span>
            Chat
            <span style={{ marginLeft: 'auto', fontSize: '0.62rem', color: 'var(--text3)', background: 'var(--surface3)', border: '1px solid var(--border)', borderRadius: 6, padding: '1px 5px', fontFamily: 'JetBrains Mono, monospace' }}>{convList.length}</span>
          </button>

          {activePage === 'chat' && (
            <div className="conv-area">
              <button className="new-chat-btn" onClick={() => { setActiveConvId(null); nav('chat') }}>
                <span style={{ fontSize: '0.92rem', lineHeight: 1 }}>＋</span> New Chat
                <span style={{ marginLeft: 'auto', opacity: 0.55, fontSize: '0.68rem', fontFamily: 'JetBrains Mono, monospace' }}>⌘ N</span>
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
                    {(hoveredConv === conv.id) && (
                      <button className="conv-delete" onClick={e => { e.stopPropagation(); handleDeleteConv(conv.id) }} title="Delete">×</button>
                    )}
                  </div>
                ))}
                {convList.length === 0 && (
                  <div style={{ padding: '0.7rem 0.6rem', fontSize: '0.72rem', color: 'var(--text3)', textAlign: 'center', border: '1px dashed var(--border2)', borderRadius: 9, marginTop: '0.35rem' }}>
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
              <span className="nav-icon"><n.Icon /></span>
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
              <span className="nav-icon"><n.Icon /></span>
              {n.label}
            </button>
          ))}
        </nav>

        <button className="tour-link" onClick={() => setShowTour(true)}>
          <span style={{ width: 14, height: 14, display: 'grid', placeItems: 'center' }}><Ico.spark /></span> Take a tour
        </button>

        <div className="sidebar-foot">
          <div className="user-avatar">{userInitial}</div>
          <div className="user-meta">
            <span className="user-name">{userName}</span>
            <span className="user-email">{user.email}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Sign out"><Ico.logout /></button>
        </div>
      </aside>

      {showTour && <Tour onComplete={() => setShowTour(false)} />}

      {/* ── Content ── */}
      <main className="content">
        <header className="topbar">
          <div className="topbar-left">
            <button className="hamburger" onClick={() => setSidebarOpen(v => !v)} aria-label="Menu">
              <Ico.menu />
            </button>
            <span className="topbar-title">{pageTitle}</span>
            {isChat && activeConv?.title && <span className="topbar-subtitle">{activeConv.title}</span>}
          </div>
          <div className="topbar-right">
            <span className="topbar-search-hint" title="Press ⌘K to search">
              <span style={{ opacity: 0.7 }}>⌘</span> K
              <span className="kbd">↵</span>
              <span style={{ color: 'var(--text3)' }}>to search</span>
            </span>
            {online !== null && (
              <span className={`status-pill${online ? '' : ' offline'}`}>{online ? 'Online' : 'Offline'}</span>
            )}
            <div ref={menuRef} style={{ position:'relative' }}>
              <div
                className="topbar-user"
                onClick={() => setUserMenuOpen(v=>!v)}
                role="button"
                tabIndex={0}
                onKeyDown={e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); setUserMenuOpen(v=>!v) } }}
                title={`${userName} — ${user.email}`}
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                style={{ cursor:'pointer' }}
              >
                <div className="user-avatar" style={{ width: 24, height: 24, fontSize: '0.60rem' }}>{userInitial}</div>
                <span className="topbar-user-name">{userName}</span>
                <span style={{ fontSize:'0.62rem', color:'var(--text3)', marginLeft:'0.15rem', transition:'transform 0.15s', transform: userMenuOpen?'rotate(180deg)':'none' }}>▾</span>
              </div>
              {userMenuOpen && (
                <div
                  role="menu"
                  style={{
                    position:'absolute', right:0, top:'calc(100% + 8px)', minWidth:220,
                    background:'var(--surface)', border:'1px solid var(--border2)', borderRadius:12,
                    boxShadow:'0 12px 32px rgba(0,0,0,0.45), 0 2px 8px rgba(0,0,0,0.25)',
                    padding:'0.45rem', zIndex:20,
                  }}
                >
                  <div style={{ padding:'0.6rem 0.65rem 0.55rem', borderBottom:'1px solid var(--border)', marginBottom:'0.35rem' }}>
                    <div style={{ fontSize:'0.82rem', fontWeight:650, color:'var(--text)', lineHeight:1.2 }}>{userName}</div>
                    <div style={{ fontSize:'0.72rem', color:'var(--text3)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{user.email}</div>
                  </div>
                  <button
                    role="menuitem"
                    onClick={()=>{ setUserMenuOpen(false); nav('settings') }}
                    style={{
                      width:'100%', display:'flex', alignItems:'center', gap:'0.5rem',
                      background:'none', border:'none', borderRadius:8, cursor:'pointer',
                      padding:'0.5rem 0.6rem', color:'var(--text2)', fontSize:'0.82rem', fontFamily:'Inter, sans-serif', textAlign:'left',
                    }}
                    onMouseEnter={e=>{ e.currentTarget.style.background='var(--surface2)'; e.currentTarget.style.color='var(--text)' }}
                    onMouseLeave={e=>{ e.currentTarget.style.background='none'; e.currentTarget.style.color='var(--text2)' }}
                  >
                    <span style={{ width:16, height:16, display:'grid', placeItems:'center' }}><Ico.gear /></span> Settings
                  </button>
                  <button
                    role="menuitem"
                    onClick={()=>{ setUserMenuOpen(false); handleLogout() }}
                    style={{
                      width:'100%', display:'flex', alignItems:'center', gap:'0.5rem',
                      background:'none', border:'none', borderRadius:8, cursor:'pointer',
                      padding:'0.5rem 0.6rem', color:'var(--red)', fontSize:'0.82rem', fontFamily:'Inter, sans-serif', textAlign:'left',
                    }}
                    onMouseEnter={e=>e.currentTarget.style.background='var(--red-dim)'}
                    onMouseLeave={e=>e.currentTarget.style.background='none'}
                  >
                    <span style={{ width:16, height:16, display:'grid', placeItems:'center' }}><Ico.logout /></span> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

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
            {page === 'runs' && <RunList onSelect={id => { setSelectedRunId(id); setPage('detail') }} onNew={() => setPage('new')} />}
            {page === 'detail' && selectedRunId && <RunDetail runId={selectedRunId} onBack={() => nav('runs')} />}
            {page === 'new'    && <NewRun onDone={id => { setSelectedRunId(id); setPage('detail') }} onBack={() => nav('runs')} />}
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
