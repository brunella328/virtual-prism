'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { storage } from '@/lib/storage'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function VerifyEmailPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying')
  const [errorMsg, setErrorMsg] = useState('')
  const called = useRef(false)

  useEffect(() => {
    // 防止 React StrictMode 雙重執行
    if (called.current) return
    called.current = true

    const token = searchParams.get('token')
    if (!token) {
      setStatus('error')
      setErrorMsg('缺少驗證 token')
      return
    }

    fetch(`${API_URL}/api/auth/verify-email?token=${token}`)
      .then(res => res.ok ? res.json() : res.json().then(e => Promise.reject(e.detail)))
      .then(data => {
        storage.setUserId(data.uuid)
        storage.setEmail(data.email)
        storage.setJwtToken(data.token)
        setStatus('success')
        setTimeout(() => router.replace('/dashboard'), 2000)
      })
      .catch(err => {
        setStatus('error')
        setErrorMsg(typeof err === 'string' ? err : '驗證失敗，請重新註冊')
      })
  }, [])

  if (status === 'verifying') return (
    <main className="min-h-screen flex flex-col items-center justify-center">
      <div className="text-5xl mb-4 animate-pulse">🌈</div>
      <p className="text-gray-500">驗證中...</p>
    </main>
  )

  if (status === 'success') return (
    <main className="min-h-screen flex flex-col items-center justify-center text-center p-8">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="text-xl font-bold mb-2">Email 驗證成功！</h2>
      <p className="text-gray-500">正在為你跳轉...</p>
    </main>
  )

  return (
    <main className="min-h-screen flex flex-col items-center justify-center text-center p-8">
      <div className="text-5xl mb-4">❌</div>
      <h2 className="text-xl font-bold mb-2">驗證失敗</h2>
      <p className="text-sm text-gray-500 mb-6">{errorMsg}</p>
      <a href="/register" className="bg-black text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-gray-800">
        重新註冊
      </a>
    </main>
  )
}
