'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import { storage } from '@/lib/storage'
import MonthCalendar, { type DayContent } from '@/components/life-stream/MonthCalendar'
import AddPostModal from '@/components/life-stream/AddPostModal'
import Navbar from '@/components/Navbar'
import ToastContainer from '@/components/Toast'
import { useToast } from '@/hooks/useToast'
import { getInstagramStatus, publishNow, scheduleInstagramPosts } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const STATUS_BADGE: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  approved: 'bg-green-100 text-green-700',
  published: 'bg-blue-100 text-blue-700',
  rejected: 'bg-red-100 text-red-600',
  regenerating: 'bg-yellow-100 text-yellow-700',
}
const STATUS_LABEL: Record<string, string> = {
  draft: '草稿', approved: '已核准', published: '已發布',
  rejected: '需重繪', regenerating: '重繪中', scheduled: '已排程',
}

export default function DashboardPage() {
  const router = useRouter()
  const { userId, isAuthenticated, isLoading, appearancePrompt } = useUser()
  const { toasts, addToast, removeToast } = useToast()

  // Schedule state
  const [schedule, setSchedule] = useState<DayContent[]>([])
  const [loading, setLoading] = useState(true)
  const [igConnected, setIgConnected] = useState(false)

  // Selected post + detail panel state
  const [selectedPost, setSelectedPost] = useState<DayContent | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [editCaption, setEditCaption] = useState('')
  const [editScenePrompt, setEditScenePrompt] = useState('')
  const [saving, setSaving] = useState(false)
  const [regenInstruction, setRegenInstruction] = useState('')
  const [scheduleTime, setScheduleTime] = useState('')
  const [confirmPublish, setConfirmPublish] = useState(false)
  const [publishing, setPublishing] = useState(false)

  // Regen confirm state
  const [pendingRegen, setPendingRegen] = useState<{ post_id: string; image_url: string; image_prompt: string } | null>(null)
  const [regenRefImage, setRegenRefImage] = useState<File | null>(null)
  const [regenRefPreview, setRegenRefPreview] = useState<string | null>(null)

  // Add post modal
  const [addPostDate, setAddPostDate] = useState<string | null>(null)
  const [addPostLoading, setAddPostLoading] = useState(false)

  // Calendar focus
  const [calendarFocusDate, setCalendarFocusDate] = useState<string | undefined>(undefined)

  // Keep selectedPost in sync with schedule updates
  const selectedItem = selectedPost
    ? (schedule.find(s => s.post_id === selectedPost.post_id) ?? selectedPost)
    : null

  // Auth guard + IG status
  useEffect(() => {
    if (isLoading) return
    if (!isAuthenticated) { router.replace('/onboarding'); return }
    getInstagramStatus(userId!)
      .then(s => setIgConnected(!!s.connected))
      .catch(() => setIgConnected(false))
  }, [isAuthenticated, isLoading, userId, router])

  // Load schedule — if empty, generate today's post only
  useEffect(() => {
    if (!userId) return
    fetch(`${API}/api/life-stream/schedule/${userId}`)
      .then(r => r.json())
      .then(data => {
        const posts = data.posts || []
        if (posts.length > 0) {
          setSchedule(posts)
          storage.setSchedule(posts)
          const todayStr = new Date().toISOString().slice(0, 10)
          const todayPost = posts.find((p: DayContent) => p.date === todayStr)
          if (todayPost) setSelectedPost(todayPost)
          setLoading(false)
        } else {
          generateTodayPost()
        }
      })
      .catch(() => {
        const cached = storage.getSchedule() as DayContent[] | null
        if (cached && cached.length > 0) {
          setSchedule(cached)
          setLoading(false)
          return
        }
        generateTodayPost()
      })
  }, [userId])

  // Generate single post for today (first-load only)
  const generateTodayPost = async () => {
    if (!userId) { setLoading(false); return }
    setLoading(true)
    const today = new Date().toISOString().slice(0, 10)
    try {
      const fd = new FormData()
      fd.append('date', today)
      fd.append('appearance_prompt', appearancePrompt || '')
      const res = await fetch(`${API}/api/life-stream/generate-post/${userId}`, {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const post = await res.json()
      setSchedule([post])
      storage.setSchedule([post])
      addToast('今日貼文已生成 ✓', 'success')
    } catch (e) {
      addToast(`生成失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  // Add post for a specific date (from calendar click)
  const handleAddPost = async (hint: string, refImage: File | null) => {
    if (!addPostDate || !userId) return
    setAddPostLoading(true)
    try {
      const fd = new FormData()
      fd.append('date', addPostDate)
      fd.append('appearance_prompt', appearancePrompt || '')
      fd.append('user_hint', hint)
      if (refImage) fd.append('reference_image', refImage)
      const res = await fetch(`${API}/api/life-stream/generate-post/${userId}`, {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const post = await res.json()
      setSchedule(prev => {
        const updated = [...prev, post]
        storage.setSchedule(updated)
        return updated
      })
      addToast('貼文已生成 ✓', 'success')
      setAddPostDate(null)
      setSelectedPost(post)
      setCalendarFocusDate(post.date)
    } catch (e) {
      addToast(`生成失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setAddPostLoading(false)
    }
  }

  // Regenerate image
  const handleRegenerate = async (post_id: string, instruction?: string) => {
    const item = schedule.find(s => s.post_id === post_id)
    if (!item || !userId) return
    setSchedule(prev => prev.map(s => s.post_id === post_id ? { ...s, status: 'regenerating' } : s))
    try {
      const fd = new FormData()
      fd.append('scene_prompt', item.scene_prompt || item.image_prompt || '')
      fd.append('instruction', instruction || '')
      fd.append('persona_id', userId)
      if (regenRefImage) fd.append('reference_image', regenRefImage)
      const res = await fetch(`${API}/api/life-stream/regenerate/${post_id}`, {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const result = await res.json()
      setSchedule(prev => prev.map(s => s.post_id === post_id ? { ...s, status: 'draft' } : s))
      setPendingRegen({ post_id, image_url: result.image_url, image_prompt: result.image_prompt })
      setRegenRefImage(null)
      setRegenRefPreview(null)
      addToast('重繪完成，請確認是否套用', 'info')
    } catch (e) {
      setSchedule(prev => prev.map(s => s.post_id === post_id ? { ...s, status: 'draft' } : s))
      addToast(`重繪失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  // Apply regen result
  const handleApplyRegen = async () => {
    if (!pendingRegen || !userId) return
    const { post_id, image_url, image_prompt } = pendingRegen
    setSchedule(prev => {
      const updated = prev.map(s => s.post_id === post_id ? { ...s, image_url, image_prompt } : s)
      storage.setSchedule(updated)
      return updated
    })
    setPendingRegen(null)
    try {
      const res = await fetch(`${API}/api/life-stream/schedule/${userId}/${post_id}/image`, {
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

  // Save caption + scene_prompt
  const handleSaveContent = async (post_id: string, caption: string, scenePrompt: string) => {
    if (!userId) return
    try {
      const res = await fetch(`${API}/api/life-stream/schedule/${userId}/${post_id}/content`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caption, scene_prompt: scenePrompt }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSchedule(prev => {
        const updated = prev.map(s => s.post_id === post_id ? { ...s, caption, scene_prompt: scenePrompt } : s)
        storage.setSchedule(updated)
        return updated
      })
      addToast('已儲存 ✓', 'success')
    } catch (e) {
      addToast(`儲存失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  // Publish now
  const handlePublishNow = async (post_id: string) => {
    const item = schedule.find(s => s.post_id === post_id)
    if (!userId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    setPublishing(true)
    try {
      const result = await publishNow(userId, post_id, item.image_url, item.caption)
      addToast(`發布成功 ✓ Media ID: ${result.media_id}`, 'success')
      setConfirmPublish(false)
      setSchedule(prev => {
        const updated = prev.map(s => s.post_id === post_id ? { ...s, status: 'published' as const } : s)
        storage.setSchedule(updated)
        return updated
      })
      fetch(`${API}/api/life-stream/schedule/${userId}/${post_id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'published' }),
      }).catch(() => {})
    } catch (e) {
      addToast(`發布失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    } finally {
      setPublishing(false)
    }
  }

  // Schedule post
  const handleSchedulePost = async (post_id: string, publishAt: string) => {
    const item = schedule.find(s => s.post_id === post_id)
    if (!userId || !item?.image_url) { addToast('缺少圖片或帳號資料', 'error'); return }
    try {
      await scheduleInstagramPosts(userId, [{
        post_id,
        image_url: item.image_url,
        caption: item.caption,
        publish_at: new Date(publishAt).toISOString(),
      }])
      addToast(`已排程 ✓ ${new Date(publishAt).toLocaleString('zh-TW')}`, 'success')
      setSchedule(prev => {
        const updated = prev.map(s => s.post_id === post_id ? { ...s, scheduledAt: publishAt, status: 'scheduled' as const } : s)
        storage.setSchedule(updated)
        return updated
      })
    } catch (e) {
      addToast(`排程失敗：${e instanceof Error ? e.message : String(e)}`, 'error')
    }
  }

  return (
    <>
      <Navbar />
      <main className="min-h-screen p-6 max-w-2xl mx-auto">
        {loading ? (
          <div className="min-h-[60vh] flex flex-col items-center justify-center">
            <div className="text-5xl mb-4 animate-spin">🌈</div>
            <h2 className="text-xl font-semibold">生成今日貼文中...</h2>
            <p className="text-gray-400 mt-2 text-sm">生圖約需 30-60 秒，請稍候</p>
          </div>
        ) : (
          <div className="space-y-6">
            <div>
              <h1 className="text-2xl font-bold">內容日曆</h1>
              <p className="text-gray-500 text-sm mt-1">點擊日期新增貼文，點擊圖片編輯或重繪</p>
            </div>

            <MonthCalendar
              schedule={schedule}
              focusDate={calendarFocusDate}
              onAddPost={date => { setAddPostDate(date); setSelectedPost(null) }}
              onSelectPost={post => {
                setSelectedPost(post)
                setEditMode(false)
                setConfirmPublish(false)
                setScheduleTime(post.date ? `${post.date}T09:00` : '')
                setRegenInstruction('')
              }}
            />

            {/* Regen confirm */}
            {pendingRegen && (
              <div className="border-2 border-yellow-300 rounded-2xl p-5 bg-yellow-50 space-y-4">
                <p className="font-semibold text-sm text-yellow-800">重繪完成 — 確認是否套用新圖片？</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-gray-400 text-center">原圖</p>
                    <div className="aspect-square rounded-xl overflow-hidden bg-gray-100">
                      {schedule.find(s => s.post_id === pendingRegen.post_id)?.image_url
                        ? <img src={schedule.find(s => s.post_id === pendingRegen.post_id)!.image_url} alt="原圖" className="w-full h-full object-cover" />
                        : <div className="w-full h-full flex items-center justify-center text-3xl">🖼️</div>}
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
                  <button onClick={handleApplyRegen} className="flex-1 bg-black text-white py-2.5 rounded-xl text-sm font-medium hover:bg-gray-800">套用新圖</button>
                  <button onClick={() => setPendingRegen(null)} className="flex-1 border py-2.5 rounded-xl text-sm hover:bg-gray-50">捨棄</button>
                </div>
              </div>
            )}

            {/* Post detail panel */}
            {selectedItem && (
              <div className="border rounded-2xl p-6 bg-white space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-lg">{selectedItem.scene}</h3>
                    <p className="text-sm text-gray-400">{selectedItem.date}</p>
                  </div>
                  <span className={`text-sm px-3 py-1 rounded-full ${STATUS_BADGE[selectedItem.status]}`}>
                    {STATUS_LABEL[selectedItem.status]}
                  </span>
                </div>

                {/* Image */}
                <div className="aspect-square max-w-sm mx-auto rounded-xl bg-gray-100 overflow-hidden relative">
                  {selectedItem.image_url
                    ? <img src={selectedItem.image_url} alt={selectedItem.scene} className="w-full h-full object-cover" />
                    : <div className="w-full h-full flex items-center justify-center text-5xl">🖼️</div>}
                  {selectedItem.status === 'regenerating' && (
                    <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                      <div className="text-white text-3xl animate-spin">🔄</div>
                    </div>
                  )}
                </div>

                {/* Caption */}
                {editMode ? (
                  <div className="bg-gray-50 rounded-xl p-4 space-y-3">
                    <div>
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">貼文文案</label>
                      <textarea value={editCaption} onChange={e => setEditCaption(e.target.value)} rows={4}
                        className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white resize-none" />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">重繪方向（scene prompt）</label>
                      <textarea value={editScenePrompt} onChange={e => setEditScenePrompt(e.target.value)} rows={3}
                        placeholder="描述畫面場景與氛圍，重繪時會使用此內容..."
                        className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white resize-none" />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={async () => {
                          setSaving(true)
                          await handleSaveContent(selectedItem.post_id, editCaption, editScenePrompt)
                          setSaving(false)
                          setEditMode(false)
                        }}
                        disabled={saving}
                        className="flex-1 bg-black text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-40"
                      >{saving ? '儲存中...' : '儲存'}</button>
                      <button onClick={() => setEditMode(false)} disabled={saving}
                        className="flex-1 border py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40">取消</button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-gray-50 rounded-xl p-4 relative">
                    <button
                      onClick={() => { setEditCaption(selectedItem.caption); setEditScenePrompt(selectedItem.scene_prompt || ''); setEditMode(true) }}
                      className="absolute top-3 right-3 text-xs text-gray-400 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-200"
                    >✏️ 編輯</button>
                    <p className="text-sm pr-12">{selectedItem.caption}</p>
                    {selectedItem.hashtags && (
                      <p className="text-xs text-blue-500 mt-2">{selectedItem.hashtags.join(' ')}</p>
                    )}
                  </div>
                )}

                {/* Regen */}
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input value={regenInstruction} onChange={e => setRegenInstruction(e.target.value)}
                      placeholder="重繪指令（選填）：修復手指、改為戶外..."
                      className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300"
                      disabled={selectedItem.status === 'regenerating'} />
                    <button
                      onClick={() => { handleRegenerate(selectedItem.post_id, regenInstruction); setRegenInstruction('') }}
                      disabled={selectedItem.status === 'regenerating'}
                      className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40"
                    >🔄 重繪</button>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="flex-1 border border-dashed border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-400 cursor-pointer hover:bg-gray-50 text-center">
                      {regenRefPreview
                        ? <img src={regenRefPreview} alt="參考圖" className="h-10 mx-auto object-contain rounded" />
                        : '上傳參考圖（選填）'}
                      <input type="file" accept="image/*" className="hidden"
                        disabled={selectedItem.status === 'regenerating'}
                        onChange={e => {
                          const f = e.target.files?.[0] || null
                          setRegenRefImage(f)
                          setRegenRefPreview(f ? URL.createObjectURL(f) : null)
                        }} />
                    </label>
                    {regenRefImage && (
                      <button onClick={() => { setRegenRefImage(null); setRegenRefPreview(null) }}
                        className="text-xs text-gray-400 hover:text-red-500">✕</button>
                    )}
                  </div>
                </div>

                {/* Publish (IG connected only) */}
                {igConnected && selectedItem.status !== 'regenerating' && (
                  <div className="border-t pt-4 space-y-3">
                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">發布</p>
                    {selectedItem.scheduledAt ? (
                      <div className="flex items-center justify-between bg-blue-50 rounded-xl px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-blue-800">已排程</p>
                          <p className="text-xs text-blue-600">{new Date(selectedItem.scheduledAt).toLocaleString('zh-TW')}</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        {confirmPublish ? (
                          <div className="border rounded-xl p-4 space-y-3 bg-gray-50">
                            <p className="text-sm font-medium">確認立即發布到 Instagram？</p>
                            {selectedItem.image_url && <img src={selectedItem.image_url} alt="" className="w-24 h-24 object-cover rounded-lg" />}
                            <p className="text-xs text-gray-500 line-clamp-2">{selectedItem.caption}</p>
                            <div className="flex gap-2">
                              <button onClick={() => handlePublishNow(selectedItem.post_id)}
                                disabled={publishing}
                                className="flex-1 bg-black text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800 disabled:opacity-60">
                                {publishing ? '發布中...' : '確認發布'}
                              </button>
                              <button onClick={() => setConfirmPublish(false)}
                                disabled={publishing}
                                className="flex-1 border py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-40">取消</button>
                            </div>
                          </div>
                        ) : (
                          <button onClick={() => setConfirmPublish(true)}
                            className="w-full border py-2.5 rounded-xl text-sm font-medium hover:bg-gray-50">立即發布</button>
                        )}
                        <div className="flex gap-2 items-center">
                          <input type="datetime-local" value={scheduleTime} onChange={e => setScheduleTime(e.target.value)}
                            min={new Date(Date.now() + 60000).toISOString().slice(0, 16)}
                            className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black" />
                          <button
                            onClick={() => { if (scheduleTime) { handleSchedulePost(selectedItem.post_id, scheduleTime); setScheduleTime('') } }}
                            disabled={!scheduleTime}
                            className="px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-gray-800 disabled:opacity-40"
                          >排程</button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Add post modal */}
      {addPostDate && (
        <AddPostModal
          date={addPostDate}
          loading={addPostLoading}
          onConfirm={(hint, refImage) => handleAddPost(hint, refImage)}
          onCancel={() => setAddPostDate(null)}
        />
      )}

      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </>
  )
}
