'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import { useUser } from '@/contexts/UserContext'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function CallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { connectIg, jwtToken } = useUser()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [message, setMessage] = useState('處理 Instagram 授權中...')

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const error = searchParams.get('error')

    if (error) {
      setStatus('error')
      const desc = searchParams.get('error_description') || error
      setMessage(`授權失敗：${decodeURIComponent(desc)}`)
      return
    }

    // 後端 redirect 帶回的參數（state = user UUID，新流程）
    const igUserId = searchParams.get('ig_user_id')
    const igUsername = searchParams.get('ig_username')
    const personaId = searchParams.get('persona_id')

    if (igUserId && personaId) {
      connectIg(igUsername || igUserId)
      setStatus('success')
      setMessage(`✅ 成功連結 @${igUsername || igUserId}，正在跳轉...`)
      setTimeout(() => router.push('/settings'), 1500)
      return
    }

    // Frontend-first OAuth flow（前端收到 code，POST 給後端換 token）
    if (code && state) {
      fetch(`${API_URL}/api/instagram/exchange`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          state,
          redirect_uri: `${window.location.origin}/auth/callback`,
        }),
      })
        .then(r => r.json())
        .then(async data => {
          if (data.ig_account_id || data.ig_username) {
            const username = data.ig_username || 'ig_user'
            const igToken = data.access_token
            if (jwtToken && igToken) {
              await fetch(`${API_URL}/api/auth/connect-ig`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  Authorization: `Bearer ${jwtToken}`,
                },
                body: JSON.stringify({ ig_token: igToken, ig_user_id: data.ig_account_id }),
              })
              connectIg(username)
              setStatus('success')
              setMessage(`✅ 成功連結 @${username}，正在跳轉...`)
              setTimeout(() => router.push('/settings'), 1500)
            } else {
              setStatus('error')
              setMessage('請先登入再連結 Instagram')
              setTimeout(() => router.push('/login'), 1500)
            }
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

    setStatus('error')
    setMessage('未收到授權資料，請重試')
  }, [searchParams, router, connectIg, jwtToken])

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
