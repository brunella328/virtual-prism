'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  getPendingReplies,
  sendReply,
  dismissReply,
  getAutoReplySetting,
  setAutoReplySetting,
  getFanList,
  type PendingReply,
  type FanRecord,
} from '@/lib/api'
import { useUser } from '@/contexts/UserContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function isDmExpired(createdAt: string): boolean {
  const created = new Date(createdAt)
  const now = new Date()
  return (now.getTime() - created.getTime()) > 24 * 60 * 60 * 1000
}

// ---------------------------------------------------------------------------
// Mock stats (replace with real API in production)
// ---------------------------------------------------------------------------
const MOCK_STATS = {
  commentsToday: 24,
  sentReplies: 17,
  pendingCount: 0, // will be updated from real data
}

export default function EngagePage() {
  const router = useRouter()
  const { userId, isAuthenticated, isLoading } = useUser()
  const [mode, setMode] = useState<'draft' | 'auto'>('draft')
  const [modeLoading, setModeLoading] = useState(false)
  const [replies, setReplies] = useState<PendingReply[]>([])
  const [repliesLoading, setRepliesLoading] = useState(true)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fans, setFans] = useState<FanRecord[]>([])
  const [fansLoading, setFansLoading] = useState(true)
  const [channelFilter, setChannelFilter] = useState<'all' | 'comment' | 'dm'>('all')

  // ── Redirect if not authenticated ─────────────────────────────────────────
  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/onboarding')
  }, [isLoading, isAuthenticated, router])

  // ── Load mode & replies on mount ──────────────────────────────────────────
  const fetchReplies = useCallback(async () => {
    if (!userId) return
    setRepliesLoading(true)
    try {
      const data = await getPendingReplies(userId)
      setReplies(data.replies)
    } catch {
      setError('無法載入待確認回覆，請稍後再試。')
    } finally {
      setRepliesLoading(false)
    }
  }, [userId])

  const fetchFans = useCallback(async () => {
    if (!userId) return
    setFansLoading(true)
    try {
      const data = await getFanList(userId)
      setFans(data.fans)
    } catch {
      // silently fail — empty state will show
    } finally {
      setFansLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (!userId) return
    async function init() {
      try {
        const setting = await getAutoReplySetting(userId!)
        setMode(setting.mode)
      } catch {
        // default to 'draft' on error
      }
      await fetchReplies()
      await fetchFans()
    }
    init()
  }, [userId, fetchReplies, fetchFans])

  // ── Toggle mode ───────────────────────────────────────────────────────────
  async function handleToggleMode() {
    if (!userId) return
    const newMode = mode === 'draft' ? 'auto' : 'draft'
    setModeLoading(true)
    try {
      await setAutoReplySetting(userId, newMode)
      setMode(newMode)
    } catch {
      setError('設定更新失敗，請重試。')
    } finally {
      setModeLoading(false)
    }
  }

  // ── Send reply ─────────────────────────────────────────────────────────────
  async function handleSend(replyId: string) {
    if (!userId) return
    setActionInProgress(replyId)
    try {
      await sendReply(replyId, userId)
      setReplies((prev) => prev.filter((r) => r.reply_id !== replyId))
    } catch {
      setError('發送失敗，請確認 Instagram 帳號已連結。')
    } finally {
      setActionInProgress(null)
    }
  }

  // ── Dismiss reply ──────────────────────────────────────────────────────────
  async function handleDismiss(replyId: string) {
    setActionInProgress(replyId)
    try {
      await dismissReply(replyId)
      setReplies((prev) => prev.filter((r) => r.reply_id !== replyId))
    } catch {
      setError('忽略操作失敗，請重試。')
    } finally {
      setActionInProgress(null)
    }
  }

  const filteredReplies = channelFilter === 'all'
    ? replies
    : replies.filter(r => r.channel === channelFilter)

  const pendingCount = replies.length
  const commentCount = replies.filter(r => r.channel === 'comment').length
  const dmCount = replies.filter(r => r.channel === 'dm').length

  return (
    <main className="min-h-screen bg-white text-black p-8 max-w-4xl mx-auto">
      {/* Header */}
      <h1 className="text-3xl font-bold mb-2">互動管理</h1>
      <p className="text-gray-500 mb-8">自動回覆系統 — 監測 IG 留言 · RAG 人設生成 · 草稿確認</p>

      {error && (
        <div className="mb-6 p-4 border border-red-300 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
          <button className="ml-4 underline" onClick={() => setError(null)}>關閉</button>
        </div>
      )}

      {/* ── 區塊 A：自動回覆開關 ──────────────────────────────────────────── */}
      <section className="mb-8 p-6 border border-gray-200 rounded-xl">
        <h2 className="text-lg font-semibold mb-1">回覆模式設定</h2>
        <p className="text-sm text-gray-500 mb-5">
          {mode === 'draft'
            ? '草稿模式：所有 AI 生成的回覆都需要人工確認後才發送。'
            : '自動模式：低風險留言將由 AI 自動回覆；高風險留言仍需人工確認。'}
        </p>

        <div className="flex items-center gap-4">
          {/* Toggle */}
          <button
            onClick={handleToggleMode}
            disabled={modeLoading}
            className={`relative inline-flex h-7 w-14 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 ${
              mode === 'auto' ? 'bg-black' : 'bg-gray-300'
            } ${modeLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            aria-label="切換回覆模式"
          >
            <span
              className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                mode === 'auto' ? 'translate-x-8' : 'translate-x-1'
              }`}
            />
          </button>
          <span className="text-sm font-medium">
            {mode === 'draft' ? '草稿模式（人工確認）' : '低風險自動發送'}
          </span>
          {modeLoading && <span className="text-xs text-gray-400">更新中…</span>}
        </div>
      </section>

      {/* ── 區塊 B：待確認回覆列表 ───────────────────────────────────────── */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            待確認回覆
            {pendingCount > 0 && (
              <span className="ml-2 px-2 py-0.5 text-xs bg-black text-white rounded-full">
                {pendingCount}
              </span>
            )}
          </h2>
          <button
            onClick={fetchReplies}
            disabled={repliesLoading}
            className="text-sm text-gray-500 hover:text-black underline disabled:opacity-50"
          >
            重新整理
          </button>
        </div>

        {/* Channel filter tabs */}
        <div className="flex gap-2 mb-4">
          {([
            { key: 'all', label: '全部', count: pendingCount },
            { key: 'comment', label: '留言', count: commentCount },
            { key: 'dm', label: '私訊', count: dmCount },
          ] as const).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setChannelFilter(key)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                channelFilter === key
                  ? 'bg-black text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {label}
              {count > 0 && (
                <span className={`ml-1.5 text-xs ${channelFilter === key ? 'text-gray-300' : 'text-gray-400'}`}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        {repliesLoading ? (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : filteredReplies.length === 0 ? (
          <div className="p-10 border border-dashed border-gray-300 rounded-xl text-center text-gray-400">
            <p className="text-2xl mb-2">✅</p>
            <p>目前沒有待確認的回覆</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredReplies.map((reply) => {
              const isProcessing = actionInProgress === reply.reply_id
              const isDm = reply.channel === 'dm'
              const expired = isDm && isDmExpired(reply.created_at)
              return (
                <div
                  key={reply.reply_id}
                  className="border border-gray-200 rounded-xl p-5 hover:border-gray-400 transition-colors"
                >
                  {/* Meta row */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">@{reply.commenter_name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        isDm ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {isDm ? '私訊' : '留言'}
                      </span>
                    </div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        reply.risk_level === 'high'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {reply.risk_level === 'high' ? '🔴 高風險' : '🟢 低風險'}
                    </span>
                  </div>

                  {/* 24h expired warning for DMs */}
                  {expired && (
                    <div className="mb-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
                      ⚠️ 此私訊已超過 24 小時，Meta 限制無法回覆
                    </div>
                  )}

                  {/* Original message */}
                  <div className="mb-3">
                    <p className="text-xs text-gray-400 mb-1">{isDm ? '原始私訊' : '原始留言'}</p>
                    <p className="text-sm bg-gray-50 rounded-lg p-3 leading-relaxed">
                      {reply.comment_text}
                    </p>
                  </div>

                  {/* AI draft */}
                  <div className="mb-4">
                    <p className="text-xs text-gray-400 mb-1">AI 草稿回覆</p>
                    <p className="text-sm bg-black text-white rounded-lg p-3 leading-relaxed">
                      {reply.draft_text}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-3">
                    <button
                      onClick={() => handleSend(reply.reply_id)}
                      disabled={isProcessing || expired}
                      className="flex-1 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isProcessing ? '處理中…' : expired ? '已過期' : '發送'}
                    </button>
                    <button
                      onClick={() => handleDismiss(reply.reply_id)}
                      disabled={isProcessing}
                      className="flex-1 py-2 border border-gray-300 text-sm font-medium rounded-lg hover:border-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isProcessing ? '處理中…' : '忽略'}
                    </button>
                  </div>

                  <p className="text-xs text-gray-300 mt-2">
                    {new Date(reply.created_at).toLocaleString('zh-TW')}
                  </p>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* ── 區塊 C：統計數字 ─────────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">今日數據</h2>
        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label="收到留言"
            value={MOCK_STATS.commentsToday}
            unit="則"
          />
          <StatCard
            label="已發送回覆"
            value={MOCK_STATS.sentReplies}
            unit="則"
          />
          <StatCard
            label="待確認"
            value={pendingCount}
            unit="則"
            highlight={pendingCount > 0}
          />
        </div>
        <p className="text-xs text-gray-400 mt-3">
          * 留言數與已發送數為 mock 資料；待確認數為即時資料
        </p>
      </section>

      {/* ── 區塊 D：粉絲記憶庫 ───────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold">粉絲互動記錄</h2>
            <p className="text-sm text-gray-500">AI 自動記錄每位粉絲的互動歷史，讓回覆更個人化</p>
          </div>
          <button
            onClick={fetchFans}
            disabled={fansLoading}
            className="text-sm text-gray-500 hover:text-black underline disabled:opacity-50"
          >
            重新整理
          </button>
        </div>

        {fansLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : fans.length === 0 ? (
          <div className="p-10 border border-dashed border-gray-300 rounded-xl text-center text-gray-400">
            <p className="text-2xl mb-2">👥</p>
            <p>尚無互動記錄，開始和粉絲互動後會在這裡顯示</p>
          </div>
        ) : (
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-4 gap-4 px-5 py-3 bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              <span>用戶名</span>
              <span className="text-center">互動次數</span>
              <span>最後互動時間</span>
              <span>備註摘要</span>
            </div>
            {/* Table rows */}
            {fans.map((fan, idx) => (
              <div
                key={fan.fan_id}
                className={`grid grid-cols-4 gap-4 px-5 py-4 text-sm items-start ${
                  idx !== fans.length - 1 ? 'border-b border-gray-100' : ''
                }`}
              >
                <span className="font-medium text-black">@{fan.username}</span>
                <span className="text-center">
                  <span className="inline-flex items-center justify-center w-8 h-8 bg-black text-white text-xs font-bold rounded-full">
                    {fan.interaction_count}
                  </span>
                </span>
                <span className="text-gray-500 text-xs leading-relaxed pt-1">
                  {new Date(fan.last_interaction).toLocaleString('zh-TW')}
                </span>
                <span className="text-gray-600 text-xs leading-relaxed line-clamp-2">
                  {fan.notes ? fan.notes.slice(-80) : '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}

// ---------------------------------------------------------------------------
// Sub-component: Stat Card
// ---------------------------------------------------------------------------
function StatCard({
  label,
  value,
  unit,
  highlight = false,
}: {
  label: string
  value: number
  unit: string
  highlight?: boolean
}) {
  return (
    <div
      className={`p-5 border rounded-xl text-center ${
        highlight ? 'border-black bg-black text-white' : 'border-gray-200'
      }`}
    >
      <p className={`text-3xl font-bold mb-1 ${highlight ? 'text-white' : 'text-black'}`}>
        {value}
      </p>
      <p className={`text-xs ${highlight ? 'text-gray-300' : 'text-gray-500'}`}>
        {label}（{unit}）
      </p>
    </div>
  )
}
