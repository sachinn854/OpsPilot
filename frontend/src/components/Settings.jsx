import { useEffect, useState } from 'react'
import { BASE, apiFetch } from '../api'

const SERVICES = [
  {
    id: 'google',
    label: 'Google Workspace',
    icon: '⊗',
    description: 'Connect Gmail, Calendar, Drive, Sheets and Meet with a single Google login.',
    oauthFlow: true,
    guide: {
      title: 'What you get after connecting',
      steps: [
        { text: 'Gmail — read, search, send emails and create drafts', chips: ['gmail_list_emails', 'gmail_send_email', 'gmail_search_emails'] },
        { text: 'Calendar — list events, find free slots, create events', chips: ['calendar_list_events', 'calendar_find_free_slot', 'calendar_create_event'] },
        { text: 'Meet — create meetings with Google Meet link automatically', chips: ['calendar_create_meeting'] },
        { text: 'Drive — search and read files, Google Docs, PDFs', chips: ['drive_search_files', 'drive_read_file'] },
        { text: 'Sheets — read ranges, append rows, update cells', chips: ['sheets_read_range', 'sheets_append_row'] },
      ],
      note: 'All write actions (send email, create meeting, update sheet) require HITL approval before executing.',
    },
  },
  {
    id: 'github',
    label: 'GitHub',
    icon: '⊙',
    description: 'Connect your GitHub account to access repos, issues, PRs, and code.',
    placeholder: 'ghp_xxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://github.com/settings/tokens',
    guide: {
      title: 'How to get a GitHub Personal Access Token',
      steps: [
        { text: 'Open GitHub → click your avatar (top-right) → Settings' },
        { text: 'Scroll down → click Developer settings → Personal access tokens → Tokens (classic)' },
        { text: 'Click "Generate new token (classic)" → add a note (e.g. OpsPilot)' },
        {
          text: 'Select scopes:',
          chips: ['repo', 'read:org', 'read:user', 'workflow'],
        },
        { text: 'Click "Generate token" → copy the token immediately (shown only once)' },
        { text: 'Paste it in the field above → click Connect' },
      ],
      note: 'Fine-grained PATs also work — grant repo + metadata read permissions for the repos you want the copilot to access.',
    },
  },
  {
    id: 'slack',
    label: 'Slack',
    icon: '◈',
    description: 'Connect Slack to send messages, read channels, DM teammates, and more.',
    placeholder: 'xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://api.slack.com/apps',
    guide: {
      title: 'How to create a Slack Bot Token',
      steps: [
        {
          text: 'Go to api.slack.com/apps → click "Create New App"',
          link: { label: 'Open Slack App Directory →', url: 'https://api.slack.com/apps' },
        },
        { text: 'Choose "From scratch" → enter a name (e.g. OpsPilot) → select your workspace → click Create App' },
        { text: 'In the left sidebar click "OAuth & Permissions"' },
        {
          text: 'Scroll to "Bot Token Scopes" → click "Add an OAuth Scope" and add all of these:',
          chips: [
            'channels:read', 'channels:write', 'chat:write', 'chat:write.customize',
            'files:write', 'groups:read', 'im:write', 'mpim:write',
            'pins:write', 'reactions:write', 'search:read', 'users:read', 'users:read.email',
          ],
        },
        { text: 'Scroll back up → click "Install to Workspace" → click Allow' },
        { text: 'Under "OAuth Tokens for Your Workspace", copy the Bot User OAuth Token (starts with xoxb-)' },
        { text: 'Paste it in the field above → click Connect' },
      ],
      note: 'Keep this token secret — it has access to your Slack workspace. You can revoke it anytime from the Slack App settings.',
    },
  },
  {
    id: 'jira',
    label: 'Jira',
    icon: '⊞',
    description: 'Connect Jira to manage tickets and sprints.',
    multiField: true,
    fields: [
      { key: 'domain', label: 'Workspace domain', placeholder: 'yourcompany.atlassian.net', type: 'text' },
      { key: 'email', label: 'Atlassian account email', placeholder: 'you@company.com', type: 'email' },
      { key: 'api_token', label: 'API token', placeholder: 'ATATT3xFfGF0...', type: 'password' },
    ],
    docsUrl: 'https://id.atlassian.com/manage-profile/security/api-tokens',
    guide: {
      title: 'How to get a Jira API Token',
      steps: [
        {
          text: 'Go to id.atlassian.com → click "Security" → "Create and manage API tokens"',
          link: { label: 'Open Atlassian API Tokens →', url: 'https://id.atlassian.com/manage-profile/security/api-tokens' },
        },
        { text: 'Click "Create API token" → enter a label (e.g. OpsPilot) → click Create' },
        { text: 'Copy the token immediately (shown only once)' },
        { text: 'Enter your workspace domain (e.g. yourcompany.atlassian.net), your email, and paste the token above → click Connect' },
      ],
      note: 'This token is tied to your Atlassian account and works across all Jira/Confluence projects you have access to.',
    },
  },
  {
    id: 'linear',
    label: 'Linear',
    icon: '⊕',
    description: 'Connect Linear to track issues and roadmap.',
    placeholder: 'lin_api_xxxxxxxxxxxx',
    docsUrl: 'https://linear.app/settings/api',
    guide: {
      title: 'How to get a Linear API Key',
      steps: [
        {
          text: 'Go to linear.app → Settings → API → Personal API keys',
          link: { label: 'Open Linear API Settings →', url: 'https://linear.app/settings/api' },
        },
        { text: 'Click "Create new API key" → enter a label (e.g. OpsPilot) → click Create' },
        { text: 'Copy the key immediately (starts with lin_api_)' },
        { text: 'Paste it in the field above → click Connect' },
      ],
    },
  },
  {
    id: 'notion',
    label: 'Notion',
    icon: '◻',
    description: 'Connect Notion to search pages, read and create docs, and query databases.',
    placeholder: 'secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://www.notion.so/my-integrations',
    guide: {
      title: 'How to get a Notion Integration Token',
      steps: [
        {
          text: 'Go to notion.so/my-integrations → click "New integration"',
          link: { label: 'Open Notion Integrations →', url: 'https://www.notion.so/my-integrations' },
        },
        { text: 'Enter a name (e.g. OpsPilot) → select your workspace → click Submit' },
        { text: 'Copy the "Internal Integration Token" (starts with secret_)' },
        { text: 'In Notion, open any page you want to give access → click ••• → Connections → select your integration' },
        { text: 'Paste the token above → click Connect' },
      ],
      note: 'You must share each Notion page/database with the integration for it to be accessible.',
    },
  },
  {
    id: 'confluence',
    label: 'Confluence',
    icon: '⊟',
    description: 'Connect Confluence to search docs, read pages, and create or update wiki content.',
    multiField: true,
    fields: [
      { key: 'domain', label: 'Atlassian domain', placeholder: 'yourcompany.atlassian.net', type: 'text' },
      { key: 'email', label: 'Atlassian account email', placeholder: 'you@company.com', type: 'email' },
      { key: 'api_token', label: 'API token', placeholder: 'ATATT3xFfGF0...', type: 'password' },
    ],
    docsUrl: 'https://id.atlassian.com/manage-profile/security/api-tokens',
    guide: {
      title: 'How to connect Confluence',
      steps: [
        {
          text: 'Go to id.atlassian.com → Security → API tokens → Create API token',
          link: { label: 'Open Atlassian API Tokens →', url: 'https://id.atlassian.com/manage-profile/security/api-tokens' },
        },
        { text: 'Enter a label (e.g. OpsPilot) → click Create → copy the token immediately' },
        { text: 'Enter your Atlassian domain (e.g. yourcompany.atlassian.net), email, and token above → click Connect' },
      ],
      note: 'The same API token works for both Jira and Confluence if your account has access to both.',
    },
  },
  {
    id: 'pagerduty',
    label: 'PagerDuty',
    icon: '⚠',
    description: 'Connect PagerDuty to manage incidents, check on-call schedules, and trigger alerts.',
    placeholder: 'u+xxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://support.pagerduty.com/docs/generating-api-keys',
    guide: {
      title: 'How to get a PagerDuty API Key',
      steps: [
        { text: 'Log into PagerDuty → click your avatar → User Settings → API Access Keys' },
        { text: 'Click "Create New API Key" → enter a description (e.g. OpsPilot) → click Create Key' },
        { text: 'Copy the key (starts with u+)' },
        { text: 'Paste it above → click Connect' },
      ],
      note: 'Use a user-level API key for personal access, or an account-level key (admin only) for broader access.',
    },
  },
  {
    id: 'hubspot',
    label: 'HubSpot',
    icon: '⊛',
    description: 'Connect HubSpot CRM to search contacts, manage deals, and track companies.',
    placeholder: 'pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
    docsUrl: 'https://app.hubspot.com/login',
    guide: {
      title: 'How to get a HubSpot Private App Token',
      steps: [
        { text: 'Log into HubSpot → click Settings (gear icon) → Integrations → Private Apps' },
        { text: 'Click "Create a private app" → enter a name (e.g. OpsPilot)' },
        {
          text: 'Go to the Scopes tab and enable:',
          chips: ['crm.objects.contacts.read', 'crm.objects.contacts.write', 'crm.objects.deals.read', 'crm.objects.deals.write', 'crm.objects.companies.read'],
        },
        { text: 'Click "Create app" → copy the access token (starts with pat-na1-)' },
        { text: 'Paste it above → click Connect' },
      ],
      note: 'Private App tokens are scoped — only the permissions you select are granted.',
    },
  },
]

