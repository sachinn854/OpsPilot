import { useEffect, useState } from 'react'
import RunList from './components/RunList'
import RunDetail from './components/RunDetail'
import ApprovalPanel from './components/ApprovalPanel'
import NewRun from './components/NewRun'
import ToolsPanel from './components/ToolsPanel'
import Documents from './components/Documents'
import Chat from './components/Chat'
import Settings from './components/Settings'
import './App.css'

const NAV = [
  { id: 'chat',      icon: '◎', label: 'Chat',      group: 'Assistant' },
  { id: 'runs',      icon: '⊞', label: 'Runs',      group: 'Agent Runs' },
  { id: 'new',       icon: '⊕', label: 'New Run',   group: 'Agent Runs' },
  { id: 'approvals', icon: '◈', label: 'Approvals', group: 'Agent Runs' },
  { id: 'documents', icon: '⊡', label: 'Documents', group: 'Knowledge' },
  { id: 'tools',     icon: '⊙', label: 'Tools',     group: 'System'    },
  { id: 'settings',  icon: '⚙', label: 'Settings',  group: 'System'    },
]

export default function App() {
  const [page, setPage]           = useState('chat')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [online, setOnline]       = useState(null)  // null = checking, true/false

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const r = await fetch('/v1/../health', { signal: AbortSignal.timeout(5000) })
        if (!cancelled) setOnline(r.ok)
      } catch {
        if (!cancelled) setOnline(false)
      }
    }
    check()
    const t = setInterval(check, 30_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  function nav(p) { setPage(p); setSelectedRunId(null) }
  const activePage = page === 'detail' ? 'runs' : page
  const defaultPage = 'chat'

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-mark">⚙</div>
            <div className="logo-text">
              <div className="logo-name">OpsPilot</div>
              <div className="logo-tag">AI Copilot</div>
            </div>
          </div>
        </div>

        <div className="nav-section">
          {['Assistant', 'Agent Runs', 'Knowledge', 'System'].map(group => {
            const items = NAV.filter(n => n.group === group)
            return (
              <div key={group}>
                <div className="nav-group-label">{group}</div>
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
          <span>v0.7</span>
          <span className={`online-badge${online === false ? ' offline' : ''}`}>
            {online === null ? 'Connecting…' : online ? 'Online' : 'Offline'}
          </span>
        </div>
      </aside>

      <main className="content">
        {page === 'chat'      && <Chat />}
        {page === 'runs'      && <RunList onSelect={id => { setSelectedRunId(id); setPage('detail') }} />}
        {page === 'detail'    && selectedRunId && <RunDetail runId={selectedRunId} onBack={() => nav('runs')} />}
        {page === 'new'       && <NewRun onDone={id => { setSelectedRunId(id); setPage('detail') }} />}
        {page === 'approvals' && <ApprovalPanel />}
        {page === 'documents' && <Documents />}
        {page === 'tools'     && <ToolsPanel />}
        {page === 'settings'  && <Settings />}
      </main>
    </div>
  )
}
