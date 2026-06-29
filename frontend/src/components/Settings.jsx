import { useEffect, useState } from 'react'
import { apiFetch } from '../api'

const SERVICES = [
  {
    id: 'github',
    label: 'GitHub',
    icon: '⊙',
    description: 'Connect your GitHub account to access repos, issues, PRs, and code.',
    placeholder: 'ghp_xxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://github.com/settings/tokens',
    docsLabel: 'Generate a token →',
  },
  {
    id: 'slack',
    label: 'Slack',
    icon: '◈',
    description: 'Connect Slack to send messages and alerts to your workspace.',
    placeholder: 'xoxb-xxxxxxxxxxxx',
    docsUrl: 'https://api.slack.com/apps',
    docsLabel: 'Create a Slack app →',
  },
  {
    id: 'jira',
    label: 'Jira',
    icon: '⊞',
    description: 'Connect Jira to manage tickets and sprints.',
    placeholder: 'your-jira-api-token',
    docsUrl: 'https://id.atlassian.com/manage-profile/security/api-tokens',
    docsLabel: 'Generate Atlassian token →',
  },
  {
    id: 'linear',
    label: 'Linear',
    icon: '⊕',
    description: 'Connect Linear to track issues and roadmap.',
    placeholder: 'lin_api_xxxxxxxxxxxx',
    docsUrl: 'https://linear.app/settings/api',
    docsLabel: 'Generate Linear token →',
  },
]

