'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import WeekCalendar from '@/components/life-stream/WeekCalendar'
import Navbar from '@/components/Navbar'
import ToastContainer from '@/components/Toast'
import { useToast } from '@/hooks/useToast'
import { getInstagramStatus, publishNow, scheduleInstagramPosts } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const GENERATION_STEPS = [
  { key: 'planning', label: '規劃內容中...' },
  { key: 'generating_1', label: '生成圖片 1/3...' },
  { key: 'generating_2', label: '生成圖片 2/3...' },
  { key: 'generating_3', label: '生成圖片 3/3...' },
  { key: 'saving', label: '儲存排程中...' },
]

export default function DashboardPage() {
  const router = useRouter()
  const { toasts, addToast, removeToast } = useToast()
  const [schedule, setSchedule] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [generationStep, setGenerationStep] = useState('')
  const [igConnected, setIgConnected] = useState(false)
  const [pendingRegen, setPendingRegen] = useState<{ day: number; image_url: string; image_prompt: string } | null>(null)

  // Auth guard
  useEffect(() => {
    const userId = localStorage.getItem('vp_user_id')
    if (!userId) { router.replace('/onboarding'); return }

    // Load IG status
    getInstagramStatus(userId)
      .then(s => setIgConnected(!!s.connected))
      .catch(() => setIgConnected(false))
  }, [router])

  // Load schedule on mount
  useEffect(() => {
    const personaId = localStorage.getItem('vp_persona_id') || localStorage.getItem('vp_user_id')
    if (!personaId) { generateSchedule(); return }

    fetch(`${API}/api/life-stream/schedule/${personaId}`)
      .then(r => r.json())
      .then(data => {
        const posts = data.posts || []
        if (posts.length > 0) {
          setSchedule(posts)
          localStorage.setItem('vp_schedule', JSON.stringify(posts))
          setLoading(false)
        } else {
          generateSchedule()
        }
      })
      .catch(() => {
        const cached = localStorage.getItem('vp_schedule')
        if (cached) {
          try {
            const parsed = JSON.parse(cached)
            if (Array.isArray(parsed) && parsed.length > 0) {
              setSchedule(parsed)
              setLoading(false)
              return
            }
          } catch {}
        }
        generateSchedule()
      })
  }, [])

  const generateSchedule = async () => {
    const personaId = localStorage.getItem('vp_persona_id')
    const personaRaw = localStorage.getItem('vp_persona')
    const appearancePrompt = localStorage.getItem('vp_appearance_prompt') || ''
    if (!personaId || !personaRaw) {
      addToast('找不到人設資料，請先完成 Onboarding', 'error')
      setLoading(false)
      return
    }

    setLoading(true)
    setGenerationStep('planning')

    // 模擬分段進度（每步約 12 秒）
    const stepKeys = GENERATION_STEPS.map(s => s.key)
    let stepIdx = 0
    const timer = setInterval(() => {
      stepIdx++
      if (stepIdx < stepKeys.length) setGenerationStep(stepKeys[stepIdx])
      else clearInterval(timer)
    }, 12000)

    try {
      const persona = JSON.parse(personaRaw)
      const res = await fetch(`${API}/api/life-stream/generate-schedule/${personaId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ persona, appearance_prompt: appearancePrompt, face_image_url: '' }),
      })
      clearInterval(timer)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      const newSchedule = data.schedule || data
      setSchedule(newSchedule)
      localStorage.setItem('vp_schedule', JSON.stringify(newSchedule))
      addToast('排程生成完成 ✓', 'success')
    } catch (e) {
      clearInterval(timer)
      addToast(`生成失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setLoading(false)
      setGenerationStep('')
    }
  }

  const handleRegenerate = async (day: number, instruction?: string) => {
    const item = schedule.find(s => s.day === day)
    if (!item) return
    const personaId = localStorage.getItem('vp_persona_id') || localStorage.getItem('vp_user_id') || ''
    setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'regenerating' } : s))
    try {
      const res = await fetch(`${API}/api/life-stream/regenerate/${day}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_prompt: item.scene_prompt || item.image_prompt,
          instruction: instruction || '',
          persona_id: personaId,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const result = await res.json()
      // 不直接覆蓋，先暫存等待用戶確認
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'draft' } : s))
      setPendingRegen({ day, image_url: result.image_url, image_prompt: result.image_prompt })
      addToast('重繪完成，請確認是否套用', 'info')
    } catch (e) {
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'draft' } : s))
      addToast(`重繪失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handleApplyRegen = () => {
    if (!pendingRegen) return
    setSchedule(prev => {
      const updated = prev.map(s => s.day === pendingRegen.day
        ? { ...s, image_url: pendingRegen.image_url, image_prompt: pendingRegen.image_prompt }
        : s)
      localStorage.setItem('vp_schedule', JSON.stringify(updated))
      return updated
    })
    setPendingRegen(null)
    addToast('已套用新圖片 ✓', 'success')
  }

  const handlePublishNow = async (day: number) => {
    const personaId = localStorage.getItem('vp_persona_id') || localStorage.getItem('vp_user_id')
    const item = schedule.find(s => s.day === day)
    if (!personaId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    try {
      const result = await publishNow(personaId, item.image_url, item.caption)
      addToast(`發布成功 ✓ Media ID: ${result.media_id}`, 'success')
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'published' } : s))
    } catch (e) {
      addToast(`發布失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handleSchedulePost = async (day: number, publishAt: string) => {
    const personaId = localStorage.getItem('vp_persona_id') || localStorage.getItem('vp_user_id')
    const item = schedule.find(s => s.day === day)
    if (!personaId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    try {
      await scheduleInstagramPosts(personaId, [{
        image_url: item.image_url,
        caption: item.caption,
        publish_at: new Date(publishAt).toISOString(),
      }])
      addToast(`已排程 ✓ ${new Date(publishAt).toLocaleString('zh-TW')}`, 'success')
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, scheduledAt: publishAt } : s))
    } catch (e) {
      addToast(`排程失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const currentStep = GENERATION_STEPS.find(s => s.key === generationStep)

  return (
    <>
      <Navbar />
      <main className="min-h-screen p-6 max-w-4xl mx-auto">
        {loading ? (
          <div className="min-h-[60vh] flex flex-col items-center justify-center">
            <div className="text-5xl mb-4 animate-spin">🌈</div>
            <h2 className="text-xl font-semibold">{currentStep?.label || '載入中...'}</h2>
            <p className="text-gray-400 mt-2 text-sm">生圖約需 30-60 秒，請稍候</p>
          </div>
        ) : (
          <>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h1 className="text-2xl font-bold">內容審核</h1>
                <p className="text-gray-500 text-sm mt-1">3 天排程</p>
              </div>
              <button
                onClick={() => { localStorage.removeItem('vp_schedule'); generateSchedule() }}
                disabled={!!generationStep}
                className="border px-4 py-2 rounded-xl text-sm hover:bg-gray-50 disabled:opacity-50"
              >
                {generationStep ? '生成中...' : '重新生成'}
              </button>
            </div>

            <WeekCalendar
              schedule={schedule}
              onRegenerate={handleRegenerate}
              onPublishNow={handlePublishNow}
              onSchedule={handleSchedulePost}
              igConnected={igConnected}
              pendingRegen={pendingRegen}
              onApplyRegen={handleApplyRegen}
              onDiscardRegen={() => setPendingRegen(null)}
            />
          </>
        )}
      </main>
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </>
  )
}
