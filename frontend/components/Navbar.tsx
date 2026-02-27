'use client'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const NAV_LINKS = [
  { href: '/onboarding', label: '人設' },
  { href: '/dashboard', label: '內容' },
  { href: '/schedule', label: '排程紀錄' },
]

export default function Navbar() {
  const pathname = usePathname()
  const router = useRouter()
  const [igUsername, setIgUsername] = useState('')

  useEffect(() => {
    const username = localStorage.getItem('vp_ig_username') || ''
    setIgUsername(username)
  }, [])

  const handleLogout = async () => {
    const userId = localStorage.getItem('vp_user_id')
    if (userId) {
      fetch(`${API}/api/instagram/token/${userId}`, { method: 'DELETE' }).catch(() => {})
    }
    Object.keys(localStorage).filter(k => k.startsWith('vp_')).forEach(k => localStorage.removeItem(k))
    router.push('/onboarding')
  }

  return (
    <nav className="border-b border-gray-100 bg-white sticky top-0 z-50">
      <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <span className="font-bold text-lg tracking-tight">Virtual Prism 🌈</span>

        {/* Nav links */}
        <div className="flex items-center gap-6">
          {NAV_LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className={`text-sm transition-colors ${
                pathname === href
                  ? 'font-semibold text-black border-b-2 border-black pb-0.5'
                  : 'text-gray-500 hover:text-black'
              }`}
            >
              {label}
            </a>
          ))}
        </div>

        {/* Account + logout */}
        <div className="flex items-center gap-3">
          {igUsername && (
            <span className="text-sm text-gray-500">@{igUsername}</span>
          )}
          <button
            onClick={handleLogout}
            className="text-xs text-gray-400 hover:text-black border border-gray-200 px-3 py-1.5 rounded-lg hover:border-gray-400 transition-colors"
          >
            登出
          </button>
        </div>
      </div>
    </nav>
  )
}
