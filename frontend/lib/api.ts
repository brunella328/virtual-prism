const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_KEY = process.env.NEXT_PUBLIC_API_SECRET_KEY || ''

// ---------------------------------------------------------------------------
// Shared header builder — always injects X-Api-Key when configured
// ---------------------------------------------------------------------------

export function apiHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {}
  if (API_KEY) headers['X-Api-Key'] = API_KEY
  if (extra) Object.assign(headers, extra)
  return headers
}

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

export async function apiGet(path: string) {
  const res = await fetch(`${API_URL}${path}`, {
    credentials: 'include',
    headers: apiHeaders(),
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

export async function apiPost(path: string, body: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

export async function apiPatch(path: string, body: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

export async function apiDelete(path: string) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: apiHeaders(),
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}
