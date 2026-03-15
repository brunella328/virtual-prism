'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import Navbar from '@/components/Navbar'

export default function SettingsPage() {
  const router = useRouter()
  const { userId, email, isLoading, logout } = useUser()

  useEffect(() => {
    if (!isLoading && !userId) {
      router.push('/login')
    }
  }, [userId, isLoading, router])

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
