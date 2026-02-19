'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

function CallbackContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing')
  const [message, setMessage] = useState('處理 Instagram 授權中...')

  useEffect(() => {
    const igUserId = searchParams.get('ig_user_id')
    const igUsername = searchParams.get('ig_username')
    const error = searchParams.get('error')

    if (error) {
      setStatus('error')
      setMessage(`授權失敗：${searchParams.get('error_description') || error}`)
      return
    }

    if (!igUserId) {
      setStatus('error')
      setMessage('授權失敗：未收到用戶 ID，請重試')
      return
    }

    // Store session
    localStorage.setItem('vp_user_id', igUserId)
    localStorage.setItem('vp_ig_username', igUsername || 'ig_user')

    setStatus('success')
    setMessage(`✅ 成功連結 @${igUsername || igUserId}，正在跳轉...`)

    // Redirect to onboarding after 1.5s
    setTimeout(() => {
      router.push('/onboarding')
    }, 1500)
  }, [searchParams, router])

  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Instagram 授權</h1>
      <div
        className={`text-lg ${
          status === 'error' ? 'text-red-500' : status === 'success' ? 'text-green-600' : 'text-gray-500'
        }`}
      >
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
