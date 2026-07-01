const API_ROOT = import.meta.env.VITE_API_URL || ''
export const BASE = `${API_ROOT}/v1`
const TIMEOUT_MS = 30_000

export function getToken() { return localStorage.getItem('token') }
export function getUser()  { try { return JSON.parse(localStorage.getItem('user')) } catch { return null } }
export function saveAuth(token, user) {
  localStorage.setItem('token', token)
  localStorage.setItem('user', JSON.stringify(user))
}
export function clearAuth() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
}

export async function apiFetch(url, opts = {}) {
  const signal = AbortSignal.timeout(TIMEOUT_MS)
  const token = getToken()
  const headers = { ...(opts.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { ...opts, headers, signal })
  if (!res.ok) {
    let detail
    try { detail = (await res.json()).detail } catch { detail = res.statusText }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────
export async function authRegister(email, password, name = '') {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Registration failed')
  return data
}

export async function authLogin(email, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Login failed')
  return data
}

export async function authMe() {
  return apiFetch(`${BASE}/auth/me`)
}

export async function fetchRuns() {
  return apiFetch(`${BASE}/runs`)
}

export async function fetchRun(id) {
  return apiFetch(`${BASE}/runs/${id}`)
}

export async function createRun(goal, role = 'operator') {
  return apiFetch(`${BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
    body: JSON.stringify({ goal }),
  })
}

export async function fetchApprovals() {
  return apiFetch(`${BASE}/approvals`)
}

export async function decide(approvalId, approved, role = 'operator') {
  return apiFetch(`${BASE}/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
    body: JSON.stringify({ approved }),
  })
}

export async function fetchMcpTools() {
  return apiFetch(`${BASE}/mcp/tools`)
}

// ── Documents ────────────────────────────────────────────
export async function uploadDocument(file) {
  const fd = new FormData()
  fd.append('file', file)
  return apiFetch(`${BASE}/documents`, { method: 'POST', body: fd })
}

export async function fetchDocuments() {
  return apiFetch(`${BASE}/documents`)
}

export async function askDocument(question, top_k) {
  return apiFetch(`${BASE}/documents/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k }),
  })
}

// ── Integrations ─────────────────────────────────────────
export async function fetchIntegrations() {
  return apiFetch(`${BASE}/integrations`)
}

export async function connectIntegration(service, token, role = 'operator') {
  return apiFetch(`${BASE}/integrations/${service}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
    body: JSON.stringify({ token }),
  })
}

export async function disconnectIntegration(service, role = 'operator') {
  return apiFetch(`${BASE}/integrations/${service}`, {
    method: 'DELETE',
    headers: { 'X-User-Role': role },
  })
}

export async function verifyIntegration(service) {
  return apiFetch(`${BASE}/integrations/${service}/verify`)
}

// ── Chat ─────────────────────────────────────────────────
export async function sendChat(message, conversation_id = null) {
  return apiFetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id }),
  })
}

// ── Conversations ─────────────────────────────────────────
export async function fetchConversations() {
  return apiFetch(`${BASE}/conversations`)
}

export async function fetchConversationMessages(id) {
  return apiFetch(`${BASE}/conversations/${id}/messages`)
}

export async function deleteConversation(id) {
  return apiFetch(`${BASE}/conversations/${id}`, { method: 'DELETE' })
}
