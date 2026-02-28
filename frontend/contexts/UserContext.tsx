'use client'
/**
 * UserContext — 全域使用者狀態
 *
 * 規則：
 * - Pages / components 只呼叫 useUser()，不直接碰 localStorage
 * - 任何 auth 狀態變更（connect / logout）必須透過此 context
 * - storage.ts 是唯一的 localStorage 入口
 */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { storage } from '@/lib/storage'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UserState {
  userId: string | null
  igUsername: string | null
  appearancePrompt: string
}

export interface UserContextType extends UserState {
  /** 是否已登入（userId 非 null） */
  isAuthenticated: boolean
  /**
   * 連結 IG 帳號後呼叫，同時更新 React state 與 localStorage。
   * userId = IG account ID（同時也是 persona ID）
   */
  connect: (userId: string, igUsername: string, appearancePrompt?: string) => void
  /** 登出：清除所有 state 與 localStorage */
  logout: () => void
  /** 更新 appearance prompt（onboarding 完成時呼叫） */
  setAppearancePrompt: (prompt: string) => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const UserContext = createContext<UserContextType | null>(null)

export function UserProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<UserState>(() => ({
    // 從 storage 讀取初始值（做過 SSR guard，server side 回傳 null）
    userId: storage.getUserId(),
    igUsername: storage.getIgUsername(),
    appearancePrompt: storage.getAppearancePrompt(),
  }))

  const connect = useCallback((
    userId: string,
    igUsername: string,
    appearancePrompt = '',
  ) => {
    storage.setUserId(userId)
    storage.setIgUsername(igUsername)
    if (appearancePrompt) storage.setAppearancePrompt(appearancePrompt)
    setState({ userId, igUsername, appearancePrompt })
  }, [])

  const logout = useCallback(() => {
    storage.clearAll()
    setState({ userId: null, igUsername: null, appearancePrompt: '' })
  }, [])

  const setAppearancePrompt = useCallback((prompt: string) => {
    storage.setAppearancePrompt(prompt)
    setState(prev => ({ ...prev, appearancePrompt: prompt }))
  }, [])

  return (
    <UserContext.Provider value={{
      ...state,
      isAuthenticated: !!state.userId,
      connect,
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
