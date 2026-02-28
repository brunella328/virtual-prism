'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import { storage } from '@/lib/storage'
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
  const { userId, isAuthenticated, appearancePrompt } = useUser()
  const { toasts, addToast, removeToast } = useToast()
  const [schedule, setSchedule] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [generationStep, setGenerationStep] = useState('')
  const [igConnected, setIgConnected] = useState(false)
  const [pendingRegen, setPendingRegen] = useState<{ day: number; image_url: string; image_prompt: string } | null>(null)

  // Auth guard
  useEffect(() => {
    if (!isAuthenticated) { router.replace('/onboarding'); return }

    getInstagramStatus(userId!)
      .then(s => setIgConnected(!!s.connected))
      .catch(() => setIgConnected(false))
  }, [isAuthenticated, userId, router])

  // Load schedule on mount
  useEffect(() => {
    if (!userId) return

    fetch(`${API}/api/life-stream/schedule/${userId}`)
      .then(r => r.json())
      .then(data => {
        const posts = data.posts || []
        if (posts.length > 0) {
          setSchedule(posts)
          storage.setSchedule(posts)
          setLoading(false)
        } else {
          generateSchedule()
        }
      })
      .catch(() => {
        const cached = storage.getSchedule()
        if (cached && cached.length > 0) {
          setSchedule(cached)
          setLoading(false)
          return
        }
        generateSchedule()
      })
  }, [userId])

  const generateSchedule = async () => {
    if (!userId) {
      addToast('找不到帳號資料，請先完成 Onboarding', 'error')
      setLoading(false)
      return
    }

    setLoading(true)
    setGenerationStep('planning')

    const stepKeys = GENERATION_STEPS.map(s => s.key)
    let stepIdx = 0
    const timer = setInterval(() => {
      stepIdx++
      if (stepIdx < stepKeys.length) setGenerationStep(stepKeys[stepIdx])
      else clearInterval(timer)
    }, 12000)

    try {
      const res = await fetch(`${API}/api/life-stream/generate-schedule/${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 後端從 persona_storage 讀取 persona，只需傳 appearance_prompt
        body: JSON.stringify({ appearance_prompt: appearancePrompt }),
      })
      clearInterval(timer)
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      const newSchedule = data.schedule || data
      setSchedule(newSchedule)
      storage.setSchedule(newSchedule)
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
    if (!item || !userId) return
    setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'regenerating' } : s))
    try {
      const res = await fetch(`${API}/api/life-stream/regenerate/${day}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scene_prompt: item.scene_prompt || item.image_prompt,
          instruction: instruction || '',
          persona_id: userId,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const result = await res.json()
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'draft' } : s))
      setPendingRegen({ day, image_url: result.image_url, image_prompt: result.image_prompt })
      addToast('重繪完成，請確認是否套用', 'info')
    } catch (e) {
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'draft' } : s))
      addToast(`重繪失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handleApplyRegen = async () => {
    if (!pendingRegen || !userId) return
    const { day, image_url, image_prompt } = pendingRegen
    // 先更新本地 state + localStorage
    setSchedule(prev => {
      const updated = prev.map(s => s.day === day
        ? { ...s, image_url, image_prompt }
        : s)
      storage.setSchedule(updated)
      return updated
    })
    setPendingRegen(null)
    // 持久化到後端，避免重整後回到舊圖
    try {
      const res = await fetch(`${API}/api/life-stream/schedule/${userId}/${day}/image`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url, image_prompt }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      addToast('已套用新圖片 ✓', 'success')
    } catch (e) {
      addToast(`圖片已套用，但後端儲存失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handleSaveContent = async (day: number, caption: string, scenePrompt: string) => {
    if (!userId) return
    try {
      const res = await fetch(`${API}/api/life-stream/schedule/${userId}/${day}/content`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caption, scene_prompt: scenePrompt }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSchedule(prev => {
        const updated = prev.map(s => s.day === day ? { ...s, caption, scene_prompt: scenePrompt } : s)
        storage.setSchedule(updated)
        return updated
      })
      addToast('已儲存 ✓', 'success')
    } catch (e) {
      addToast(`儲存失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handlePublishNow = async (day: number) => {
    const item = schedule.find(s => s.day === day)
    if (!userId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    try {
      const result = await publishNow(userId, item.image_url, item.caption)
      addToast(`發布成功 ✓ Media ID: ${result.media_id}`, 'success')
      setSchedule(prev => prev.map(s => s.day === day ? { ...s, status: 'published' } : s))
    } catch (e) {
      addToast(`發布失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const handleSchedulePost = async (day: number, publishAt: string) => {
    const item = schedule.find(s => s.day === day)
    if (!userId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    try {
      await scheduleInstagramPosts(userId, [{
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
                onClick={() => { storage.clearSchedule(); generateSchedule() }}
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
              onSaveContent={handleSaveContent}
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
