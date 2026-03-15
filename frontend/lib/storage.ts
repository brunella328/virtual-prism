/**
 * storage.ts — localStorage 唯一入口
 *
 * 規則：
 * - 所有 localStorage key 集中定義在此，其他檔案不直接呼叫 localStorage
 * - 所有函數做 SSR guard（Next.js 在 hydration 時也會在 server side 跑 client component）
 * - vp_user_id = UUID（平台帳號 ID）
 */

const KEYS = {
  USER_ID: 'vp_user_id',
  EMAIL: 'vp_email',
  JWT_TOKEN: 'vp_jwt_token',
  APPEARANCE_PROMPT: 'vp_appearance_prompt',
  SCHEDULE: 'vp_schedule',
} as const

const isClient = typeof window !== 'undefined'

function get(key: string): string | null {
  if (!isClient) return null
  return localStorage.getItem(key)
}

function set(key: string, value: string): void {
  if (!isClient) return
  localStorage.setItem(key, value)
}

function remove(key: string): void {
  if (!isClient) return
  localStorage.removeItem(key)
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const storage = {
  // Auth (platform account)
  getUserId: (): string | null => get(KEYS.USER_ID),
  setUserId: (id: string): void => set(KEYS.USER_ID, id),

  getEmail: (): string | null => get(KEYS.EMAIL),
  setEmail: (email: string): void => set(KEYS.EMAIL, email),

  getJwtToken: (): string | null => get(KEYS.JWT_TOKEN),
  setJwtToken: (token: string): void => set(KEYS.JWT_TOKEN, token),

  // Image generation
  getAppearancePrompt: (): string => get(KEYS.APPEARANCE_PROMPT) ?? '',
  setAppearancePrompt: (prompt: string): void => set(KEYS.APPEARANCE_PROMPT, prompt),

  // Schedule cache
  getSchedule: (): unknown[] | null => {
    const raw = get(KEYS.SCHEDULE)
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : null
    } catch {
      return null
    }
  },
  setSchedule: (schedule: unknown[]): void => set(KEYS.SCHEDULE, JSON.stringify(schedule)),
  clearSchedule: (): void => remove(KEYS.SCHEDULE),

  // Clear everything on logout
  clearAll: (): void => {
    Object.values(KEYS).forEach(k => remove(k))
  },
}
