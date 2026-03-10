'use client'
/**
 * UserContext — 全域使用者狀態
 *
 * 規則：
 * - Pages / components 只呼叫 useUser()，不直接碰 localStorage
 * - 任何 auth 狀態變更（login / logout / connectIg）必須透過此 context
 * - storage.ts 是唯一的 localStorage 入口
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { storage } from '@/lib/storage'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UserState {
  userId: string | null      // UUID（平台帳號）
  email: string | null
  jwtToken: string | null
  igUsername: string | null  // 僅在連結 IG 後有值
  hasIgToken: boolean
  appearancePrompt: string
}

export interface UserContextType extends UserState {
  isAuthenticated: boolean
  isLoading: boolean
  /** Email + password 登入 */
  loginWithEmail: (email: string, password: string) => Promise<void>
  /** Email + password 註冊，成功後回傳後端 message（需 email 驗證） */
  registerWithEmail: (email: string, password: string) => Promise<string>
  /** IG OAuth 完成後呼叫（/auth/callback 頁面使用） */
  connectIg: (igUsername: string) => void
  /** 登出：清除所有 state 與 localStorage */
  logout: () => void
  setAppearancePrompt: (prompt: string) => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const UserContext = createContext<UserContextType | null>(null)

export function UserProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UserState>({
    userId: null,
    email: null,
    jwtToken: null,
    igUsername: null,
    hasIgToken: false,
    appearancePrompt: '',
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const userId = storage.getUserId()
    const jwtToken = storage.getJwtToken()
    setState({
      userId,
      email: storage.getEmail(),
      jwtToken,
      igUsername: storage.getIgUsername(),
      hasIgToken: false,
      appearancePrompt: storage.getAppearancePrompt(),
    })
    // 若有 JWT，從後端確認 has_ig_token
    if (userId && jwtToken) {
      fetch(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data) {
            setState(prev => ({ ...prev, hasIgToken: data.has_ig_token ?? false }))
          }
        })
        .catch(() => {})
    }
    setIsLoading(false)
  }, [])

  const loginWithEmail = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    storage.setUserId(data.uuid)
    storage.setEmail(data.email)
    storage.setJwtToken(data.token)
    setState(prev => ({
      ...prev,
      userId: data.uuid,
      email: data.email,
      jwtToken: data.token,
      hasIgToken: false,
    }))
  }, [])

  const registerWithEmail = useCallback(async (email: string, password: string): Promise<string> => {
    const res = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Registration failed')
    }
    const data = await res.json()
    // 後端不再回傳 token，需先驗證 email 才能登入
    return data.message as string
  }, [])

  const connectIg = useCallback((igUsername: string) => {
    storage.setIgUsername(igUsername)
    setState(prev => ({ ...prev, igUsername, hasIgToken: true }))
  }, [])

  const logout = useCallback(() => {
    storage.clearAll()
    setState({
      userId: null,
      email: null,
      jwtToken: null,
      igUsername: null,
      hasIgToken: false,
      appearancePrompt: '',
    })
  }, [])

  const setAppearancePrompt = useCallback((prompt: string) => {
    storage.setAppearancePrompt(prompt)
    setState(prev => ({ ...prev, appearancePrompt: prompt }))
  }, [])

  return (
    <UserContext.Provider value={{
      ...state,
      isAuthenticated: !!state.userId,
      isLoading,
      loginWithEmail,
      registerWithEmail,
      connectIg,
      logout,
      setAppearancePrompt,
    }}>
      {children}
    </UserContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useUser(): UserContextType {
  const ctx = useContext(UserContext)
  if (!ctx) throw new Error('useUser() must be used inside <UserProvider>')
  return ctx
}
