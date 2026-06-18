const BASE = '/v1'

export async function fetchRuns() {
  const r = await fetch(`${BASE}/runs`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function fetchRun(id) {
  const r = await fetch(`${BASE}/runs/${id}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createRun(goal, role = 'operator') {
  const r = await fetch(`${BASE}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
    body: JSON.stringify({ goal }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function fetchApprovals() {
  const r = await fetch(`${BASE}/approvals`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function decide(approvalId, approved, role = 'operator') {
  const r = await fetch(`${BASE}/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
    body: JSON.stringify({ approved, decided_by: 'ui-user' }),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function fetchMcpTools() {
  const r = await fetch(`${BASE}/mcp/tools`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
