'use client'
import { useState, useEffect } from 'react'
import WeekCalendar from '@/components/life-stream/WeekCalendar'

export default function DashboardPage() {
  const [schedule, setSchedule] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // TODO: 從 API 取得排程（串接 persona_id）
    // 暫時用 mock 資料展示 UI
    const mockSchedule = Array.from({ length: 7 }, (_, i) => ({
      day: i + 1,
      date: new Date(Date.now() + i * 86400000).toISOString().split('T')[0],
      scene: ['海邊晨跑', '咖啡廳工作', '衝浪練習', '市集閒逛', '健身房', '好友聚餐', '夕陽海邊'][i],
      caption: ['開始美好的一天 🌊', '咖啡 + 工作 = 完美 ☕', '浪來了！🤙', '挖到寶！🎁', '破 PR 了 💪', '最棒的朋友們 🥂', '這個時刻 ✨'][i],
      image_url: null,
      seed: Math.floor(Math.random() * 99999),
      status: 'draft' as const,
      hashtags: ['#生活', '#日常', '#lifestyle'],
    }))
    setSchedule(mockSchedule)
    setLoading(false)
  }, [])

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
  const handleRegenerate = (day: number, instruction?: string) => {
    console.log(`Regenerating day ${day} with instruction: ${instruction}`)
    // TODO: 呼叫 /api/image/regenerate
  }

  const approvedCount = schedule.filter(d => d.status === 'approved').length

  return (
    <main className="min-h-screen p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">內容審核後台</h1>
          <p className="text-gray-500 text-sm mt-1">本週排程 · {approvedCount}/7 已核准</p>
        </div>
        {approvedCount > 0 && (
          <a href="/publish"
            className="bg-black text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800">
            排程發布 {approvedCount} 則 →
          </a>
        )}
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">載入中...</div>
      ) : (
        <WeekCalendar
          schedule={schedule}
          onApprove={handleApprove}
          onReject={handleReject}
          onRegenerate={handleRegenerate}
        />
      )}
    </main>
  )
}
