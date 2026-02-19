'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function CallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [message, setMessage] = useState('處理 Instagram 授權中...')

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const error = searchParams.get('error')

    // Handle direct error redirect from backend
    if (error) {
      setStatus('error')
      const desc = searchParams.get('error_description') || error
      setMessage(`授權失敗：${decodeURIComponent(desc)}`)
      return
    }

    // Handle OAuth code from Instagram (frontend-first flow)
    if (code) {
      // Exchange code via backend
      fetch(`${API_URL}/api/instagram/exchange`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          state: state || 'default',
          redirect_uri: `${window.location.origin}/auth/callback`,
        }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.ig_account_id || data.ig_username) {
            const igUserId = data.ig_account_id
            const igUsername = data.ig_username || 'ig_user'
            localStorage.setItem('vp_user_id', igUserId)
            localStorage.setItem('vp_ig_username', igUsername)
            setStatus('success')
            setMessage(`✅ 成功連結 @${igUsername}，正在跳轉...`)
            setTimeout(() => router.push('/onboarding'), 1500)
          } else {
            throw new Error(data.detail || JSON.stringify(data))
          }
        })
        .catch(e => {
          setStatus('error')
          setMessage(`授權失敗：${e.message}`)
        })
      return
    }

    // Handle ig_user_id passed directly from backend redirect (legacy)
    const igUserId = searchParams.get('ig_user_id')
    const igUsername = searchParams.get('ig_username')

    if (igUserId) {
      localStorage.setItem('vp_user_id', igUserId)
      localStorage.setItem('vp_ig_username', igUsername || 'ig_user')
      setStatus('success')
      setMessage(`✅ 成功連結 @${igUsername || igUserId}，正在跳轉...`)
      setTimeout(() => router.push('/onboarding'), 1500)
      return
    }

    setStatus('error')
    setMessage('未收到授權資料，請重試')
  }, [searchParams, router])

  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Instagram 授權</h1>
      <div className={`text-lg ${
        status === 'error' ? 'text-red-500' : status === 'success' ? 'text-green-600' : 'text-gray-500'
      }`}>
        {status === 'processing' && <span className="animate-pulse">⏳ </span>}
        {message}
      </div>
      {status === 'error' && (
        <a href="/" className="mt-4 px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800">
          返回首頁重試
        </a>
      )}
    </main>
  )
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500 animate-pulse">處理授權中...</p>
      </main>
    }>
      <CallbackContent />
    </Suspense>
  )
}
