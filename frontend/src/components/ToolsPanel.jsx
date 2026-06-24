import { useEffect, useState } from 'react'
import { fetchMcpTools } from '../api'

const SERVER_COLORS = {
  github:     '#2563eb',
  ops:        '#dc2626',
  rag:        '#0891b2',
  slack:      '#059669',
  search:     '#d97706',
  monitoring: '#7c3aed',
}

export default function ToolsPanel() {
  const [tools, setTools]     = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    fetchMcpTools()
      .then(setTools)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const servers = [...new Set(tools.map(t => t.server))]

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Tool Registry</div>
        <div className="page-subtitle">{tools.length} tools · {servers.length} servers</div>
      </div>

      {loading && (
        <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', color:'var(--text3)' }}>
          <div className="spinner" /> Loading…
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {servers.map(server => {
        const color  = SERVER_COLORS[server] || 'var(--text2)'
        const sTools = tools.filter(t => t.server === server)
        return (
          <div key={server} style={{ marginBottom:'2rem' }}>
            <div className="server-header">
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: color, flexShrink: 0,
                display: 'inline-block',
              }} />
              <span style={{ color }}>{server}</span>
              <span>{sTools.length} tool{sTools.length !== 1 ? 's' : ''}</span>
            </div>
            <div className="tools-grid">
              {sTools.map(t => (
                <div key={t.name} className="tool-card">
                  <div className="row" style={{ marginBottom:'0.35rem' }}>
                    <div className="tool-card-name">{t.name}</div>
                    {t.sensitive && (
                      <span className="badge awaiting_approval" style={{ fontSize:'0.62rem' }}>
                        <span className="bdot" />sensitive
                      </span>
                    )}
                  </div>
                  <div className="tool-card-desc">{t.description}</div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
