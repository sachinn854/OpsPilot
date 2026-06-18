import { useEffect, useState } from 'react'
import { fetchMcpTools } from '../api'

const SERVER_COLORS = {
  github:     '#818cf8',
  ops:        '#f87171',
  rag:        '#22d3ee',
  slack:      '#34d399',
  search:     '#f59e0b',
  monitoring: '#a78bfa',
}

export default function ToolsPanel() {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchMcpTools()
      .then(setTools)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="muted">Loading…</p>
  if (error)   return <p className="error">{error}</p>

  const servers = [...new Set(tools.map(t => t.server))]

  return (
    <div>
      <h1>Registered Tools ({tools.length})</h1>
      {servers.map(server => (
        <div key={server} style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ color: SERVER_COLORS[server] || '#818cf8', marginBottom: '0.75rem' }}>
            {server}
          </h2>
          <div className="tools-grid">
            {tools.filter(t => t.server === server).map(t => (
              <div key={t.name} className="card no-hover">
                <div className="row">
                  <strong style={{ fontSize: '0.875rem' }}>{t.name}</strong>
                  {t.sensitive && (
                    <span className="badge awaiting_approval" style={{ fontSize: '0.65rem' }}>sensitive</span>
                  )}
                </div>
                <p className="muted" style={{ marginTop: '0.35rem', fontSize: '0.8rem' }}>{t.description}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
