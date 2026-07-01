import { useEffect, useState } from 'react'
import { BASE, apiFetch } from '../api'

// ── Keyword Alerts ─────────────────────────────────────────────────────────

function KeywordAlerts() {
  const [alerts, setAlerts]     = useState([])
  const [keyword, setKeyword]   = useState('')
  const [channels, setChannels] = useState('')
  const [via, setVia]           = useState('both')
  const [busy, setBusy]         = useState(false)
  const [error, setError]       = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    try { setAlerts(await apiFetch(`${BASE}/slack/alerts`)) } catch {}
  }

  async function add() {
    if (!keyword.trim()) return
    setBusy(true); setError('')
    try {
      const a = await apiFetch(`${BASE}/slack/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: keyword.trim(), channels, notify_via: via }),
      })
      setAlerts(prev => [a, ...prev])
      setKeyword(''); setChannels('')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  async function toggle(id) {
    try {
      const updated = await apiFetch(`${BASE}/slack/alerts/${id}`, { method: 'PATCH' })
      setAlerts(prev => prev.map(a => a.id === id ? updated : a))
    } catch {}
  }

  async function remove(id) {
    try {
      await apiFetch(`${BASE}/slack/alerts/${id}`, { method: 'DELETE' })
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {}
  }

  return (
    <div>
      <div style={{ fontSize: '0.82rem', color: 'var(--text2)', marginBottom: '0.85rem' }}>
        Get notified whenever a keyword appears in any Slack channel — via email, DM, or both.
        Scanned every 15 minutes.
      </div>

      {/* Add form */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
        <input
          placeholder="keyword (e.g. production down)"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          style={inputStyle}
        />
        <input
          placeholder="#channel1,#channel2  (blank = all)"
          value={channels}
          onChange={e => setChannels(e.target.value)}
          style={{ ...inputStyle, maxWidth: 200 }}
        />
        <select value={via} onChange={e => setVia(e.target.value)} style={selectStyle}>
          <option value="both">Email + DM</option>
          <option value="email">Email only</option>
          <option value="dm">Slack DM only</option>
        </select>
        <button className="btn btn-primary" onClick={add} disabled={busy || !keyword.trim()}
          style={{ padding: '0.45rem 0.9rem', fontSize: '0.8rem' }}>
          {busy ? 'Adding…' : '+ Add'}
        </button>
      </div>
      {error && <div className="error" style={{ fontSize: '0.78rem', marginBottom: '0.5rem' }}>{error}</div>}

      {/* Alert list */}
      {alerts.length === 0
        ? <div style={{ fontSize: '0.78rem', color: 'var(--text3)' }}>No alerts yet.</div>
        : alerts.map(a => (
          <div key={a.id} style={{
            display: 'flex', alignItems: 'center', gap: '0.6rem',
            padding: '0.5rem 0.7rem', background: 'var(--surface2)',
            borderRadius: 6, marginBottom: '0.4rem',
            opacity: a.is_active ? 1 : 0.5,
          }}>
            <span style={{ fontSize: '0.85rem' }}>🔔</span>
            <code style={{ fontSize: '0.8rem', color: 'var(--cyan)', flex: 1 }}>{a.keyword}</code>
            {a.channels && <span style={{ fontSize: '0.72rem', color: 'var(--text3)' }}>{a.channels}</span>}
            <span className="badge" style={{ fontSize: '0.65rem' }}>{a.notify_via}</span>
            <button onClick={() => toggle(a.id)} style={ghostBtn}>
              {a.is_active ? 'Pause' : 'Resume'}
            </button>
            <button onClick={() => remove(a.id)} style={{ ...ghostBtn, color: 'var(--red)' }}>×</button>
          </div>
        ))}
    </div>
  )
}

// ── Event Triggers ─────────────────────────────────────────────────────────

const ACTION_LABELS = {
  create_github_issue: 'Create GitHub Issue',
  post_to_channel:     'Post to Channel',
  run_copilot:         'Run Copilot',
}

function EventTriggers() {
  const [triggers, setTriggers]   = useState([])
  const [showForm, setShowForm]   = useState(false)
  const [form, setForm]           = useState({
    name: '', trigger_keyword: '', source_channel: '',
    action_type: 'create_github_issue', action_config: {},
  })
  const [configStr, setConfigStr] = useState('{}')
  const [busy, setBusy]           = useState(false)
  const [error, setError]         = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    try { setTriggers(await apiFetch(`${BASE}/slack/triggers`)) } catch {}
  }

  async function save() {
    setBusy(true); setError('')
    try {
      const config = JSON.parse(configStr || '{}')
      const t = await apiFetch(`${BASE}/slack/triggers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, action_config: config }),
      })
      setTriggers(prev => [t, ...prev])
      setShowForm(false)
      setForm({ name: '', trigger_keyword: '', source_channel: '', action_type: 'create_github_issue', action_config: {} })
      setConfigStr('{}')
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  async function toggle(id) {
    try {
      const updated = await apiFetch(`${BASE}/slack/triggers/${id}`, { method: 'PATCH' })
      setTriggers(prev => prev.map(t => t.id === id ? updated : t))
    } catch {}
  }

  async function remove(id) {
    try {
      await apiFetch(`${BASE}/slack/triggers/${id}`, { method: 'DELETE' })
      setTriggers(prev => prev.filter(t => t.id !== id))
    } catch {}
  }

  const configPlaceholders = {
    create_github_issue: '{"repo": "owner/repo", "label": "slack-trigger"}',
    post_to_channel:     '{"channel": "#ops", "message": "Alert: {text}"}',
    run_copilot:         '{"prompt": "Summarise this: {text}", "reply_channel": "#ops"}',
  }

  return (
    <div>
      <div style={{ fontSize: '0.82rem', color: 'var(--text2)', marginBottom: '0.85rem' }}>
        Automatically trigger an action when a keyword appears in Slack.
        Powered by the Socket Mode bot — requires <code style={{ fontSize: '0.78rem' }}>SLACK_APP_TOKEN</code> in .env.
      </div>

      <button className="btn btn-primary" onClick={() => setShowForm(v => !v)}
        style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
        {showForm ? 'Cancel' : '+ New Trigger'}
      </button>

      {showForm && (
        <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, padding: '1rem', marginBottom: '0.85rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
            <input placeholder="Trigger name (e.g. Incident auto-issue)" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} style={inputStyle} />
            <input placeholder="Keyword to watch (e.g. production down)" value={form.trigger_keyword}
              onChange={e => setForm(f => ({ ...f, trigger_keyword: e.target.value }))} style={inputStyle} />
            <input placeholder="Source channel (blank = all channels)" value={form.source_channel}
              onChange={e => setForm(f => ({ ...f, source_channel: e.target.value }))} style={inputStyle} />
            <select value={form.action_type} onChange={e => setForm(f => ({ ...f, action_type: e.target.value }))}
              style={selectStyle}>
              {Object.entries(ACTION_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <div>
              <div style={{ fontSize: '0.73rem', color: 'var(--text3)', marginBottom: '0.25rem' }}>
                Action config (JSON) — {configPlaceholders[form.action_type]}
              </div>
              <textarea value={configStr} onChange={e => setConfigStr(e.target.value)} rows={3}
                style={{ ...inputStyle, resize: 'vertical', fontFamily: 'monospace', fontSize: '0.78rem' }}
                placeholder={configPlaceholders[form.action_type]} />
            </div>
            {error && <div className="error" style={{ fontSize: '0.78rem' }}>{error}</div>}
            <button className="btn btn-primary" onClick={save} disabled={busy || !form.name || !form.trigger_keyword}
              style={{ alignSelf: 'flex-start', padding: '0.45rem 1rem', fontSize: '0.8rem' }}>
              {busy ? 'Saving…' : 'Save Trigger'}
            </button>
          </div>
        </div>
      )}

      {triggers.length === 0
        ? <div style={{ fontSize: '0.78rem', color: 'var(--text3)' }}>No triggers yet.</div>
        : triggers.map(t => (
          <div key={t.id} style={{
            padding: '0.6rem 0.8rem', background: 'var(--surface2)',
            borderRadius: 6, marginBottom: '0.4rem', opacity: t.is_active ? 1 : 0.5,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              <span style={{ fontSize: '0.85rem' }}>⚡</span>
              <span style={{ fontWeight: 600, fontSize: '0.82rem', flex: 1 }}>{t.name}</span>
              <span className="badge" style={{ fontSize: '0.65rem' }}>{ACTION_LABELS[t.action_type]}</span>
              <button onClick={() => toggle(t.id)} style={ghostBtn}>{t.is_active ? 'Pause' : 'Resume'}</button>
              <button onClick={() => remove(t.id)} style={{ ...ghostBtn, color: 'var(--red)' }}>×</button>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginTop: '0.25rem', paddingLeft: '1.4rem' }}>
              keyword: <code style={{ color: 'var(--cyan)' }}>{t.trigger_keyword}</code>
              {t.source_channel && <> · channel: <code style={{ color: 'var(--cyan)' }}>#{t.source_channel}</code></>}
            </div>
          </div>
        ))}
    </div>
  )
}

// ── Shared styles ──────────────────────────────────────────────────────────

const inputStyle = {
  background: 'var(--surface3)', border: '1px solid var(--border2)',
  borderRadius: 'var(--r-sm)', color: 'var(--text)',
  padding: '0.5rem 0.75rem', fontSize: '0.82rem',
  fontFamily: 'Inter, sans-serif', flex: 1, minWidth: 140,
}
const selectStyle = {
  ...inputStyle, flex: 'none', cursor: 'pointer',
}
const ghostBtn = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text3)', fontSize: '0.75rem', padding: '2px 6px',
  borderRadius: 4, fontFamily: 'Inter, sans-serif',
}

