'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import { apiGet, apiPost } from '@/lib/api'
import Navbar from '@/components/Navbar'

interface PersonaInfo {
  id: string
  name: string
}

export default function NewChatPostPage() {
  const router = useRouter()
  const { userId, isAuthenticated, isLoading } = useUser()

  const [personas, setPersonas] = useState<PersonaInfo[]>([])
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>('')
  const [topic, setTopic] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [questions, setQuestions] = useState<string[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadingPersonas, setLoadingPersonas] = useState(true)

  // 載入使用者的 persona（persona_id = userId）
  useEffect(() => {
    if (\!userId) return

    const fetchPersona = async () => {
      setLoadingPersonas(true)
      try {
        const data = await apiGet(`/api/genesis/persona/${userId}`)
        if (data?.persona) {
          const persona: PersonaInfo = {
            id: userId,
            name: data.persona.name || '我的人設',
          }
          setPersonas([persona])
          setSelectedPersonaId(userId)
        }
      } catch (_e) {
        // 尚未建立人設，仍允許使用 userId 送出
        setPersonas([])
        setSelectedPersonaId(userId)
      } finally {
        setLoadingPersonas(false)
      }
    }

    fetchPersona()
  }, [userId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (\!topic.trim() || \!selectedPersonaId) return

    setSubmitting(true)
    setError(null)
    setQuestions([])
    setSessionId(null)

    try {
      const data = await apiPost('/api/chat-sessions', {
        persona_id: selectedPersonaId,
        topic: topic.trim(),
      })
      setSessionId(data.session_id)
      setQuestions(data.questions || [])
    } catch (e: any) {
      setError(e?.message || '發生錯誤，請稍後再試')
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 text-sm">載入中…</p>
      </div>
    )
  }

  if (\!isAuthenticated) {
    router.push('/login')
    return null
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">建立聊天發文</h1>
        <p className="text-gray-500 text-sm mb-8">
          輸入話題，AI 會幫你生成引導問題，協助整理貼文思路。
        </p>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5"
        >
          {/* Persona 選擇 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">人設</label>
            {loadingPersonas ? (
              <div className="h-10 bg-gray-100 rounded-lg animate-pulse" />
            ) : personas.length > 0 ? (
              <select
                value={selectedPersonaId}
                onChange={(e) => setSelectedPersonaId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                required
              >
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="text-sm text-amber-600 bg-amber-50 rounded-lg px-3 py-2.5 border border-amber-100">
                尚未建立人設，將使用帳號 ID 作為 persona。
              </div>
            )}
          </div>

          {/* 話題輸入 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">話題</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="例如：我第一次嘗試冷水游泳的經歷"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              required
              maxLength={200}
            />
            <p className="text-xs text-gray-400 mt-1 text-right">{topic.length}/200</p>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2.5 border border-red-100">
              ❌ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || \!topic.trim()}
            className="w-full bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? '⏳ AI 生成問題中…' : '✨ 生成引導問題'}
          </button>
        </form>

        {/* 問題清單 */}
        {questions.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-900">引導問題</h2>
              {sessionId && (
                <span className="text-xs text-gray-400 font-mono">
                  Session: {sessionId.slice(0, 8)}…
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500 mb-4">
              針對「{topic}」的引導問題，幫你整理貼文思路：
            </p>
            <ol className="space-y-3">
              {questions.map((q, i) => (
                <li
                  key={i}
                  className="flex gap-3 bg-white border border-gray-100 rounded-xl px-4 py-3.5 shadow-sm"
                >
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-sm text-gray-800 leading-relaxed">{q}</p>
                </li>
              ))}
            </ol>

            <div className="mt-6 text-center">
              <button
                onClick={() => {
                  setQuestions([])
                  setSessionId(null)
                  setTopic('')
                  setError(null)
                }}
                className="text-sm text-gray-500 hover:text-gray-700 underline"
              >
                重新輸入話題
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