export default function Settings() {
  const [connected, setConnected] = useState({})   // { github: { username, ... }, ... }
  const [inputs, setInputs]       = useState({})   // { github: 'ghp_...' }
  const [busy, setBusy]           = useState({})   // { github: true }
  const [errors, setErrors]       = useState({})
  const [success, setSuccess]     = useState({})

  useEffect(() => { loadConnected() }, [])

  async function loadConnected() {
    try {
      const rows = await apiFetch('/v1/integrations')
      const map = {}
      for (const r of rows) map[r.service] = r
      setConnected(map)
    } catch { /* silent — backend may be down */ }
  }

  async function handleConnect(serviceId) {
    const token = (inputs[serviceId] || '').trim()
    if (!token) return
    setBusy(b => ({ ...b, [serviceId]: true }))
    setErrors(e => ({ ...e, [serviceId]: '' }))
    setSuccess(s => ({ ...s, [serviceId]: '' }))
    try {
      const result = await apiFetch(`/v1/integrations/${serviceId}`, {
        method: 'POST',
        body: JSON.stringify({ token }),
      })
      setConnected(c => ({ ...c, [serviceId]: result }))
      setInputs(i => ({ ...i, [serviceId]: '' }))
      setSuccess(s => ({ ...s, [serviceId]: 'Connected successfully!' }))
    } catch (e) {
      setErrors(er => ({ ...er, [serviceId]: e.message }))
    } finally {
      setBusy(b => ({ ...b, [serviceId]: false }))
    }
  }

  async function handleDisconnect(serviceId) {
    if (!window.confirm(`Disconnect ${serviceId}? The stored token will be deleted.`)) return
    setBusy(b => ({ ...b, [serviceId]: true }))
    try {
      await apiFetch(`/v1/integrations/${serviceId}`, { method: 'DELETE' })
      setConnected(c => { const n = { ...c }; delete n[serviceId]; return n })
      setSuccess(s => ({ ...s, [serviceId]: 'Disconnected.' }))
    } catch (e) {
      setErrors(er => ({ ...er, [serviceId]: e.message }))
    } finally {
      setBusy(b => ({ ...b, [serviceId]: false }))
    }
  }

  async function handleVerify(serviceId) {
    setBusy(b => ({ ...b, [serviceId]: true }))
    setSuccess(s => ({ ...s, [serviceId]: '' }))
    setErrors(e => ({ ...e, [serviceId]: '' }))
    try {
      const result = await apiFetch(`/v1/integrations/${serviceId}/verify`)
      if (result.valid) {
        setSuccess(s => ({ ...s, [serviceId]: `Token valid ✓ ${result.meta?.username || result.meta?.user || ''}` }))
      } else {
        setErrors(er => ({ ...er, [serviceId]: `Token invalid: ${result.reason}` }))
      }
    } catch (e) {
      setErrors(er => ({ ...er, [serviceId]: e.message }))
    } finally {
      setBusy(b => ({ ...b, [serviceId]: false }))
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Settings</div>
        <div className="page-subtitle">Connect external services to unlock more capabilities</div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', maxWidth: 640 }}>

        {/* Webhook info card */}
        <div className="card static" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '1.1rem', color: 'var(--accent)' }}>⊛</span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>GitHub Webhooks</span>
            <span className="badge" style={{ fontSize: '0.65rem', background: 'var(--surface3)', color: 'var(--text2)' }}>
              real-time events
            </span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text2)', marginBottom: '0.75rem' }}>
            Receive live GitHub events (push, pull requests, issues, releases) directly into the copilot.
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text3)', lineHeight: 1.7 }}>
            <div style={{ marginBottom: '0.4rem', color: 'var(--text2)', fontWeight: 500 }}>Setup steps:</div>
            <ol style={{ margin: 0, paddingLeft: '1.2rem' }}>
              <li>Set <code style={{ background: 'var(--surface3)', padding: '0 4px', borderRadius: 3 }}>GITHUB_WEBHOOK_SECRET</code> in your <code style={{ background: 'var(--surface3)', padding: '0 4px', borderRadius: 3 }}>.env</code></li>
              <li>Go to your GitHub repo → Settings → Webhooks → Add webhook</li>
              <li>Payload URL: <code style={{ background: 'var(--surface3)', padding: '0 4px', borderRadius: 3 }}>https://&lt;your-domain&gt;/v1/webhooks/github</code></li>
              <li>Content type: <code style={{ background: 'var(--surface3)', padding: '0 4px', borderRadius: 3 }}>application/json</code> · paste the same secret</li>
              <li>Select events: push, pull requests, issues, releases</li>
            </ol>
          </div>
        </div>

        {SERVICES.map(svc => {
          const isConnected = !!connected[svc.id]
          const meta = connected[svc.id]?.meta || {}
          const isBusy = !!busy[svc.id]

          return (
            <div key={svc.id} className="card static" style={{ padding: '1.25rem' }}>
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span style={{ fontSize: '1.1rem', color: 'var(--accent)' }}>{svc.icon}</span>
                  <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{svc.label}</span>
                  {isConnected && (
                    <span className="badge completed" style={{ fontSize: '0.65rem' }}>
                      <span className="bdot" />connected
                    </span>
                  )}
                </div>
                {isConnected && (
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                      disabled={isBusy}
                      onClick={() => handleVerify(svc.id)}
                    >
                      {isBusy ? <div className="spinner" style={{ width: 11, height: 11, borderWidth: 2 }} /> : '↻ Verify'}
                    </button>
                    <button
                      className="btn btn-danger"
                      style={{ padding: '0.3rem 0.65rem', fontSize: '0.75rem' }}
                      disabled={isBusy}
                      onClick={() => handleDisconnect(svc.id)}
                    >
                      Disconnect
                    </button>
                  </div>
                )}
              </div>

              {/* Description */}
              <div style={{ fontSize: '0.8rem', color: 'var(--text2)', marginBottom: '0.75rem' }}>
                {svc.description}
              </div>

              {/* Connected meta */}
              {isConnected && (meta.username || meta.user || meta.team) && (
                <div style={{
                  fontSize: '0.78rem', color: 'var(--green)',
                  background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                  borderRadius: 'var(--r-xs)', padding: '0.4rem 0.7rem',
                  marginBottom: '0.75rem',
                }}>
                  {meta.username && <>@{meta.username}</>}
                  {meta.user && <> · {meta.user}</>}
                  {meta.team && <> · {meta.team}</>}
                  {meta.name && <> · {meta.name}</>}
                  {meta.source === 'env' && ' (from .env)'}
                </div>
              )}

              {/* Token input (shown when disconnected) */}
              {!isConnected && (
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
                  <div className="field" style={{ flex: 1, marginBottom: 0 }}>
                    <input
                      type="password"
                      placeholder={svc.placeholder}
                      value={inputs[svc.id] || ''}
                      onChange={e => setInputs(i => ({ ...i, [svc.id]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && handleConnect(svc.id)}
                      disabled={isBusy}
                    />
                  </div>
                  <button
                    className="btn btn-primary"
                    style={{ flexShrink: 0, alignSelf: 'flex-end', marginBottom: '1.1rem', padding: '0.55rem 1rem' }}
                    disabled={isBusy || !inputs[svc.id]?.trim()}
                    onClick={() => handleConnect(svc.id)}
                  >
                    {isBusy
                      ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Connecting…</>
                      : 'Connect'}
                  </button>
                </div>
              )}

              {/* Docs link */}
              {!isConnected && (
                <div style={{ fontSize: '0.73rem', color: 'var(--text3)', marginTop: '0.3rem' }}>
                  <a href={svc.docsUrl} target="_blank" rel="noreferrer"
                    style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                    {svc.docsLabel}
                  </a>
                </div>
              )}

              {/* Success / error messages */}
              {success[svc.id] && (
                <div style={{ fontSize: '0.78rem', color: 'var(--green)', marginTop: '0.5rem' }}>
                  {success[svc.id]}
                </div>
              )}
              {errors[svc.id] && (
                <div className="error" style={{ marginTop: '0.5rem', fontSize: '0.78rem' }}>
                  {errors[svc.id]}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
