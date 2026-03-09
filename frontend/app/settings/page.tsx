'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import Navbar from '@/components/Navbar'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function SettingsPage() {
  const router = useRouter()
  const { userId, email, jwtToken, igUsername, hasIgToken, isLoading, connectIg, logout } = useUser()
  const [igLoading, setIgLoading] = useState(false)
  const [disconnectLoading, setDisconnectLoading] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!isLoading && !userId) {
      router.push('/login')
    }
  }, [userId, isLoading, router])

  const handleConnectIg = async () => {
    if (!userId || !jwtToken) return
    setIgLoading(true)
    try {
      // 取得 IG OAuth URL，state = UUID
      const res = await fetch(`${API_URL}/api/instagram/auth?persona_id=${userId}`)
      const data = await res.json()
      if (data.auth_url) {
        window.location.href = data.auth_url
      } else {
        setMessage('無法取得授權連結，請確認後端設定')
      }
    } catch {
      setMessage('連線失敗，請確認後端是否運行中')
    } finally {
      setIgLoading(false)
    }
  }

  const handleDisconnectIg = async () => {
    if (!jwtToken) return
    setDisconnectLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/auth/disconnect-ig`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${jwtToken}` },
      })
      if (res.ok) {
        connectIg('')  // 清空 igUsername
        setMessage('已解除 Instagram 連結')
      } else {
        setMessage('解除失敗，請稍後再試')
      }
    } catch {
      setMessage('連線失敗')
    } finally {
      setDisconnectLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  if (isLoading || !userId) return null

  return (
    <>
      <Navbar />
      <main className="max-w-lg mx-auto px-6 py-10 space-y-8">
        <h1 className="text-2xl font-bold">帳號設定</h1>

        {/* 帳號資訊 */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">帳號資訊</h2>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500">Email</span>
            <span className="text-sm font-medium">{email}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500">帳號 ID</span>
            <span className="text-xs text-gray-400 font-mono">{userId}</span>
          </div>
        </section>

        {/* Instagram 連結 */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Instagram 連結</h2>

          {hasIgToken && igUsername ? (
            <>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-500">已連結帳號</span>
                <span className="text-sm font-medium">@{igUsername}</span>
              </div>
              <p className="text-xs text-gray-400">連結後可直接從平台發布貼文到 Instagram</p>
              <button
                onClick={handleDisconnectIg}
                disabled={disconnectLoading}
                className="w-full border border-red-200 text-red-500 rounded-lg py-2 text-sm hover:bg-red-50 disabled:opacity-50"
              >
                {disconnectLoading ? '解除中...' : '解除 Instagram 連結'}
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-500">連結 Instagram 帳號後，可直接從平台排程發布貼文。<br />不連結也能使用 Web Share 分享到任意社交平台。</p>
              <button
                onClick={handleConnectIg}
                disabled={igLoading}
                className="w-full bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg py-2 text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                {igLoading ? '連線中...' : '連結 Instagram 帳號'}
              </button>
            </>
          )}
        </section>

        {message && (
          <p className="text-sm text-center text-gray-500">{message}</p>
        )}

        {/* 登出 */}
        <button
          onClick={handleLogout}
          className="w-full border border-gray-200 text-gray-400 rounded-lg py-2 text-sm hover:border-gray-400 hover:text-black transition-colors"
        >
          登出
        </button>
      </main>
    </>
  )
}
