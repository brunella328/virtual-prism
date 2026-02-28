'use client'

interface AddPostModalProps {
  date: string               // "2026-03-15"
  onConfirm: () => void
  onCancel: () => void
  loading: boolean
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('zh-TW', { month: 'long', day: 'numeric', weekday: 'short' })
}

export default function AddPostModal({ date, onConfirm, onCancel, loading }: AddPostModalProps) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-xl">
        <div>
          <h3 className="font-bold text-lg">新增貼文</h3>
          <p className="text-gray-500 text-sm mt-1">
            為 <span className="font-medium text-black">{formatDateLabel(date)}</span> 生成一篇 AI 貼文？
          </p>
        </div>

        <p className="text-xs text-gray-400">
          AI 將根據你的人設自動規劃場景、文案並生成圖片，約需 30–60 秒。
        </p>

        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 bg-black text-white py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <span className="animate-spin inline-block">🌈</span>
                生成中...
              </>
            ) : '生成'}
          </button>
          <button
            onClick={onCancel}
            disabled={loading}
            className="flex-1 border py-2.5 rounded-xl text-sm hover:bg-gray-50 disabled:opacity-40"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  )
}
