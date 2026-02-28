'use client'
import { useState, useMemo } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DayContent {
  day: number
  date: string
  scene: string
  caption: string
  scene_prompt?: string
  image_url?: string
  image_prompt?: string
  seed: number
  status: 'draft' | 'approved' | 'published' | 'rejected' | 'regenerating'
  hashtags?: string[]
  scheduledAt?: string
}

interface MonthCalendarProps {
  schedule: DayContent[]
  onAddPost: (date: string) => void          // trigger AddPostModal
  onSelectPost: (post: DayContent) => void   // open detail panel
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const STATUS_DOT: Record<string, string> = {
  draft: 'bg-gray-400',
  approved: 'bg-green-500',
  published: 'bg-blue-500',
  rejected: 'bg-red-400',
  regenerating: 'bg-yellow-400',
}

function toDateStr(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MonthCalendar({ schedule, onAddPost, onSelectPost }: MonthCalendarProps) {
  const today = new Date()
  const [viewYear, setViewYear] = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())

  const todayStr = toDateStr(today.getFullYear(), today.getMonth(), today.getDate())

  // Group posts by date
  const postsByDate = useMemo(() => {
    const map = new Map<string, DayContent[]>()
    for (const post of schedule) {
      const list = map.get(post.date) ?? []
      list.push(post)
      map.set(post.date, list)
    }
    return map
  }, [schedule])

  // Build calendar grid: leading nulls + date strings
  const daysInMonth = getDaysInMonth(viewYear, viewMonth)
  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay()
  const cells: (string | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) =>
      toDateStr(viewYear, viewMonth, i + 1)
    ),
  ]

  // Month navigation
  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  const monthLabel = `${viewYear} 年 ${viewMonth + 1} 月`

  return (
    <div className="space-y-3">
      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={prevMonth}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
        >
          ‹
        </button>
        <h2 className="font-semibold text-base">{monthLabel}</h2>
        <button
          onClick={nextMonth}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
        >
          ›
        </button>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 text-center">
        {WEEKDAYS.map(d => (
          <div key={d} className="text-xs text-gray-400 py-1">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {cells.map((dateStr, idx) => {
          if (!dateStr) return <div key={`pad-${idx}`} />

          const posts = postsByDate.get(dateStr) ?? []
          const isToday = dateStr === todayStr
          const isPast = dateStr < todayStr
          const dayNum = parseInt(dateStr.slice(8), 10)
          const canAdd = posts.length < 3

          return (
            <div
              key={dateStr}
              className={`
                rounded-lg border min-h-[72px] p-1 flex flex-col gap-0.5 cursor-pointer
                transition-colors
                ${isToday ? 'border-black bg-gray-50' : 'border-gray-100 hover:border-gray-300'}
                ${isPast && posts.length === 0 ? 'opacity-40' : ''}
              `}
              onClick={() => {
                if (posts.length === 0 && canAdd) {
                  onAddPost(dateStr)
                }
              }}
            >
              {/* Day number */}
              <div className="flex items-center justify-between px-0.5">
                <span className={`text-xs font-medium ${isToday ? 'text-black' : 'text-gray-500'}`}>
                  {dayNum}
                </span>
                {canAdd && posts.length > 0 && (
                  <button
                    onClick={e => { e.stopPropagation(); onAddPost(dateStr) }}
                    className="text-gray-300 hover:text-gray-600 text-xs leading-none"
                    title="新增貼文"
                  >
                    +
                  </button>
                )}
              </div>

              {/* Post thumbnails */}
              {posts.length > 0 && (
                <div className={`grid gap-0.5 flex-1 ${posts.length === 1 ? 'grid-cols-1' : 'grid-cols-3'}`}>
                  {posts.map(post => (
                    <div
                      key={post.day}
                      onClick={e => { e.stopPropagation(); onSelectPost(post) }}
                      className="relative aspect-square rounded overflow-hidden bg-gray-200 hover:ring-2 hover:ring-black"
                    >
                      {post.image_url ? (
                        <img
                          src={post.image_url}
                          alt={post.scene}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-[10px]">
                          {post.status === 'regenerating' ? '...' : '?'}
                        </div>
                      )}
                      {/* Status dot */}
                      <span className={`absolute bottom-0.5 right-0.5 w-1.5 h-1.5 rounded-full ${STATUS_DOT[post.status] ?? 'bg-gray-400'}`} />
                    </div>
                  ))}
                </div>
              )}

              {/* Empty day hint */}
              {posts.length === 0 && !isPast && (
                <div className="flex-1 flex items-center justify-center text-gray-200 text-xs">
                  +
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-gray-400 pt-1">
        {[
          { label: '草稿', color: 'bg-gray-400' },
          { label: '已核准', color: 'bg-green-500' },
          { label: '已發布', color: 'bg-blue-500' },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full inline-block ${color}`} />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}
