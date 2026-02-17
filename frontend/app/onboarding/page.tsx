'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function OnboardingPage() {
  const router = useRouter()
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<FileList | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    // T2: 視覺反推 + T3: 人設稜鏡 (to be implemented)
    router.push('/dashboard')
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">創建你的 AI 網紅</h1>
      <p className="text-gray-500 mb-8">上傳參考圖 + 一句話描述，30 秒生成完整人設</p>

      <form onSubmit={handleSubmit} className="w-full space-y-6">
        {/* 圖片上傳區 */}
        <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center">
          <input
            type="file"
            accept="image/*"
            multiple
            max={3}
            onChange={e => setFiles(e.target.files)}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <div className="text-4xl mb-2">📸</div>
            <p className="font-medium">上傳 1-3 張參考圖</p>
            <p className="text-sm text-gray-400">支援 JPG / PNG</p>
            {files && <p className="mt-2 text-green-600">已選擇 {files.length} 張圖片</p>}
          </label>
        </div>

        {/* 一句話描述 */}
        <div>
          <label className="block text-sm font-medium mb-2">一句話描述這個人設</label>
          <input
            type="text"
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="例：一個熱愛衝浪、充滿陽光能量的男孩"
            className="w-full border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-black"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading || !description}
          className="w-full bg-black text-white py-3 rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50"
        >
          {loading ? '生成中...' : '開始生成人設 →'}
        </button>
      </form>
    </main>
  )
}
