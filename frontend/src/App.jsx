import { useState } from 'react'
import RunList from './components/RunList'
import RunDetail from './components/RunDetail'
import ApprovalPanel from './components/ApprovalPanel'
import NewRun from './components/NewRun'
import ToolsPanel from './components/ToolsPanel'
import './App.css'

export default function App() {
  const [page, setPage] = useState('runs')
  const [selectedRunId, setSelectedRunId] = useState(null)

  function nav(p) {
    setPage(p)
    setSelectedRunId(null)
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">⚙ OpsPilot</div>
        <nav>
          <button className={page === 'runs' || page === 'detail' ? 'active' : ''} onClick={() => nav('runs')}>Runs</button>
          <button className={page === 'new' ? 'active' : ''} onClick={() => nav('new')}>New Run</button>
          <button className={page === 'approvals' ? 'active' : ''} onClick={() => nav('approvals')}>Approvals</button>
          <button className={page === 'tools' ? 'active' : ''} onClick={() => nav('tools')}>Tools</button>
        </nav>
      </aside>

      <main className="content">
        {page === 'runs' && (
          <RunList onSelect={id => { setSelectedRunId(id); setPage('detail') }} />
        )}
        {page === 'detail' && selectedRunId && (
          <RunDetail runId={selectedRunId} onBack={() => nav('runs')} />
        )}
        {page === 'new' && (
          <NewRun onDone={id => { setSelectedRunId(id); setPage('detail') }} />
        )}
        {page === 'approvals' && <ApprovalPanel />}
        {page === 'tools' && <ToolsPanel />}
      </main>
    </div>
  )
}
