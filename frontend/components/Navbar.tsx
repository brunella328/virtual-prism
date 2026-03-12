'use client'
import { usePathname, useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'

const NAV_LINKS = [
  { href: '/onboarding', label: '人設' },
  { href: '/dashboard', label: '內容' },
  { href: '/settings', label: '設定' },
]

export default function Navbar() {
  const pathname = usePathname()
  const router = useRouter()
  const { email, igUsername, logout } = useUser()

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  return (
    <nav className="border-b border-gray-100 bg-white sticky top-0 z-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        {/* Main row */}
        <div className="h-14 flex items-center justify-between">
          <span className="font-[family-name:var(--font-syne)] font-extrabold text-xl tracking-tight italic">VP</span>

          <div className="flex items-center gap-4 sm:gap-6">
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

          {/* Desktop: email + logout inline */}
          <div className="hidden sm:flex items-center gap-3">
            {igUsername ? (
              <span className="text-sm text-gray-500">@{igUsername}</span>
            ) : email ? (
              <span className="text-sm text-gray-500">{email}</span>
            ) : null}
            <button
              onClick={handleLogout}
              className="text-xs text-gray-400 hover:text-black border border-gray-200 px-3 py-1.5 rounded-lg hover:border-gray-400 transition-colors"
            >
              登出
            </button>
          </div>
        </div>

        {/* Mobile: email + logout on second row */}
        <div className="flex sm:hidden items-center justify-end gap-3 pb-2">
          {igUsername ? (
            <span className="text-xs text-gray-500">@{igUsername}</span>
          ) : email ? (
            <span className="text-xs text-gray-500">{email}</span>
          ) : null}
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
