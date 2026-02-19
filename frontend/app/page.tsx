'use client'

import { useEffect, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [igUsername, setIgUsername] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem('vp_ig_username')
    if (stored) setIgUsername(stored)
  }, [])

  const handleIgLogin = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${API_URL}/api/instagram/auth?persona_id=default`)
      const data = await resp.json()
      if (data.auth_url) {
        window.location.href = data.auth_url
      }
    } catch (e) {
      console.error('Failed to get auth URL', e)
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
