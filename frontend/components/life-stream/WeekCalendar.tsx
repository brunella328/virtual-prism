'use client'
import { useState } from 'react'

interface DayContent {
  day: number
  date: string
  scene: string
  caption: string
  image_url?: string
  seed: number
  status: 'draft' | 'approved' | 'published' | 'rejected'
  hashtags?: string[]
}

interface WeekCalendarProps {
  schedule: DayContent[]
  onApprove: (day: number) => void
  onReject: (day: number) => void
  onRegenerate: (day: number, instruction?: string) => void
}

const STATUS_BADGE: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  approved: 'bg-green-100 text-green-700',
  published: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-600',
}
const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', approved: '已核准', published: '已發布', rejected: '需重繪'
}
const DAY_NAMES = ['一', '二', '三', '四', '五', '六', '日']

export default function WeekCalendar({ schedule, onApprove, onReject, onRegenerate }: WeekCalendarProps) {
  const [selected, setSelected] = useState<DayContent | null>(null)
  const [regenInstruction, setRegenInstruction] = useState('')

  return (
    <div className="space-y-4">
      {/* 週曆網格 */}
      <div className="grid grid-cols-7 gap-2">
        {schedule.map((item) => (
          <button
            key={item.day}
            onClick={() => setSelected(item)}
            className={`rounded-xl border-2 p-2 text-left transition-all hover:shadow-md ${
              selected?.day === item.day ? 'border-black' : 'border-gray-100'
            }`}
          >
            {/* 圖片縮圖 */}
            <div className="aspect-square rounded-lg bg-gray-100 mb-2 overflow-hidden">
              {item.image_url ? (
                <img src={item.image_url} alt={item.scene} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl">🖼️</div>
              )}
            </div>
            {/* 日期 + 狀態 */}
            <p className="text-xs text-gray-400">週{DAY_NAMES[(item.day - 1) % 7]}</p>
            <p className="text-xs font-medium truncate">{item.scene}</p>
            <span className={`text-xs px-1.5 py-0.5 rounded-full mt-1 inline-block ${STATUS_BADGE[item.status]}`}>
              {STATUS_LABEL[item.status]}
            </span>
          </button>
        ))}
      </div>

      {/* 詳細面板 */}
      {selected && (
        <div className="border rounded-2xl p-6 bg-white space-y-4">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="font-bold text-lg">Day {selected.day} — {selected.scene}</h3>
              <p className="text-sm text-gray-400">{selected.date}</p>
            </div>
            <span className={`text-sm px-3 py-1 rounded-full ${STATUS_BADGE[selected.status]}`}>
              {STATUS_LABEL[selected.status]}
            </span>
          </div>

          {/* 大圖 */}
          <div className="aspect-square max-w-sm mx-auto rounded-xl bg-gray-100 overflow-hidden">
            {selected.image_url ? (
              <img src={selected.image_url} alt={selected.scene} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-5xl">🖼️</div>
            )}
          </div>

          {/* 文案 */}
          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-sm">{selected.caption}</p>
            {selected.hashtags && (
              <p className="text-xs text-blue-500 mt-2">{selected.hashtags.join(' ')}</p>
            )}
          </div>

          {/* 重繪指令 */}
          <div className="flex gap-2">
            <input
              value={regenInstruction}
              onChange={e => setRegenInstruction(e.target.value)}
              placeholder="重繪指令（選填）：修復手指、改為戶外..."
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
            />
            <button
              onClick={() => { onRegenerate(selected.day, regenInstruction); setRegenInstruction('') }}
              className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
            >
              🔄 重繪
            </button>
          </div>

          {/* 核准 / 捨棄 */}
          {selected.status === 'draft' || selected.status === 'rejected' ? (
            <div className="flex gap-3">
              <button
                onClick={() => onApprove(selected.day)}
                className="flex-1 bg-black text-white py-2.5 rounded-xl font-medium hover:bg-gray-800"
              >
                ✅ 核准
              </button>
              <button
                onClick={() => onReject(selected.day)}
                className="flex-1 border py-2.5 rounded-xl font-medium hover:bg-gray-50 text-red-500 border-red-200"
              >
                ✗ 捨棄
              </button>
            </div>
          ) : (
            <button
              onClick={() => onApprove(selected.day)}
              className="w-full border py-2.5 rounded-xl font-medium hover:bg-gray-50"
            >
              取消核准
            </button>
          )}
        </div>
      )}
    </div>
  )
}
