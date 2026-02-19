'use client'

import { useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [igUsername, setIgUsername] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem('vp_ig_username')
    if (stored) setIgUsername(stored)
  }, [])

  const handleIgLogin = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API_URL}/api/instagram/auth?persona_id=default`)
      if (!resp.ok) throw new Error(`後端錯誤 ${resp.status}`)
      const data = await resp.json()
      if (data.auth_url) {
        window.location.href = data.auth_url
      } else {
        throw new Error('未取得授權連結')
      }
    } catch (e) {
      console.error('Failed to get auth URL', e)
      setError(e instanceof Error ? e.message : '連線失敗，請確認後端服務正常後重試')
      setLoading(false)
    }
  }

  const handleLogout = () => {
    const userId = localStorage.getItem('vp_user_id')
    if (userId) {
      fetch(`${API_URL}/api/instagram/token/${userId}`, { method: 'DELETE' }).catch(() => {})
    }
    localStorage.removeItem('vp_user_id')
    localStorage.removeItem('vp_ig_username')
    setIgUsername(null)
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6">
      <h1 className="text-4xl font-bold">Virtual Prism 🌈</h1>
      <p className="text-gray-500">B2B AI 虛擬網紅自動化營運平台</p>

      {error && (
        <p className="text-red-500 text-sm bg-red-50 px-4 py-2 rounded-lg">⚠️ {error}</p>
      )}

      {igUsername ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-green-600 font-medium">✅ 已連結：@{igUsername}</p>
          <a
            href="/onboarding"
            className="px-6 py-3 bg-black text-white rounded-lg hover:bg-gray-800"
          >
            開始創建你的 AI 網紅 →
          </a>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-gray-600 underline"
          >
            登出 / 切換帳號
          </button>
        </div>
      ) : (
        <button
          onClick={handleIgLogin}
          disabled={loading}
          className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? '連結中...' : '連結 Instagram 帳號 →'}
        </button>
      )}
    </main>
  )
}
