'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import WeekCalendar from '@/components/life-stream/WeekCalendar'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function DashboardPage() {
  const router = useRouter()
  const [schedule, setSchedule] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    generateSchedule()
  }, [])

  const generateSchedule = async () => {
    const personaId = localStorage.getItem('vp_persona_id')
    const personaRaw = localStorage.getItem('vp_persona')
    const appearancePrompt = localStorage.getItem('vp_appearance_prompt') || ''

    if (!personaId || !personaRaw) {
      setError('找不到人設資料，請先完成 Onboarding')
      setLoading(false)
      return
    }

    setGenerating(true)
    setLoading(true)
    setError('')

    try {
      const persona = JSON.parse(personaRaw)
      const faceImageUrl = localStorage.getItem('vp_face_image') || ''
      const res = await fetch(`${API}/api/life-stream/generate-schedule/${personaId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          persona,
          appearance_prompt: appearancePrompt,
          face_image_url: faceImageUrl,  // InstantID 人臉圖
        }),
      })
      if (!res.ok) throw new Error(`API ${res.status}`)
      const data = await res.json()
      setSchedule(data.schedule || data)
    } catch (e) {
      setError(`生成失敗：${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setLoading(false)
      setGenerating(false)
    }
  }

  const handleApprove = (day: number) => {
    setSchedule(prev => prev.map(item =>
      item.day === day ? { ...item, status: item.status === 'approved' ? 'draft' : 'approved' } : item
    ))
  }
  const handleReject = (day: number) => {
    setSchedule(prev => prev.map(item =>
      item.day === day ? { ...item, status: 'rejected' } : item
    ))
  }
  const handleRegenerate = async (day: number, instruction?: string) => {
    const item = schedule.find(s => s.day === day)
    if (!item) return
    setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'regenerating' } : s))
    try {
      const res = await fetch(`${API}/api/life-stream/regenerate/${day}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original_prompt: item.image_prompt, instruction }),
      })
      if (res.ok) {
        const updated = await res.json()
        setSchedule(prev => prev.map(s => s.day === day ? { ...s, ...updated, status: 'draft' } : s))
      }
    } catch {
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'draft' } : s))
    }
  }

  const approvedCount = schedule.filter(d => d.status === 'approved').length

  if (error) return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <p className="text-red-500 mb-4">{error}</p>
      <button onClick={() => router.push('/onboarding')} className="bg-black text-white px-6 py-2 rounded-lg">
        回到 Onboarding
      </button>
    </main>
  )

  if (loading) return (
    <main className="min-h-screen flex flex-col items-center justify-center">
      <div className="text-5xl mb-4 animate-spin">🌈</div>
      <h2 className="text-xl font-semibold">{generating ? 'AI 生成 7 天內容 + 圖片中...' : '載入中...'}</h2>
      <p className="text-gray-400 mt-2 text-sm">生圖約需 20-40 秒，請稍候</p>
    </main>
  )

  return (
    <main className="min-h-screen p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">內容審核後台</h1>
          <p className="text-gray-500 text-sm mt-1">本週排程 · {approvedCount}/7 已核准</p>
        </div>
        <div className="flex gap-3">
          <button onClick={generateSchedule} disabled={generating}
            className="border px-4 py-2 rounded-xl text-sm hover:bg-gray-50 disabled:opacity-50">
            {generating ? '生成中...' : '重新生成'}
          </button>
          {approvedCount > 0 && (
            <a href="/publish"
              className="bg-black text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800">
              排程發布 {approvedCount} 則 →
            </a>
          )}
        </div>
      </div>

      <WeekCalendar
        schedule={schedule}
        onApprove={handleApprove}
        onReject={handleReject}
        onRegenerate={handleRegenerate}
      />
    </main>
  )
}