function TokenGuide({ guide, onClose }) {
  return (
    <div style={{
      marginTop: '0.85rem',
      background: 'var(--surface2)',
      border: '1px solid var(--border2)',
      borderRadius: 8,
      padding: '1rem 1.1rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>
          📖 {guide.title}
        </div>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text3)', fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}
        >×</button>
      </div>

      <ol style={{ margin: 0, paddingLeft: '1.3rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        {guide.steps.map((step, i) => (
          <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text2)', lineHeight: 1.6 }}>
            <span>{step.text}</span>
            {step.link && (
              <span> <a
                href={step.link.url}
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--accent)', textDecoration: 'none', fontWeight: 500 }}
              >{step.link.label}</a></span>
            )}
            {step.chips && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginTop: '0.35rem' }}>
                {step.chips.map(chip => (
                  <code key={chip} style={{
                    background: 'var(--surface3)',
                    border: '1px solid var(--border)',
                    borderRadius: 4,
                    padding: '1px 7px',
                    fontSize: '0.73rem',
                    color: 'var(--cyan)',
                    fontFamily: 'monospace',
                  }}>{chip}</code>
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>

      {guide.note && (
        <div style={{
          marginTop: '0.75rem',
          paddingTop: '0.65rem',
          borderTop: '1px solid var(--border)',
          fontSize: '0.74rem',
          color: 'var(--text3)',
          lineHeight: 1.6,
        }}>
          💡 {guide.note}
        </div>
      )}
    </div>
  )
}

const inputStyle = {
  background: 'var(--surface3)', border: '1px solid var(--border2)',
  borderRadius: 6, color: 'var(--text)', padding: '0.5rem 0.75rem',
  fontSize: '0.82rem', fontFamily: 'Inter, sans-serif', width: '100%',
  boxSizing: 'border-box',
}

function LLMProviderPanel() {
  const [config, setConfig]           = useState(null)
  const [provider, setProvider]       = useState('openrouter')
  const [model, setModel]             = useState('')
  const [saving, setSaving]           = useState(false)
  const [msg, setMsg]                 = useState('')

  // OpenRouter
  const [orKey, setOrKey]             = useState('')
  const [orKeyStatus, setOrKeyStatus] = useState(null) // null | 'saving' | 'ok' | 'error'
  const [orModels, setOrModels]       = useState([])
  const [orSearch, setOrSearch]       = useState('')
  const [orLoading, setOrLoading]     = useState(false)
  const [showOrList, setShowOrList]   = useState(false)

  useEffect(() => {
    apiFetch(`${BASE}/llm/config`).then(c => {
      setConfig(c); setProvider(c.provider); setModel(c.model)
    }).catch(() => {})
    apiFetch(`${BASE}/integrations`).then(rows => {
      if (rows.find(r => r.service === 'openrouter')) setOrKeyStatus('ok')
    }).catch(() => {})
  }, [])

  async function saveOrKey() {
    if (!orKey.trim()) return
    setOrKeyStatus('saving')
    try {
      await apiFetch(`${BASE}/integrations/openrouter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: orKey.trim() }),
      })
      setOrKeyStatus('ok'); setOrKey('')
    } catch { setOrKeyStatus('error') }
  }

  async function loadOrModels() {
    setOrLoading(true); setShowOrList(true)
    try {
      const r = await apiFetch(`${BASE}/llm/openrouter/models`)
      if (r.ok) setOrModels(r.models || [])
      else { setMsg(r.error); setShowOrList(false) }
    } catch (e) { setMsg(e.message); setShowOrList(false) }
    finally { setOrLoading(false) }
  }

  async function save() {
    if (!model.trim()) return
    setSaving(true); setMsg('')
    try {
      await apiFetch(`${BASE}/llm/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model: model.trim() }),
      })
      setConfig(c => ({ ...c, provider, model: model.trim(), is_custom: true }))
      setMsg('Saved!')
    } catch (e) { setMsg('Error: ' + e.message) }
    finally { setSaving(false) }
  }

  async function reset() {
    setSaving(true); setMsg('')
    try {
      await apiFetch(`${BASE}/llm/config`, { method: 'DELETE' })
      const c = await apiFetch(`${BASE}/llm/config`)
      setConfig(c); setProvider(c.provider); setModel(c.model)
      setMsg('Reset to system default.')
    } catch (e) { setMsg('Error: ' + e.message) }
    finally { setSaving(false) }
  }

  const filteredOrModels = orModels.filter(m =>
    !orSearch || m.id.toLowerCase().includes(orSearch.toLowerCase()) ||
    m.name.toLowerCase().includes(orSearch.toLowerCase())
  )

  return (
    <div className="card static" style={{ padding: '1.25rem' }}>
      <div style={{ fontWeight: 600, fontSize: '0.92rem', marginBottom: '0.75rem' }}>🤖 LLM Provider</div>

      {/* Active badge */}
      {config && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.73rem', color: 'var(--text3)' }}>Active:</span>
          <span className="badge" style={{ fontSize: '0.68rem' }}>☁ OpenRouter</span>
          <code style={{ fontSize: '0.78rem', color: 'var(--cyan)' }}>{config.model}</code>
          {config.is_custom && <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>(your choice)</span>}
        </div>
      )}

      {/* ── OpenRouter panel ── */}
      {provider === 'openrouter' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {/* API Key */}
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.3rem' }}>
              Your OpenRouter API Key
              {orKeyStatus === 'ok' && <span style={{ color: '#22c55e', marginLeft: '0.5rem' }}>✓ Connected</span>}
              {orKeyStatus === 'error' && <span style={{ color: '#f87171', marginLeft: '0.5rem' }}>✗ Invalid key</span>}
            </div>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <input
                type="password"
                placeholder={orKeyStatus === 'ok' ? '••••••••••••••• (saved)' : 'sk-or-v1-...'}
                value={orKey}
                onChange={e => setOrKey(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              />
              <button className="btn btn-primary" onClick={saveOrKey}
                disabled={orKeyStatus === 'saving' || !orKey.trim()}
                style={{ padding: '0.45rem 0.85rem', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                {orKeyStatus === 'saving' ? 'Saving…' : 'Save Key'}
              </button>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text3)', marginTop: '0.25rem' }}>
              Get your key at <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer"
                style={{ color: 'var(--accent)' }}>openrouter.ai/keys</a> — free to create
            </div>
          </div>

          {/* Model picker */}
          <div>
            <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.3rem' }}>
              <input
                placeholder="Paste model ID — e.g. openai/gpt-4o or anthropic/claude-3-5-sonnet"
                value={model}
                onChange={e => setModel(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              />
              <button onClick={loadOrModels} disabled={orLoading}
                style={{ padding: '0.45rem 0.7rem', borderRadius: 6, border: '1px solid var(--border)',
                  background: 'var(--surface2)', color: 'var(--text2)', fontSize: '0.75rem',
                  cursor: 'pointer', fontFamily: 'Inter, sans-serif', whiteSpace: 'nowrap' }}>
                {orLoading ? 'Loading…' : 'Browse'}
              </button>
            </div>

            {/* Model list */}
            {showOrList && (
              <div style={{ border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
                <input
                  placeholder="Search models…"
                  value={orSearch}
                  onChange={e => setOrSearch(e.target.value)}
                  style={{ ...inputStyle, borderRadius: 0, borderBottom: '1px solid var(--border)', borderLeft: 'none', borderRight: 'none', borderTop: 'none' }}
                />
                <div style={{ maxHeight: 240, overflowY: 'auto' }}>
                  {filteredOrModels.slice(0, 100).map(m => (
                    <div key={m.id} onClick={() => { setModel(m.id); setShowOrList(false); setOrSearch('') }}
                      style={{ padding: '0.45rem 0.7rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem',
                        borderBottom: '1px solid var(--border)', fontSize: '0.78rem' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                      <span style={{ flex: 1, color: 'var(--text)' }}>{m.id}</span>
                      {m.supports_tools && <span style={{ fontSize: '0.65rem', color: '#22c55e' }}>✓ tools</span>}
                      <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>
                        ${(parseFloat(m.prompt_price || 0) * 1e6).toFixed(2)}/M
                      </span>
                    </div>
                  ))}
                  {filteredOrModels.length === 0 && (
                    <div style={{ padding: '0.6rem', fontSize: '0.75rem', color: 'var(--text3)' }}>No models found</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Save */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.85rem' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving || !model.trim()}
          style={{ padding: '0.45rem 1rem', fontSize: '0.8rem' }}>
          {saving ? 'Saving…' : 'Use this model'}
        </button>
        {config?.is_custom && (
          <button onClick={reset} disabled={saving}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text3)', fontSize: '0.75rem' }}>
            Reset to default
          </button>
        )}
        {msg && <span style={{ fontSize: '0.75rem', color: msg.startsWith('Error') ? '#f87171' : '#22c55e' }}>{msg}</span>}
      </div>
    </div>
  )
}

export default function Settings() {
  const [connected, setConnected] = useState({})
  const [inputs, setInputs]       = useState({})
  const [multiInputs, setMultiInputs] = useState({})
  const [busy, setBusy]           = useState({})
  const [errors, setErrors]       = useState({})
  const [success, setSuccess]     = useState({})
  const [showGuide, setShowGuide] = useState({})

  // Email digest preferences
  const [digestEnabled, setDigestEnabled]   = useState(true)
  const [digestEmail, setDigestEmail]       = useState('')
  const [digestSaving, setDigestSaving]     = useState(false)
  const [digestMsg, setDigestMsg]           = useState('')

  useEffect(() => { loadConnected(); loadDigestPrefs() }, [])

  async function loadConnected() {
    try {
      const rows = await apiFetch(`${BASE}/integrations`)
      const map = {}
      for (const r of rows) map[r.service] = r
      setConnected(map)
    } catch { /* silent */ }
  }

  async function loadDigestPrefs() {
    try {
      const me = await apiFetch(`${BASE}/auth/me`)
      setDigestEnabled(me.digest_email_enabled ?? true)
      setDigestEmail(me.digest_email_override || '')
    } catch { /* silent */ }
  }

  async function saveDigestPrefs() {
    setDigestSaving(true)
    setDigestMsg('')
    try {
      await apiFetch(`${BASE}/auth/digest-prefs`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          digest_email_enabled: digestEnabled,
          digest_email_override: digestEmail.trim(),
        }),
      })
      setDigestMsg('Saved!')
    } catch (e) {
      setDigestMsg('Failed to save: ' + e.message)
    } finally {
      setDigestSaving(false)
    }
  }

  async function handleConnect(serviceId) {
    const svc = SERVICES.find(s => s.id === serviceId)
    let token
    if (svc?.multiField) {
      const fields = multiInputs[serviceId] || {}
      const missing = svc.fields.find(f => !fields[f.key]?.trim())
      if (missing) {
        setErrors(er => ({ ...er, [serviceId]: `Please fill in: ${missing.label}` }))
        return
      }
      const payload = {}
      svc.fields.forEach(f => { payload[f.key] = fields[f.key].trim() })
      token = JSON.stringify(payload)
    } else {
      token = (inputs[serviceId] || '').trim()
      if (!token) return
    }
    setBusy(b => ({ ...b, [serviceId]: true }))
    setErrors(e => ({ ...e, [serviceId]: '' }))
    setSuccess(s => ({ ...s, [serviceId]: '' }))
    try {
      const result = await apiFetch(`${BASE}/integrations/${serviceId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-User-Role': 'operator' },
        body: JSON.stringify({ token }),
      })
      setConnected(c => ({ ...c, [serviceId]: result }))
      setInputs(i => ({ ...i, [serviceId]: '' }))
      setMultiInputs(m => ({ ...m, [serviceId]: {} }))
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
      await apiFetch(`${BASE}/integrations/${serviceId}`, { method: 'DELETE' })
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
      const result = await apiFetch(`${BASE}/integrations/${serviceId}/verify`)
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

        <LLMProviderPanel />

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

        {/* Email Digest card */}
        <div className="card static" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '1.1rem', color: 'var(--accent)' }}>✉</span>
            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>Email Digest</span>
            <span className="badge" style={{ fontSize: '0.65rem', background: 'var(--surface3)', color: 'var(--text2)' }}>
              twice daily
            </span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text2)', marginBottom: '1rem' }}>
            Receive a summary of all Slack channel activity — sent automatically at 9 AM and 6 PM UTC.
          </div>

          {/* Toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', cursor: 'pointer', marginBottom: '0.85rem' }}>
            <div
              onClick={() => setDigestEnabled(v => !v)}
              style={{
                width: 36, height: 20, borderRadius: 10, flexShrink: 0,
                background: digestEnabled ? 'var(--accent)' : 'var(--surface3)',
                position: 'relative', cursor: 'pointer', transition: 'background 0.2s',
              }}
            >
              <div style={{
                width: 14, height: 14, borderRadius: '50%', background: '#fff',
                position: 'absolute', top: 3,
                left: digestEnabled ? 18 : 3,
                transition: 'left 0.2s',
              }} />
            </div>
            <span style={{ fontSize: '0.82rem', color: 'var(--text2)' }}>
              {digestEnabled ? 'Email digest enabled' : 'Email digest disabled'}
            </span>
          </label>

          {/* Optional override email */}
          {digestEnabled && (
            <div style={{ marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text3)', marginBottom: '0.3rem' }}>
                Send to (leave blank to use your account email)
              </div>
              <input
                type="email"
                placeholder="other@example.com"
                value={digestEmail}
                onChange={e => setDigestEmail(e.target.value)}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'var(--surface2)', border: '1px solid var(--border2)',
                  borderRadius: 'var(--r-sm)', color: 'var(--text)',
                  padding: '0.55rem 0.8rem', fontSize: '0.85rem',
                  fontFamily: 'Inter, sans-serif',
                }}
              />
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              className="btn btn-primary"
              style={{ padding: '0.45rem 1rem', fontSize: '0.8rem' }}
              disabled={digestSaving}
              onClick={saveDigestPrefs}
            >
              {digestSaving ? 'Saving…' : 'Save'}
            </button>
            {digestMsg && (
              <span style={{ fontSize: '0.78rem', color: digestMsg.startsWith('Failed') ? 'var(--red)' : 'var(--green)' }}>
                {digestMsg}
              </span>
            )}
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
                <>
                  {svc.oauthFlow ? (
                    <div style={{ marginBottom: '0.5rem' }}>
                      <button
                        className="btn btn-primary"
                        style={{ padding: '0.55rem 1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                        disabled={isBusy}
                        onClick={() => {
                          setBusy(b => ({ ...b, [svc.id]: true }))
                          const API_ROOT = import.meta.env.VITE_API_URL || ''
                          fetch(`${API_ROOT}/v1/integrations/google/connect`, {
                            headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
                          })
                            .then(r => r.json())
                            .then(({ auth_url }) => {
                              const popup = window.open(auth_url, 'google-oauth', 'width=550,height=680,scrollbars=yes')
                              const check = setInterval(() => {
                                if (popup && popup.closed) {
                                  clearInterval(check)
                                  setBusy(b => ({ ...b, [svc.id]: false }))
                                  loadConnected()
                                }
                              }, 800)
                            })
                            .catch(e => {
                              setBusy(b => ({ ...b, [svc.id]: false }))
                              setErrors(er => ({ ...er, [svc.id]: e.message }))
                            })
                        }}
                      >
                        {isBusy
                          ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Connecting…</>
                          : '⊗ Connect Google Account'}
                      </button>
                    </div>
                  ) : svc.multiField ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      {svc.fields.map(f => (
                        <div className="field" key={f.key} style={{ marginBottom: 0 }}>
                          <label style={{ fontSize: '0.72rem', color: 'var(--text3)', marginBottom: '0.2rem', display: 'block' }}>{f.label}</label>
                          <input
                            type={f.type}
                            placeholder={f.placeholder}
                            value={(multiInputs[svc.id] || {})[f.key] || ''}
                            onChange={e => setMultiInputs(m => ({ ...m, [svc.id]: { ...(m[svc.id] || {}), [f.key]: e.target.value } }))}
                            disabled={isBusy}
                          />
                        </div>
                      ))}
                      <button
                        className="btn btn-primary"
                        style={{ alignSelf: 'flex-start', padding: '0.55rem 1.2rem', marginTop: '0.2rem' }}
                        disabled={isBusy}
                        onClick={() => handleConnect(svc.id)}
                      >
                        {isBusy ? <><div className="spinner" style={{ borderTopColor: '#fff' }} /> Connecting…</> : 'Connect'}
                      </button>
                    </div>
                  ) : (
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

                  {/* Guide toggle */}
                  {svc.guide && (
                    <div style={{ marginTop: '0.1rem' }}>
                      <button
                        onClick={() => setShowGuide(g => ({ ...g, [svc.id]: !g[svc.id] }))}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          color: showGuide[svc.id] ? 'var(--accent)' : 'var(--text3)',
                          fontSize: '0.75rem', padding: 0, fontFamily: 'Inter, sans-serif',
                          display: 'flex', alignItems: 'center', gap: '0.3rem',
                          transition: 'color 0.15s',
                        }}
                      >
                        <span style={{ fontSize: '0.85rem' }}>{showGuide[svc.id] ? '▾' : '▸'}</span>
                        {svc.oauthFlow ? 'What tools will I get?' : 'Where do I get this token?'}
                      </button>
                      {showGuide[svc.id] && (
                        <TokenGuide
                          guide={svc.guide}
                          onClose={() => setShowGuide(g => ({ ...g, [svc.id]: false }))}
                        />
                      )}
                    </div>
                  )}
                </>
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
