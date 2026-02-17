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

// ---------------------------------------------------------------------------
// Interact / Auto-Reply Types
// ---------------------------------------------------------------------------

export interface PendingReply {
  reply_id: string
  persona_id: string
  ig_comment_id: string
  ig_media_id: string
  commenter_name: string
  comment_text: string
  draft_text: string
  risk_level: 'high' | 'low'
  status: 'pending' | 'sent' | 'dismissed'
  created_at: string
}

export interface PendingRepliesResponse {
  persona_id: string
  replies: PendingReply[]
  count: number
}

export interface AutoReplySettingResponse {
  persona_id: string
  mode: 'draft' | 'auto'
}

// ---------------------------------------------------------------------------
// Interact / Auto-Reply API functions
// ---------------------------------------------------------------------------

/**
 * Fetch all pending reply drafts for a persona.
 */
export async function getPendingReplies(personaId: string): Promise<PendingRepliesResponse> {
  return apiGet(`/api/interact/replies/pending/${encodeURIComponent(personaId)}`)
}

/**
 * Confirm and send a queued reply draft to Instagram.
 */
export async function sendReply(
  replyId: string,
  personaId: string,
): Promise<{ status: string; reply: PendingReply }> {
  return apiPost(`/api/interact/replies/${encodeURIComponent(replyId)}/send`, {
    persona_id: personaId,
  })
}

/**
 * Dismiss (ignore) a queued reply draft.
 */
export async function dismissReply(replyId: string): Promise<{ status: string; reply: PendingReply }> {
  return apiPost(`/api/interact/replies/${encodeURIComponent(replyId)}/dismiss`, {})
}

/**
 * Get the auto-reply mode setting for a persona.
 */
export async function getAutoReplySetting(personaId: string): Promise<AutoReplySettingResponse> {
  return apiGet(`/api/interact/settings/${encodeURIComponent(personaId)}`)
}

/**
 * Update the auto-reply mode setting for a persona.
 */
export async function setAutoReplySetting(
  personaId: string,
  mode: 'draft' | 'auto',
): Promise<{ persona_id: string; mode: string; status: string }> {
  return apiPost(`/api/interact/settings/${encodeURIComponent(personaId)}`, { mode })
}

// ---------------------------------------------------------------------------
// Fan Memory Types
// ---------------------------------------------------------------------------

export interface FanRecord {
  fan_id: string
  username: string
  interaction_count: number
  last_interaction: string   // ISO datetime
  notes: string
  first_seen: string         // ISO datetime
}

export interface FanListResponse {
  persona_id: string
  fans: FanRecord[]
  count: number
}

// ---------------------------------------------------------------------------
// Fan Memory API functions
// ---------------------------------------------------------------------------

/**
 * Fetch the fan list for a given persona, sorted by interaction count.
 */
export async function getFanList(personaId: string, limit = 20): Promise<FanListResponse> {
  return apiGet(`/api/fans/${encodeURIComponent(personaId)}?limit=${limit}`)
}

/**
 * Fetch a single fan record for the given persona + fan.
 */
export async function getFanDetail(personaId: string, fanId: string): Promise<FanRecord> {
  return apiGet(`/api/fans/${encodeURIComponent(personaId)}/${encodeURIComponent(fanId)}`)
}
