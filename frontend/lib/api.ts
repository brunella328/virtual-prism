const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Generic helpers
// ---------------------------------------------------------------------------

export async function apiGet(path: string) {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

export async function apiPost(path: string, body: unknown) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

export async function apiDelete(path: string) {
  const res = await fetch(`${API_URL}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InstagramStatus {
  connected: boolean
  ig_account_id?: string
  ig_username?: string
  connected_at?: string
}

export interface ScheduledPost {
  image_url: string
  caption: string
  publish_at: string  // ISO-8601 datetime string
}

export interface ScheduledJobInfo {
  job_id: string
  name: string
  run_date: string | null
  persona_id: string
}

// ---------------------------------------------------------------------------
// Instagram API functions
// ---------------------------------------------------------------------------

/**
 * Check if an Instagram account is connected for the given persona.
 */
export async function getInstagramStatus(personaId: string): Promise<InstagramStatus> {
  return apiGet(`/api/instagram/status?persona_id=${encodeURIComponent(personaId)}`)
}

/**
 * Get the Facebook OAuth URL to connect an Instagram account.
 * Typically: window.location.href = data.auth_url
 */
export async function getInstagramAuthUrl(personaId: string): Promise<{ auth_url: string; persona_id: string }> {
  return apiGet(`/api/instagram/auth?persona_id=${encodeURIComponent(personaId)}`)
}

/**
 * Schedule one or more posts for future publishing.
 */
export async function scheduleInstagramPosts(
  personaId: string,
  posts: ScheduledPost[],
): Promise<{ scheduled: { job_id: string; publish_at: string }[]; count: number }> {
  return apiPost('/api/instagram/schedule', { persona_id: personaId, posts })
}

/**
 * Immediately publish a photo to Instagram (no scheduling).
 */
export async function publishNow(
  personaId: string,
  imageUrl: string,
  caption: string,
): Promise<{ success: boolean; media_id: string; persona_id: string }> {
  return apiPost('/api/instagram/publish-now', {
    persona_id: personaId,
    image_url: imageUrl,
    caption: caption,
  })
}

/**
 * Retrieve all pending scheduled posts for a persona.
 */
export async function getScheduledPosts(
  personaId: string,
): Promise<{ persona_id: string; scheduled_posts: ScheduledJobInfo[]; count: number }> {
  return apiGet(`/api/instagram/schedule?persona_id=${encodeURIComponent(personaId)}`)
}

/**
 * Cancel a scheduled post by job ID.
 */
export async function cancelScheduledPost(jobId: string): Promise<{ cancelled: boolean; job_id: string }> {
  return apiDelete(`/api/instagram/schedule/${encodeURIComponent(jobId)}`)
}
