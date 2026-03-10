'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useUser } from '@/contexts/UserContext'

export default function RegisterPage() {
  const router = useRouter()
  const { registerWithEmail, isAuthenticated, isLoading } = useUser()

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace('/dashboard')
  }, [isAuthenticated, isLoading, router])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('密碼至少需要 8 個字元')
      return
    }
    setLoading(true)
    try {
      const msg = await registerWithEmail(email, password)
      setSuccessMsg(msg)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '註冊失敗')
    } finally {
      setLoading(false)
    }
  }

  if (successMsg) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm p-8 space-y-4 text-center">
          <div className="text-5xl">📬</div>
          <h2 className="text-xl font-bold">驗證信已寄出</h2>
          <p className="text-sm text-gray-500">{successMsg}</p>
          <p className="text-sm text-gray-400">驗證完成後，請回到登入頁面。</p>
          <Link href="/login" className="block w-full bg-black text-white rounded-lg py-2 text-sm font-medium hover:bg-gray-800 text-center">
            前往登入
          </Link>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-sm p-8 space-y-6">
        <h1 className="text-2xl font-bold text-center">建立帳號</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
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

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white rounded-lg py-2 text-sm font-medium hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? '建立中...' : '建立帳號'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500">
          已有帳號？{' '}
          <Link href="/login" className="text-black font-medium hover:underline">
            登入
          </Link>
        </p>
      </div>
    </main>
  )
}
