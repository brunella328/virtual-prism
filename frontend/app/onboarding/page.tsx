'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiPost } from '@/lib/api'

interface AppearanceResult {
  appearance: {
    facial_features: string
    skin_tone: string
    hair: string
    body: string
    style: string
    image_prompt: string
  }
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

export default function OnboardingPage() {
  const router = useRouter()
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<FileList | null>(null)
  const [previews, setPreviews] = useState<string[]>([])
  const [step, setStep] = useState<'input' | 'analyzing' | 'done'>('input')
  const [appearance, setAppearance] = useState<AppearanceResult | null>(null)
  const [persona, setPersona] = useState<PersonaResult | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (!selected) return
    setFiles(selected)
    const urls = Array.from(selected).map(f => URL.createObjectURL(f))
    setPreviews(urls)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStep('analyzing')

    try {
      // T2: 視覺反推
      if (files && files.length > 0) {
        const formData = new FormData()
        Array.from(files).forEach(f => formData.append('images', f))
        const appearanceRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/genesis/analyze-appearance`, {
          method: 'POST',
          body: formData,
        })
        const appearanceData = await appearanceRes.json()
        setAppearance(appearanceData)
      }

      // T3: 人設稜鏡
      const formData2 = new FormData()
      formData2.append('description', description)
      const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const personaRes = await fetch(`${API}/api/genesis/create-persona`, {
        method: 'POST',
        body: formData2,
      })
      if (!personaRes.ok) {
        const errText = await personaRes.text()
        throw new Error(`Persona API error: ${personaRes.status} - ${errText}`)
      }
      const personaResult = await personaRes.json()
      setPersona(personaResult)
      // 儲存到 localStorage 讓 dashboard 使用
      localStorage.setItem('vp_persona_id', personaResult.persona_id)
      localStorage.setItem('vp_persona', JSON.stringify(personaResult.persona))
      localStorage.setItem('vp_appearance_prompt', appearance?.appearance?.image_prompt || '')
      setStep('done')
    } catch (err) {
      console.error('Onboarding error:', err)
      alert(`發生錯誤：${err instanceof Error ? err.message : String(err)}`)
      setStep('input')
    }
  }

  if (step === 'analyzing') {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center">
        <div className="text-5xl mb-4 animate-pulse">🌈</div>
        <h2 className="text-xl font-semibold">Virtual Prism 稜鏡折射中...</h2>
        <p className="text-gray-500 mt-2">分析外觀特徵 + 生成人設，約需 10 秒</p>
      </main>
    )
  }

  if (step === 'done' && persona) {
    return (
      <main className="min-h-screen p-8 max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold mb-6">✨ 人設草稿生成完成</h2>
        <div className="bg-gray-50 rounded-xl p-6 space-y-4">
          <div><span className="font-medium">姓名：</span>{persona.persona.name}</div>
          <div><span className="font-medium">職業：</span>{persona.persona.occupation}</div>
          <div><span className="font-medium">個性標籤：</span>{persona.persona.personality_tags.join('、')}</div>
          <div><span className="font-medium">口癖：</span>{persona.persona.speech_pattern}</div>
          <div><span className="font-medium">生活風格：</span>{persona.persona.weekly_lifestyle}</div>
          {appearance && (
            <div className="border-t pt-4">
              <p className="font-medium mb-1">外觀分析</p>
              <p className="text-sm text-gray-600">{appearance.appearance.image_prompt}</p>
            </div>
          )}
        </div>
        <button
          onClick={() => router.push('/dashboard')}
          className="mt-6 w-full bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800"
        >
          確認人設，開始生成內容 →
        </button>
      </main>
    )
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">創建你的 AI 網紅</h1>
      <p className="text-gray-500 mb-8">上傳參考圖 + 一句話描述，30 秒生成完整人設</p>

      <form onSubmit={handleSubmit} className="w-full space-y-6">
        {/* 圖片上傳 */}
        <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center">
          <input type="file" accept="image/*" multiple id="file-upload"
            onChange={handleFileChange} className="hidden" />
          <label htmlFor="file-upload" className="cursor-pointer block">
            {previews.length > 0 ? (
              <div className="flex gap-2 justify-center flex-wrap">
                {previews.map((src, i) => (
                  <img key={i} src={src} alt="" className="h-24 w-24 object-cover rounded-lg" />
                ))}
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

        {/* 描述輸入 */}
        <div>
          <label className="block text-sm font-medium mb-2">一句話描述這個人設</label>
          <input type="text" value={description} onChange={e => setDescription(e.target.value)}
            placeholder="例：一個熱愛衝浪、充滿陽光能量的男孩"
            className="w-full border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-black"
            required />
        </div>

        <button type="submit" disabled={!description}
          className="w-full bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50">
          開始生成人設 →
        </button>
      </form>
    </main>
  )
}
