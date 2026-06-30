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
  { id: 'chat',      icon: '◎', label: 'Chat',      group: 'main' },
  { id: 'runs',      icon: '▶', label: 'Runs',      group: 'ops'  },
  { id: 'approvals', icon: '◈', label: 'Approvals', group: 'ops'  },
  { id: 'documents', icon: '⊡', label: 'Documents', group: 'ops'  },
  { id: 'tools',     icon: '⊙', label: 'Tools',     group: 'sys'  },
  { id: 'settings',  icon: '⚙', label: 'Settings',  group: 'sys'  },
]

const GROUP_LABELS = {
  main: null,      // no label for top item
  ops:  'Workspace',
  sys:  'System',
}

export default function App() {
  const [page, setPage]                   = useState('chat')
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [online, setOnline]               = useState(null)

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
  const activePage = page === 'detail' || page === 'new' ? 'runs' : page

  const groups = [...new Set(NAV.map(n => n.group))]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-mark">OP</div>
            <div className="logo-text">
              <div className="logo-name">OpsPilot</div>
              <div className="logo-tag">AI Copilot</div>
            </div>
          </div>
        </div>

        <div className="nav-section">
          {groups.map(group => {
            const items = NAV.filter(n => n.group === group)
            const label = GROUP_LABELS[group]
            return (
              <div key={group}>
                {label && <div className="nav-group-label">{label}</div>}
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
        {page === 'runs'      && (
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
        {page === 'settings'  && <Settings />}
      </main>
    </div>
  )
}
