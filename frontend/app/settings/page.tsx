'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import Navbar from '@/components/Navbar'
import { apiHeaders } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Tab = 'account' | 'chat-style'

export default function SettingsPage() {
  const router = useRouter()
  const { userId, email, isLoading, logout } = useUser()
  const [activeTab, setActiveTab] = useState<Tab>('account')

  // Chat style state
  const [chatStylePrompt, setChatStylePrompt] = useState('')
  const [chatStyleImage, setChatStyleImage] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [loadingStyle, setLoadingStyle] = useState(false)

  useEffect(() => {
    if (!isLoading && !userId) {
      router.push('/login')
    }
  }, [userId, isLoading, router])

  // 切到聊天發文風格 Tab 時載入現有設定
  useEffect(() => {
    if (!userId || activeTab !== 'chat-style') return
    setLoadingStyle(true)
    fetch(`${API}/api/genesis/persona/${userId}`, {
      credentials: 'include',
      headers: apiHeaders(),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.persona) {
          setChatStylePrompt(data.persona.chat_style_prompt ?? '')
          setChatStyleImage(data.persona.chat_style_image ?? '')
        }
      })
      .catch(() => {})
      .finally(() => setLoadingStyle(false))
  }, [userId, activeTab])

  const handleLogout = () => {
    logout()
    router.push('/login')
  }

  const handleSaveChatStyle = async () => {
    if (!userId) return
    setSaving(true)
    setSaveMsg(null)
    try {
      const res = await fetch(`${API}/api/genesis/persona/${userId}/chat-style`, {
        method: 'PATCH',
        credentials: 'include',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          chat_style_prompt: chatStylePrompt || null,
          chat_style_image: chatStyleImage || null,
        }),
      })
      if (!res.ok) throw new Error('save failed')
      setSaveMsg('已儲存 ✓')
    } catch {
      setSaveMsg('儲存失敗，請再試')
    } finally {
      setSaving(false)
      setTimeout(() => setSaveMsg(null), 3000)
    }
  }

  if (isLoading || !userId) return null

  return (
    <>
      <Navbar />
      <main className="max-w-lg mx-auto px-6 py-10 space-y-6">
        <h1 className="text-2xl font-bold">設定</h1>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('account')}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === 'account'
                ? 'border-black text-black'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            帳號設定
          </button>
          <button
            onClick={() => setActiveTab('chat-style')}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === 'chat-style'
                ? 'border-black text-black'
                : 'border-transparent text-gray-400 hover:text-gray-600'
            }`}
          >
            聊天發文風格
          </button>
        </div>

        {/* ── 帳號設定 ── */}
        {activeTab === 'account' && (
          <div className="space-y-6">
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

            <button
              onClick={handleLogout}
              className="w-full border border-gray-200 text-gray-400 rounded-lg py-2 text-sm hover:border-gray-400 hover:text-black transition-colors"
            >
              登出
            </button>
          </div>
        )}

        {/* ── 聊天發文風格 ── */}
        {activeTab === 'chat-style' && (
          <div className="space-y-6">
            <p className="text-sm text-gray-500">
              設定你的聊天發文風格偏好，AI 在生成貼文草稿時會參考這些設定。
            </p>

            {loadingStyle ? (
              <div className="text-sm text-gray-400 py-4">載入中…</div>
            ) : (
              <>
                {/* 風格 Prompt */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    話題風格描述
                  </label>
                  <p className="text-xs text-gray-400">
                    描述你希望貼文呈現的風格、語氣或特色，例如：「輕鬆幽默、口語化，偶爾用台語詞彙」
                  </p>
                  <textarea
                    value={chatStylePrompt}
                    onChange={(e) => setChatStylePrompt(e.target.value)}
                    rows={5}
                    placeholder="例如：語氣親切自然，像在跟好朋友說話。句子不要太長，喜歡用問句跟讀者互動。偶爾加入一點幽默或自嘲。"
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black resize-none"
                  />
                </div>

                {/* 參考圖 URL */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">
                    風格參考圖 URL（選填）
                  </label>
                  <p className="text-xs text-gray-400">
                    貼上一張能代表你發文風格的圖片網址，AI 生圖時會參考此視覺風格
                  </p>
                  <input
                    type="url"
                    value={chatStyleImage}
                    onChange={(e) => setChatStyleImage(e.target.value)}
                    placeholder="https://..."
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black"
                  />
                  {chatStyleImage && (
                    <img
                      src={chatStyleImage}
                      alt="風格參考圖預覽"
                      className="mt-2 rounded-xl max-h-40 object-cover border border-gray-100"
                      onError={(e) => {
                        ;(e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                  )}
                </div>

                {/* 儲存 */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleSaveChatStyle}
                    disabled={saving}
                    className="px-6 py-2.5 bg-black text-white text-sm font-medium rounded-xl hover:bg-gray-800 disabled:opacity-50 transition-colors"
                  >
                    {saving ? '儲存中…' : '儲存設定'}
                  </button>
                  {saveMsg && (
                    <span
                      className={`text-sm ${
                        saveMsg.includes('失敗') ? 'text-red-500' : 'text-green-600'
                      }`}
                    >
                      {saveMsg}
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </main>
    </>
  )
}
