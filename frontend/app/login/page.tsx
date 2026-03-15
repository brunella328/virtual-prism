'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useUser } from '@/contexts/UserContext'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function LoginPage() {
  const router = useRouter()
  const { loginWithEmail, isAuthenticated, isLoading } = useUser()
  const [email, setEmail] = useState('')

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace('/dashboard')
  }, [isAuthenticated, isLoading, router])
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [needsVerification, setNeedsVerification] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [resendMsg, setResendMsg] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setNeedsVerification(false)
    setResendMsg('')
    setLoading(true)
    try {
      await loginWithEmail(email, password)
      router.push('/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '登入失敗'
      if (msg.includes('驗證 Email') || msg.includes('驗證信')) {
        setNeedsVerification(true)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setResendLoading(true)
    setResendMsg('')
    try {
      const res = await fetch(`${API_URL}/api/auth/resend-verification`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: '' }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '重送失敗')
      setResendMsg(data.message)
    } catch (err: unknown) {
      setResendMsg(err instanceof Error ? err.message : '重送失敗')
    } finally {
      setResendLoading(false)
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm p-8 space-y-6">
        <h1 className="text-2xl font-bold text-center">登入 Virtual Prism</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => { setEmail(e.target.value); setNeedsVerification(false); setResendMsg('') }}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">密碼</label>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="至少 8 個字元"
            />
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          {needsVerification && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 space-y-2">
              <p className="text-sm text-yellow-800">請先驗證 Email 才能登入。</p>
              {resendMsg ? (
                <p className="text-sm text-green-700">{resendMsg}</p>
              ) : (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendLoading}
                  className="text-sm text-yellow-700 underline hover:text-yellow-900 disabled:opacity-50"
                >
                  {resendLoading ? '寄送中...' : '重新寄送驗證信'}
                </button>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white rounded-lg py-2 text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? '登入中...' : '登入'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500">
          還沒有帳號？{' '}
          <Link href="/register" className="text-black font-medium hover:underline">
            立即註冊
          </Link>
        </p>
      </div>
    </main>
  )
}
