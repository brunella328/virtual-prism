'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  getInstagramStatus,
  getInstagramAuthUrl,
  disconnectInstagram,
  scheduleInstagramPosts,
  publishNow,
  getScheduledPosts,
  cancelScheduledPost,
  type InstagramStatus,
  type ScheduledPost,
  type ScheduledJobInfo,
} from '@/lib/api'

// A7: 動態 persona_id — 優先用已登入的 ig_user_id，fallback to 'default'
const getPersonaId = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('vp_user_id') || 'default'
  }
  return 'default'
}

type Post = {
  id: number
  day?: number
  scene: string
  caption: string
  image_url: string | null
  status: string
  hashtags?: string[]
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ connected, igUsername }: { connected: boolean; igUsername?: string }) {
  if (connected) {
    return (
      <div className="flex items-center gap-2 px-4 py-2 bg-green-50 border border-green-200 rounded-xl w-fit">
        <span className="text-green-600 text-lg">✅</span>
        <span className="text-sm font-medium text-green-800">
          已連結 @{igUsername || 'instagram'}
        </span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-gray-100 border border-gray-200 rounded-xl w-fit">
      <span className="text-gray-400 text-lg">🔗</span>
      <span className="text-sm text-gray-500">尚未連結 Instagram 帳號</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function PublishPage() {
  // A7: 動態 persona_id
  const [personaId, setPersonaId] = useState<string>('default')

  useEffect(() => {
    setPersonaId(getPersonaId())
  }, [])

  // 從 localStorage 讀取 Dashboard 傳過來的已核准貼文
  const [posts, setPosts] = useState<Post[]>([])

  useEffect(() => {
    // 優先讀已核准清單，備援從完整排程裡撈 approved 項目
    const loadPosts = () => {
      const raw = localStorage.getItem('vp_approved_posts')
      if (raw) {
        try {
          const parsed = JSON.parse(raw)
          if (Array.isArray(parsed) && parsed.length > 0) {
            setPosts(parsed.map((p: Post, i: number) => ({ ...p, id: p.day ?? i + 1 })))
            return
          }
        } catch {}
      }
      // 備援：從 vp_schedule 撈 approved 項目
      const scheduleRaw = localStorage.getItem('vp_schedule')
      if (scheduleRaw) {
        try {
          const schedule = JSON.parse(scheduleRaw)
          const approved = schedule.filter((p: Post) => p.status === 'approved')
          if (approved.length > 0) {
            setPosts(approved.map((p: Post, i: number) => ({ ...p, id: p.day ?? i + 1 })))
            localStorage.setItem('vp_approved_posts', JSON.stringify(approved))
          }
        } catch {}
      }
    }
    loadPosts()
  }, [])

  // IG connection
  const [igStatus, setIgStatus] = useState<InstagramStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)

  // Per-post scheduled datetime
  const [scheduleTimes, setScheduleTimes] = useState<Record<number, string>>({})

  // Scheduled jobs list
  const [scheduledJobs, setScheduledJobs] = useState<ScheduledJobInfo[]>([])
  const [jobsLoading, setJobsLoading] = useState(false)

  // Action states
  const [publishing, setPublishing] = useState<Record<number, boolean>>({})
  const [scheduling, setScheduling] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [successMsg, setSuccessMsg] = useState('')

  // Check URL params for post-OAuth redirect signals
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === 'true') {
      setSuccessMsg('Instagram 帳號已成功連結！')
    }
    if (params.get('error')) {
      setErrors([`OAuth 錯誤：${params.get('error_description') || params.get('error')}`])
    }
  }, [])

  // Load IG connection status
  useEffect(() => {
    if (!personaId) return
    setStatusLoading(true)
    getInstagramStatus(personaId)
      .then(setIgStatus)
      .catch(() => setIgStatus({ connected: false }))
      .finally(() => setStatusLoading(false))
  }, [personaId])

  // Load scheduled jobs
  const loadScheduledJobs = useCallback(() => {
    if (!personaId) return
    setJobsLoading(true)
    getScheduledPosts(personaId)
      .then(data => setScheduledJobs(data.scheduled_posts))
      .catch(() => setScheduledJobs([]))
      .finally(() => setJobsLoading(false))
  }, [personaId])

  useEffect(() => {
    loadScheduledJobs()
  }, [loadScheduledJobs])

  // Connect IG account (OAuth)
  const handleConnect = async () => {
    try {
      const data = await getInstagramAuthUrl(personaId)
      window.location.href = data.auth_url
    } catch {
      setErrors(['無法取得授權網址，請確認後端設定了 INSTAGRAM_APP_ID。'])
    }
  }

  // Disconnect and re-authorize via OAuth
  const handleReconnect = async () => {
    setErrors([])
    setSuccessMsg('')
    try {
      await disconnectInstagram(personaId)
      // A8: 清除本地 session，重新 OAuth 後會以新帳號作為 persona_id
      localStorage.removeItem('vp_user_id')
      localStorage.removeItem('vp_ig_username')
      const data = await getInstagramAuthUrl(personaId)
      window.location.href = data.auth_url
    } catch {
      setErrors(['重新授權失敗，請稍後再試。'])
    }
  }

  // Publish a single post immediately
  const handlePublishNow = async (post: Post) => {
    if (!igStatus?.connected) {
      setErrors(['請先連結 Instagram 帳號。'])
      return
    }
    setPublishing(prev => ({ ...prev, [post.id]: true }))
    setErrors([])
    setSuccessMsg('')
    try {
      const result = await publishNow(personaId, post.image_url, post.caption)
      setSuccessMsg(`✅ 已發布！Media ID: ${result.media_id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErrors([`發布失敗：${msg}`])
    } finally {
      setPublishing(prev => ({ ...prev, [post.id]: false }))
    }
  }

  // Schedule all posts with set times
  const handleScheduleAll = async () => {
    if (!igStatus?.connected) {
      setErrors(['請先連結 Instagram 帳號。'])
      return
    }

    const postsToSchedule: ScheduledPost[] = posts
      .filter(p => scheduleTimes[p.id])
      .map(p => ({
        image_url: p.image_url,
        caption: p.caption,
        publish_at: new Date(scheduleTimes[p.id]).toISOString(),
      }))

    if (postsToSchedule.length === 0) {
      setErrors(['請為至少一則貼文設定排程時間。'])
      return
    }

    setScheduling(true)
    setErrors([])
    setSuccessMsg('')
    try {
      const result = await scheduleInstagramPosts(personaId, postsToSchedule)
      setSuccessMsg(`✅ 已排程 ${result.count} 則貼文！`)
      loadScheduledJobs()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErrors([`排程失敗：${msg}`])
    } finally {
      setScheduling(false)
    }
  }

  // Cancel a scheduled job
  const handleCancelJob = async (jobId: string) => {
    try {
      await cancelScheduledPost(jobId)
      setScheduledJobs(prev => prev.filter(j => j.job_id !== jobId))
      setSuccessMsg('已取消排程。')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErrors([`取消失敗：${msg}`])
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <main className="min-h-screen p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">排程發布</h1>
        <p className="text-gray-500 text-sm mt-1">Instagram Graph API 串接（T9）</p>
      </div>

      {/* Toast messages */}
      {successMsg && (
        <div className="mb-4 px-4 py-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-sm">
          {successMsg}
        </div>
      )}
      {errors.length > 0 && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm space-y-1">
          {errors.map((e, i) => <p key={i}>{e}</p>)}
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* 區塊 A：IG 帳號連結狀態                                            */}
      {/* ---------------------------------------------------------------- */}
      <section className="mb-8 p-5 border border-gray-200 rounded-2xl">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          區塊 A · Instagram 帳號
        </h2>

        {statusLoading ? (
          <div className="text-gray-400 text-sm">載入中...</div>
        ) : (
          <div className="flex items-center gap-4 flex-wrap">
            <StatusBadge connected={!!igStatus?.connected} igUsername={igStatus?.ig_username} />
            {!igStatus?.connected ? (
              <button
                onClick={handleConnect}
                className="px-4 py-2 bg-black text-white text-sm font-medium rounded-xl hover:bg-gray-800 transition-colors"
              >
                連結 Instagram 帳號
              </button>
            ) : (
              <button
                onClick={handleReconnect}
                className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-xl hover:bg-gray-100 transition-colors text-gray-600"
              >
                重新授權 Meta OAuth
              </button>
            )}
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* 區塊 B：待發布內容                                                 */}
      {/* ---------------------------------------------------------------- */}
      <section className="mb-8 p-5 border border-gray-200 rounded-2xl">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
          區塊 B · 待發布內容（{posts.length} 則已核准）
        </h2>

        <div className="space-y-4">
          {posts.map(post => (
            <div key={post.id} className="flex gap-4 p-4 bg-gray-50 rounded-xl">
              {/* Thumbnail */}
              <img
                src={post.image_url}
                alt={post.scene}
                className="w-16 h-16 rounded-lg object-cover flex-shrink-0 bg-gray-200"
                onError={e => { (e.target as HTMLImageElement).src = 'https://placehold.co/64x64?text=IMG' }}
              />

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm">{post.scene}</p>
                <p className="text-gray-500 text-xs mt-0.5 line-clamp-2">{post.caption}</p>

                {/* Datetime picker */}
                <div className="mt-2 flex items-center gap-2 flex-wrap">
                  <label className="text-xs text-gray-400">排程時間：</label>
                  <input
                    type="datetime-local"
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-black"
                    value={scheduleTimes[post.id] || ''}
                    onChange={e => setScheduleTimes(prev => ({ ...prev, [post.id]: e.target.value }))}
                    min={new Date(Date.now() + 60000).toISOString().slice(0, 16)}
                  />
                </div>
              </div>

              {/* Publish now button */}
              <button
                onClick={() => handlePublishNow(post)}
                disabled={publishing[post.id] || !igStatus?.connected}
                className="self-start flex-shrink-0 px-3 py-1.5 border border-gray-300 text-xs rounded-lg hover:bg-black hover:text-white hover:border-black transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {publishing[post.id] ? '發布中…' : '立即發布'}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* 區塊 C：操作按鈕 + 排程清單                                         */}
      {/* ---------------------------------------------------------------- */}
      <section className="mb-8 p-5 border border-gray-200 rounded-2xl">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
          區塊 C · 操作 &amp; 排程清單
        </h2>

        {/* Action buttons */}
        <div className="flex gap-3 flex-wrap mb-6">
          <button
            onClick={handleScheduleAll}
            disabled={scheduling || !igStatus?.connected}
            className="px-5 py-2.5 bg-black text-white text-sm font-medium rounded-xl hover:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {scheduling ? '排程中…' : '排程發布全部'}
          </button>
        </div>

        {/* Scheduled jobs */}
        <div>
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            已建立的排程（{scheduledJobs.length}）
          </h3>

          {jobsLoading ? (
            <div className="text-gray-400 text-sm">載入中...</div>
          ) : scheduledJobs.length === 0 ? (
            <p className="text-gray-400 text-sm">目前沒有排程任務。</p>
          ) : (
            <ul className="space-y-2">
              {scheduledJobs.map(job => (
                <li
                  key={job.job_id}
                  className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-xl text-sm"
                >
                  <div>
                    <p className="font-medium truncate max-w-xs">{job.name.split(':').slice(1).join(':') || job.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {job.run_date
                        ? new Date(job.run_date).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })
                        : '時間未知'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleCancelJob(job.job_id)}
                    className="ml-4 text-xs text-red-500 hover:text-red-700 border border-red-200 hover:border-red-400 px-3 py-1 rounded-lg transition-colors"
                  >
                    取消
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* Back link */}
      <div className="text-center">
        <a href="/dashboard" className="text-sm text-gray-400 hover:text-black transition-colors">
          ← 返回審核後台
        </a>
      </div>
    </main>
  )
}
