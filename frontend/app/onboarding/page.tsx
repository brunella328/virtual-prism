'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUser } from '@/contexts/UserContext'
import { connectWithToken } from '@/lib/api'
import { storage } from '@/lib/storage'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface AppearanceData {
  facial_features: string
  skin_tone: string
  hair: string
  body: string
  style: string
  image_prompt: string
}

interface PersonaResult {
  persona_id: string
  persona: {
    name: string
    occupation: string
    personality_tags: string[]
    speech_pattern: string
    values: string[]
    weekly_lifestyle: string
  }
}

type Step = 'connect' | 'input' | 'analyzing' | 'done'

export default function OnboardingPage() {
  const router = useRouter()
  const { userId, connect, setAppearancePrompt } = useUser()

  const [step, setStep] = useState<Step>('connect')

  // Step 1 — IG Token
  const [tokenInput, setTokenInput] = useState('')
  const [tokenLoading, setTokenLoading] = useState(false)
  const [tokenError, setTokenError] = useState('')

  // Step 2 — 人設輸入
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<FileList | null>(null)
  const [previews, setPreviews] = useState<string[]>([])

  // Step 3/4 — 結果
  const [appearanceData, setAppearanceData] = useState<AppearanceData | null>(null)
  const [persona, setPersona] = useState<PersonaResult | null>(null)
  const [editedPersona, setEditedPersona] = useState<PersonaResult['persona'] | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  // 頁面載入：依 context 決定起始 step
  useEffect(() => {
    if (!userId) { setStep('connect'); return }

    // 已連結 IG，嘗試從後端讀取既有人設
    fetch(`${API}/api/genesis/persona/${userId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setPersona({ persona_id: data.persona_id, persona: data.persona })
          setEditedPersona(data.persona)
          if (data.persona.appearance) {
            setAppearanceData(data.persona.appearance)
          }
          setStep('done')
        } else {
          setStep('input')
        }
      })
      .catch(() => setStep('input'))
  }, [userId])

  // ── Step 1：連結 IG ──────────────────────────────────────────────────────
  const handleConnectToken = async () => {
    if (!tokenInput.trim()) { setTokenError('請輸入 Access Token'); return }
    setTokenLoading(true)
    setTokenError('')
    try {
      const result = await connectWithToken('temp', tokenInput.trim())
      // connect() 同時更新 React context 與 localStorage
      connect(result.ig_account_id, result.ig_username)
      setTokenInput('')
      setStep('input')
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : '連結失敗，請確認 Token 是否有效')
    } finally {
      setTokenLoading(false)
    }
  }

  if (step === 'connect') return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 max-w-md mx-auto">
      <h1 className="text-3xl font-bold mb-2">Virtual Prism 🌈</h1>
      <p className="text-gray-500 mb-8 text-center">連結你的 Instagram 帳號，開始創建 AI 網紅</p>

      {/* OAuth 登入按鈕 */}
      <div className="w-full p-6 border-2 border-black rounded-2xl bg-white space-y-3">
        <h2 className="text-lg font-semibold">連結 Instagram 帳號</h2>
        <p className="text-sm text-gray-500">點擊下方按鈕，透過 Instagram 官方授權流程登入</p>
        <button
          onClick={async () => {
            try {
              const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/instagram/auth?persona_id=temp`)
              const data = await res.json()
              if (data.auth_url) window.location.href = data.auth_url
              else alert('無法取得授權連結，請確認後端設定')
            } catch {
              alert('連線失敗，請確認後端是否運行中')
            }
          }}
          className="w-full py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:opacity-90 font-medium flex items-center justify-center gap-2"
        >
          <span>📷</span> 用 Instagram 帳號登入
        </button>
      </div>

      {/* Token 手動輸入（進階） */}
      <details className="w-full mt-3">
        <summary className="text-xs text-gray-400 cursor-pointer text-center select-none">
          進階：手動輸入 Access Token
        </summary>
        <div className="w-full p-4 border border-gray-200 rounded-2xl bg-white space-y-3 mt-2">
          <textarea
            value={tokenInput}
            onChange={e => setTokenInput(e.target.value)}
            placeholder="貼上 Access Token (IGAA... 或 EAA...)"
            className="w-full border border-gray-300 rounded-lg px-3 py-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-black"
            rows={4}
          />
          {tokenError && <p className="text-red-500 text-sm">{tokenError}</p>}
          <button
            onClick={handleConnectToken}
            disabled={tokenLoading || !tokenInput.trim()}
            className="w-full py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 font-medium text-sm"
          >
            {tokenLoading ? '驗證中...' : '以 Token 連結'}
          </button>
          <p className="text-xs text-gray-400 text-center">
            💡 請使用長效 Access Token（60 天有效期），系統會自動刷新
          </p>
        </div>
      </details>
    </main>
  )

  // ── Step 2：輸入人設 ────────────────────────────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (!selected) return
    setFiles(selected)
    setPreviews(Array.from(selected).map(f => URL.createObjectURL(f)))
  }

  const runAnalysis = async () => {
    setStep('analyzing')
    try {
      let localAppearance: AppearanceData | null = null
      if (files && files.length > 0) {
        const formData = new FormData()
        Array.from(files).forEach(f => formData.append('images', f))
        const res = await fetch(`${API}/api/genesis/analyze-appearance`, { method: 'POST', body: formData })
        const result = await res.json()
        localAppearance = result.appearance
        setAppearanceData(localAppearance)
      }

      const formData2 = new FormData()
      formData2.append('description', description)
      if (userId) formData2.append('persona_id', userId)
      if (files && files.length > 0) formData2.append('reference_image', files[0])

      const personaRes = await fetch(`${API}/api/genesis/create-persona`, { method: 'POST', body: formData2 })
      if (!personaRes.ok) throw new Error(`Persona API error: ${personaRes.status}`)
      const personaResult: PersonaResult = await personaRes.json()
      setPersona(personaResult)
      setEditedPersona(personaResult.persona)

      // 透過 context 同步 appearance prompt（storage 同步已在 context 內完成）
      if (localAppearance?.image_prompt) {
        setAppearancePrompt(localAppearance.image_prompt)
      }

      setStep('done')
    } catch (err) {
      console.error('Onboarding error:', err)
      alert(`發生錯誤：${err instanceof Error ? err.message : String(err)}`)
      setStep('input')
    }
  }

  if (step === 'analyzing') return (
    <main className="min-h-screen flex flex-col items-center justify-center">
      <div className="text-5xl mb-4 animate-pulse">🌈</div>
      <h2 className="text-xl font-semibold">Virtual Prism 稜鏡折射中...</h2>
      <p className="text-gray-500 mt-2">分析外觀特徵 + 生成人設，約需 10 秒</p>
    </main>
  )

  // ── Step 4：人設卡（可編輯）──────────────────────────────────────────────
  if (step === 'done' && persona && editedPersona) {
    const handleSavePersona = async () => {
      if (!userId) return
      setIsSaving(true)
      try {
        const res = await fetch(`${API}/api/genesis/persona/${userId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editedPersona),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setPersona({ persona_id: data.persona_id, persona: data.persona })
        alert('人設已儲存 ✓')
      } catch (e) {
        alert(`儲存失敗：${e instanceof Error ? e.message : String(e)}`)
      } finally {
        setIsSaving(false)
      }
    }

    return (
      <main className="min-h-screen p-8 max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold mb-2">✨ 人設草稿生成完成</h2>
        <p className="text-sm text-gray-400 mb-6">描述：「{description}」</p>

        {previews.length > 0 && (
          <div className="flex gap-2 mb-5">
            {previews.map((src, i) => (
              <img key={i} src={src} alt="" className="h-20 w-20 object-cover rounded-xl border" />
            ))}
          </div>
        )}

        <div className="bg-gray-50 rounded-xl p-6 space-y-3 mb-4">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">人設資訊（可直接編輯）</h3>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">姓名</span>
            <input
              value={editedPersona.name}
              onChange={e => setEditedPersona({ ...editedPersona, name: e.target.value })}
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">職業</span>
            <input
              value={editedPersona.occupation}
              onChange={e => setEditedPersona({ ...editedPersona, occupation: e.target.value })}
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">個性標籤</span>
            <input
              value={editedPersona.personality_tags.join(', ')}
              onChange={e => setEditedPersona({
                ...editedPersona,
                personality_tags: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
              })}
              placeholder="以逗號分隔，例：活潑, 熱情"
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">口癖</span>
            <input
              value={editedPersona.speech_pattern}
              onChange={e => setEditedPersona({ ...editedPersona, speech_pattern: e.target.value })}
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">核心價值</span>
            <input
              value={editedPersona.values?.join(', ') || ''}
              onChange={e => setEditedPersona({
                ...editedPersona,
                values: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
              })}
              placeholder="以逗號分隔，例：真誠, 自由"
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm w-20 shrink-0">生活風格</span>
            <input
              value={editedPersona.weekly_lifestyle}
              onChange={e => setEditedPersona({ ...editedPersona, weekly_lifestyle: e.target.value })}
              className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 bg-white"
            />
          </div>
          <button
            onClick={handleSavePersona}
            disabled={isSaving}
            className="w-full border border-gray-400 py-2 rounded-lg text-sm font-medium hover:bg-gray-100 disabled:opacity-50 mt-2"
          >
            {isSaving ? '儲存中...' : '儲存修改'}
          </button>
        </div>

        {appearanceData && (
          <div className="bg-blue-50 rounded-xl p-6 space-y-2 mb-4">
            <h3 className="text-xs font-semibold text-blue-400 uppercase tracking-wide mb-3">外觀分析</h3>
            <div className="grid grid-cols-1 gap-2 text-sm">
              <div><span className="font-medium text-blue-700">臉部特徵：</span><span className="text-gray-700">{appearanceData.facial_features}</span></div>
              <div><span className="font-medium text-blue-700">膚色：</span><span className="text-gray-700">{appearanceData.skin_tone}</span></div>
              <div><span className="font-medium text-blue-700">髮型髮色：</span><span className="text-gray-700">{appearanceData.hair}</span></div>
              <div><span className="font-medium text-blue-700">體型：</span><span className="text-gray-700">{appearanceData.body}</span></div>
              <div><span className="font-medium text-blue-700">穿搭風格：</span><span className="text-gray-700">{appearanceData.style}</span></div>
            </div>
            <div className="mt-3 pt-3 border-t border-blue-100">
              <p className="text-xs font-medium text-blue-600 mb-1">生圖 Prompt</p>
              <p className="text-xs text-gray-500 leading-relaxed">{appearanceData.image_prompt}</p>
            </div>
          </div>
        )}

        <div className="flex gap-3 mt-2">
          <button
            onClick={() => { setStep('input') }}
            className="flex-1 border border-gray-300 py-3 rounded-lg font-medium hover:bg-gray-50 text-sm"
          >
            🔄 重新生成人設
          </button>
          <button
            onClick={() => {
              storage.clearSchedule()
              router.push('/dashboard')
            }}
            className="flex-2 flex-grow-[2] bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800 text-sm"
          >
            確認人設，開始生成內容 →
          </button>
        </div>
        <button
          onClick={() => setStep('input')}
          className="mt-3 w-full text-sm text-gray-400 hover:text-black text-center transition-colors"
        >
          ← 修改描述或重新上傳圖片
        </button>
      </main>
    )
  }

  // ── Step 2 render：輸入表單 ──────────────────────────────────────────────
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">創建你的 AI 網紅</h1>
      <p className="text-gray-500 mb-8">上傳參考圖 + 一句話描述，30 秒生成完整人設</p>

      <form onSubmit={e => { e.preventDefault(); runAnalysis() }} className="w-full space-y-6">
        <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center">
          <input type="file" accept="image/*" multiple id="file-upload" onChange={handleFileChange} className="hidden" />
          <label htmlFor="file-upload" className="cursor-pointer block">
            {previews.length > 0 ? (
              <div className="flex gap-2 justify-center flex-wrap">
                {previews.map((src, i) => <img key={i} src={src} alt="" className="h-24 w-24 object-cover rounded-lg" />)}
              </div>
            ) : (
              <>
                <div className="text-4xl mb-2">📸</div>
                <p className="font-medium">上傳 1-3 張參考圖</p>
                <p className="text-sm text-gray-400">支援 JPG / PNG（可選）</p>
              </>
            )}
          </label>
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">一句話描述這個人設</label>
          <input
            type="text" value={description} onChange={e => setDescription(e.target.value)}
            placeholder="例：一個熱愛衝浪、充滿陽光能量的男孩"
            className="w-full border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-black"
            required
          />
        </div>

        <button type="submit" disabled={!description}
          className="w-full bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50">
          開始生成人設 →
        </button>
      </form>
    </main>
  )
}
