const BASE = '/v1'
const TIMEOUT_MS = 30_000

export async function apiFetch(url, opts = {}) {
  const signal = AbortSignal.timeout(TIMEOUT_MS)
  const res = await fetch(url, { ...opts, signal })
  if (!res.ok) {
    let detail
    try { detail = (await res.json()).detail } catch { detail = res.statusText }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.json()
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
