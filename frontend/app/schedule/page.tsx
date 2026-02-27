'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Navbar from '@/components/Navbar'
import ToastContainer from '@/components/Toast'
import { useToast } from '@/hooks/useToast'
import { getScheduledPosts, cancelScheduledPost } from '@/lib/api'

export default function SchedulePage() {
  const router = useRouter()
  const { toasts, addToast, removeToast } = useToast()
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const userId = localStorage.getItem('vp_user_id')
    if (!userId) { router.replace('/onboarding'); return }

    getScheduledPosts(userId)
      .then(data => setJobs(data.scheduled_posts || []))
      .catch(() => addToast('載入排程失敗', 'error'))
      .finally(() => setLoading(false))
  }, [router])

  const handleCancel = async (jobId: string) => {
    try {
      await cancelScheduledPost(jobId)
      setJobs(prev => prev.filter(j => j.job_id !== jobId))
      addToast('已取消排程', 'success')
    } catch (e) {
      addToast(`取消失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  return (
    <>
      <Navbar />
      <main className="min-h-screen p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">排程紀錄</h1>

        {loading ? (
          <p className="text-gray-400">載入中...</p>
        ) : jobs.length === 0 ? (
          <div className="text-center py-20 text-gray-400">
            <p className="text-4xl mb-4">📅</p>
            <p>目前沒有排程任務</p>
            <a href="/dashboard" className="mt-4 inline-block text-sm text-black underline">
              前往內容頁建立排程
            </a>
          </div>
        ) : (
          <ul className="space-y-3">
            {jobs.map(job => (
              <li key={job.job_id}
                className="flex items-center justify-between px-5 py-4 border border-gray-100 rounded-2xl bg-white">
                <div>
                  <p className="font-medium text-sm">
                    {job.name.split(':').slice(1).join(':') || job.name}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {job.run_date
                      ? new Date(job.run_date).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })
                      : '時間未知'}
                  </p>
                </div>
                <button
                  onClick={() => handleCancel(job.job_id)}
                  className="text-xs text-red-500 hover:text-red-700 border border-red-200 hover:border-red-400 px-3 py-1.5 rounded-lg transition-colors"
                >
                  取消
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </>
  )
}
