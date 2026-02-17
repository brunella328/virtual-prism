import type { Metadata } from 'next'

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
    <html lang="zh-TW">
      <body>{children}</body>
    </html>
  )
}
