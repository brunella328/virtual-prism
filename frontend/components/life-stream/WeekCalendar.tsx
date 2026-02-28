'use client'
import { useState } from 'react'

interface DayContent {
  day: number
  date: string
  scene: string
  caption: string
  scene_prompt?: string
  image_url?: string
  seed: number
  status: 'draft' | 'approved' | 'published' | 'rejected' | 'regenerating'
  hashtags?: string[]
  scheduledAt?: string
}

interface WeekCalendarProps {
  schedule: DayContent[]
  onRegenerate: (day: number, instruction?: string) => void
  onPublishNow: (day: number) => void
  onSchedule: (day: number, publishAt: string) => void
  onSaveContent: (day: number, caption: string, scenePrompt: string) => Promise<void>
  igConnected: boolean
  pendingRegen: { day: number; image_url: string } | null
  onApplyRegen: () => void
  onDiscardRegen: () => void
}

const STATUS_BADGE: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  approved: 'bg-green-100 text-green-700',
  published: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-600',
  regenerating: 'bg-yellow-100 text-yellow-700',
}
const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', approved: '已核准', published: '已發布',
  rejected: '需重繪', regenerating: '重繪中',
}

export default function WeekCalendar({
  schedule, onRegenerate,
  onPublishNow, onSchedule, onSaveContent, igConnected,
  pendingRegen, onApplyRegen, onDiscardRegen,
}: WeekCalendarProps) {
  const [selected, setSelected] = useState<DayContent | null>(null)
  const [regenInstruction, setRegenInstruction] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editCaption, setEditCaption] = useState('')
  const [editScenePrompt, setEditScenePrompt] = useState('')
  const [saving, setSaving] = useState(false)

  // Keep selected in sync with schedule updates
  const selectedItem = selected ? schedule.find(s => s.day === selected.day) ?? selected : null

  return (
    <div className="space-y-4">
      {/* 網格 */}
      <div className="grid grid-cols-3 gap-3">
        {schedule.map((item) => (
          <button
            key={item.day}
            onClick={() => { setSelected(item); setConfirmPublish(false); setScheduleTime(''); setEditMode(false) }}
            className={`rounded-xl border-2 p-2 text-left transition-all hover:shadow-md ${
              selectedItem?.day === item.day ? 'border-black' : 'border-gray-100'
            }`}
          >
            {/* 圖片縮圖 */}
            <div className="aspect-square rounded-lg bg-gray-100 mb-2 overflow-hidden relative">
              {item.image_url ? (
                <img src={item.image_url} alt={item.scene} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl">🖼️</div>
              )}
              {item.status === 'regenerating' && (
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                  <div className="text-white text-xl animate-spin">🔄</div>
                </div>
              )}
            </div>
            <p className="text-xs text-gray-400">{item.date}</p>
            <p className="text-xs font-medium truncate">{item.scene}</p>
            <span className={`text-xs px-1.5 py-0.5 rounded-full mt-1 inline-block ${STATUS_BADGE[item.status]}`}>
              {STATUS_LABEL[item.status]}
            </span>
          </button>
        ))}
      </div>

      {/* 重繪確認彈窗 */}
      {pendingRegen && (
        <div className="border-2 border-yellow-300 rounded-2xl p-5 bg-yellow-50 space-y-4">
          <p className="font-semibold text-sm text-yellow-800">重繪完成 — 確認是否套用新圖片？</p>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-gray-400 text-center">原圖</p>
              <div className="aspect-square rounded-xl overflow-hidden bg-gray-100">
                {schedule.find(s => s.day === pendingRegen.day)?.image_url ? (
                  <img
                    src={schedule.find(s => s.day === pendingRegen.day)!.image_url}
                    alt="原圖"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-3xl">🖼️</div>
                )}
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-gray-400 text-center">新圖</p>
              <div className="aspect-square rounded-xl overflow-hidden bg-gray-100">
                <img src={pendingRegen.image_url} alt="新圖" className="w-full h-full object-cover" />
              </div>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onApplyRegen}
              className="flex-1 bg-black text-white py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800"
            >
              套用新圖
            </button>
            <button
              onClick={onDiscardRegen}
              className="flex-1 border py-2.5 rounded-xl text-sm hover:bg-gray-50"
            >
              捨棄
            </button>
          </div>
        </div>
      )}

      {/* 詳細面板 */}
      {selectedItem && (
        <div className="border rounded-2xl p-6 bg-white space-y-4">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="font-bold text-lg">Day {selectedItem.day} — {selectedItem.scene}</h3>
              <p className="text-sm text-gray-400">{selectedItem.date}</p>
            </div>
            <span className={`text-sm px-3 py-1 rounded-full ${STATUS_BADGE[selectedItem.status]}`}>
              {STATUS_LABEL[selectedItem.status]}
            </span>
          </div>

          {/* 大圖 */}
          <div className="aspect-square max-w-sm mx-auto rounded-xl bg-gray-100 overflow-hidden relative">
            {selectedItem.image_url ? (
              <img src={selectedItem.image_url} alt={selectedItem.scene} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-5xl">🖼️</div>
            )}
            {selectedItem.status === 'regenerating' && (
              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                <div className="text-white text-3xl animate-spin">🔄</div>
              </div>
            )}
          </div>

          {/* 文案 */}
          {editMode ? (
            <div className="bg-gray-50 rounded-xl p-4 space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">貼文文案</label>
                <textarea
                  value={editCaption}
                  onChange={e => setEditCaption(e.target.value)}
                  rows={4}
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white resize-none"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">重繪方向（scene prompt）</label>
                <textarea
                  value={editScenePrompt}
                  onChange={e => setEditScenePrompt(e.target.value)}
                  rows={3}
                  placeholder="描述畫面場景與氛圍，重繪時會使用此內容..."
                  className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white resize-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    setSaving(true)
                    await onSaveContent(selectedItem.day, editCaption, editScenePrompt)
                    setSaving(false)
                    setEditMode(false)
                  }}
                  disabled={saving}
                  className="flex-1 bg-black text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-40"
                >
                  {saving ? '儲存中...' : '儲存'}
                </button>
                <button
                  onClick={() => setEditMode(false)}
                  disabled={saving}
                  className="flex-1 border py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40"
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-xl p-4 group relative">
              <button
                onClick={() => {
                  setEditCaption(selectedItem.caption)
                  setEditScenePrompt(selectedItem.scene_prompt || '')
                  setEditMode(true)
                }}
                className="absolute top-3 right-3 text-xs text-gray-400 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-200"
              >
                ✏️ 編輯
              </button>
              <p className="text-sm pr-12">{selectedItem.caption}</p>
              {selectedItem.hashtags && (
                <p className="text-xs text-blue-500 mt-2">{selectedItem.hashtags.join(' ')}</p>
              )}
            </div>
          )}

          {/* 重繪 */}
          <div className="flex gap-2">
            <input
              value={regenInstruction}
              onChange={e => setRegenInstruction(e.target.value)}
              placeholder="重繪指令（選填）：修復手指、改為戶外..."
              className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
              disabled={selectedItem.status === 'regenerating'}
            />
            <button
              onClick={() => { onRegenerate(selectedItem.day, regenInstruction); setRegenInstruction('') }}
              disabled={selectedItem.status === 'regenerating'}
              className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40"
            >
              🔄 重繪
            </button>
          </div>

          {/* 發布區塊（已連結 IG 才顯示） */}
          {igConnected && selectedItem.status !== 'regenerating' && (
            <div className="border-t pt-4 space-y-3">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">發布</p>

              {selectedItem.scheduledAt ? (
                <div className="flex items-center justify-between bg-blue-50 rounded-xl px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-blue-800">已排程</p>
                    <p className="text-xs text-blue-600">
                      {new Date(selectedItem.scheduledAt).toLocaleString('zh-TW')}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  {/* 確認彈窗 */}
                  {confirmPublish ? (
                    <div className="border rounded-xl p-4 space-y-3 bg-gray-50">
                      <p className="text-sm font-medium">確認立即發布到 Instagram？</p>
                      {selectedItem.image_url && (
                        <img src={selectedItem.image_url} alt="" className="w-24 h-24 object-cover rounded-lg" />
                      )}
                      <p className="text-xs text-gray-500 line-clamp-2">{selectedItem.caption}</p>
                      <div className="flex gap-2">
                        <button onClick={() => { onPublishNow(selectedItem.day); setConfirmPublish(false) }}
                          className="flex-1 bg-black text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800">
                          確認發布
                        </button>
                        <button onClick={() => setConfirmPublish(false)}
                          className="flex-1 border py-2 rounded-lg text-sm hover:bg-gray-50">
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button onClick={() => setConfirmPublish(true)}
                      className="w-full border py-2.5 rounded-xl text-sm font-medium hover:bg-gray-50">
                      立即發布
                    </button>
                  )}

                  {/* 排程 */}
                  <div className="flex gap-2 items-center">
                    <input
                      type="datetime-local"
                      value={scheduleTime}
                      onChange={e => setScheduleTime(e.target.value)}
                      min={new Date(Date.now() + 60000).toISOString().slice(0, 16)}
                      className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
                    />
                    <button
                      onClick={() => { if (scheduleTime) { onSchedule(selectedItem.day, scheduleTime); setScheduleTime('') } }}
                      disabled={!scheduleTime}
                      className="px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-gray-800 disabled:opacity-40"
                    >
                      排程
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
