'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import Navbar from '@/components/Navbar'
import ToastContainer from '@/components/Toast'
import { useToast } from '@/hooks/useToast'
import { cancelScheduledPost } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ScheduledPost {
  post_id: string
  date: string
  scene: string
  caption: string
  image_url?: string
  status: string
  scheduled_at?: string
  scheduledAt?: string
  job_id?: string
  hashtags?: string[]
}

export default function SchedulePage() {
  const router = useRouter()
  const { userId, isAuthenticated, isLoading } = useUser()
  const { toasts, addToast, removeToast } = useToast()
  const [posts, setPosts] = useState<ScheduledPost[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isLoading) return
    if (!isAuthenticated) { router.replace('/onboarding'); return }

    fetch(`${API}/api/life-stream/schedule/${userId}`)
      .then(r => r.json())
      .then(data => {
        const all: ScheduledPost[] = data.posts || []
        const scheduled = all
          .filter(p => p.status === 'scheduled' && (p.scheduled_at || p.scheduledAt))
          .sort((a, b) =>
            (a.scheduled_at || a.scheduledAt || '').localeCompare(b.scheduled_at || b.scheduledAt || '')
          )
        setPosts(scheduled)
      })
      .catch(() => addToast('載入排程失敗', 'error'))
      .finally(() => setLoading(false))
  }, [isAuthenticated, isLoading, userId, router])

  const handleCancel = async (post: ScheduledPost) => {
    if (!post.job_id) { addToast('找不到 job_id，無法取消', 'error'); return }
    try {
      await cancelScheduledPost(post.job_id)
      setPosts(prev => prev.filter(p => p.post_id !== post.post_id))
      addToast('已取消排程', 'success')
    } catch (e) {
      addToast(`取消失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  const goToPost = (post: ScheduledPost) => {
    router.push(`/dashboard?select=${post.post_id}`)
  }

  return (
    <>
      <Navbar />
      <main className="min-h-screen p-6 max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">即將發布</h1>
          <p className="text-gray-500 text-sm mt-1">點擊貼文可前往編輯內容</p>
        </div>

        {loading ? (
          <p className="text-gray-400 text-sm">載入中...</p>
        ) : posts.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <p className="text-4xl mb-4">📅</p>
            <p>目前沒有排程任務</p>
            <a href="/dashboard" className="mt-4 inline-block text-sm text-black underline">
              前往內容頁建立排程
            </a>
          </div>
        ) : (
          <div className="border rounded-2xl overflow-hidden">
            <div className="divide-y">
              {posts.map(post => {
                const scheduledTime = post.scheduled_at || post.scheduledAt
                return (
                  <div key={post.post_id} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors">
                    {/* Thumbnail — click to go to dashboard */}
                    <button onClick={() => goToPost(post)} className="w-14 h-14 rounded-xl overflow-hidden bg-gray-100 flex-shrink-0">
                      {post.image_url
                        ? <img src={post.image_url} alt={post.scene} className="w-full h-full object-cover" />
                        : <div className="w-full h-full flex items-center justify-center text-gray-300 text-xl">🖼️</div>}
                    </button>

                    {/* Info — click to go to dashboard */}
                    <button onClick={() => goToPost(post)} className="flex-1 min-w-0 text-left">
                      <p className="text-sm font-medium text-gray-800 truncate">{post.caption}</p>
                      {post.hashtags && post.hashtags.length > 0 && (
                        <p className="text-xs text-blue-400 truncate mt-0.5">{post.hashtags.join(' ')}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-0.5">{post.date}</p>
                    </button>

                    {/* Scheduled time + cancel */}
                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                      {scheduledTime && (
                        <div className="text-right">
                          <p className="text-xs font-semibold text-purple-700">
                            {new Date(scheduledTime).toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' })}
                          </p>
                          <p className="text-xs text-purple-500">
                            {new Date(scheduledTime).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      )}
                      <button
                        onClick={() => handleCancel(post)}
                        className="text-xs text-red-400 hover:text-red-600 border border-red-100 hover:border-red-300 px-2 py-0.5 rounded-lg transition-colors"
                      >
                        取消排程
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </main>
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </>
  )
}