// ── Main export ────────────────────────────────────────────────────────────

export default function SlackFeatures() {
  const [tab, setTab] = useState('alerts')

  return (
    <div>
      <div className="page-header">
        <div className="page-title">Slack Features</div>
        <div className="page-subtitle">Keyword alerts, event triggers, and bot configuration</div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.25rem' }}>
        {[['alerts', '🔔 Keyword Alerts'], ['triggers', '⚡ Event Triggers'], ['bot', '🤖 Bot Setup']].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            style={{
              background: tab === id ? 'var(--accent)' : 'var(--surface2)',
              color: tab === id ? '#fff' : 'var(--text2)',
              border: '1px solid var(--border)',
              borderRadius: 6, padding: '0.4rem 0.9rem',
              fontSize: '0.8rem', cursor: 'pointer', fontFamily: 'Inter, sans-serif',
            }}>
            {label}
          </button>
        ))}
      </div>

      <div style={{ maxWidth: 680 }}>
        {tab === 'alerts' && (
          <div className="card static" style={{ padding: '1.25rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '0.75rem' }}>🔔 Keyword Alerts</div>
            <KeywordAlerts />
          </div>
        )}

        {tab === 'triggers' && (
          <div className="card static" style={{ padding: '1.25rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '0.75rem' }}>⚡ Event Triggers</div>
            <EventTriggers />
          </div>
        )}

        {tab === 'bot' && (
          <div className="card static" style={{ padding: '1.25rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '0.75rem' }}>🤖 Bot Setup Guide</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text2)', lineHeight: 1.8 }}>
              <p style={{ marginTop: 0 }}>To enable the bidirectional Slack bot (DMs + @mentions):</p>
              <ol style={{ paddingLeft: '1.2rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li>Go to <a href="https://api.slack.com/apps" target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>api.slack.com/apps</a> → your app</li>
                <li><strong>Settings → Socket Mode</strong> → Enable Socket Mode → Generate an App-Level Token with <code>connections:write</code> scope</li>
                <li>Copy the token (starts with <code>xapp-</code>) → add to <code>.env</code> as <code>SLACK_APP_TOKEN</code></li>
                <li><strong>Event Subscriptions → Subscribe to bot events:</strong> add <code>message.im</code> and <code>app_mention</code></li>
                <li><strong>Basic Information → Signing Secret</strong> → copy it → add to <code>.env</code> as <code>SLACK_SIGNING_SECRET</code></li>
                <li>For interactive buttons (HITL approvals): <strong>Interactivity & Shortcuts → Request URL:</strong><br/>
                  <code style={{ background: 'var(--surface3)', padding: '2px 6px', borderRadius: 3 }}>
                    https://&lt;your-domain&gt;/v1/slack/interactive
                  </code>
                </li>
                <li>Start the bot process alongside the server:<br/>
                  <code style={{ background: 'var(--surface3)', padding: '2px 6px', borderRadius: 3 }}>
                    python -m backend.workers.slack_bot
                  </code>
                </li>
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
