import type { Metadata } from 'next'
import { Syne } from 'next/font/google'
import './globals.css'
import { UserProvider } from '@/contexts/UserContext'

const syne = Syne({ subsets: ['latin'], weight: ['800'], variable: '--font-syne' })

export const metadata: Metadata = {
  title: 'Virtual Prism',
  description: 'B2B AI 虛擬網紅自動化營運平台',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-TW" className={syne.variable}>
      <body>
        <UserProvider>{children}</UserProvider>
      </body>
    </html>
  )
}
