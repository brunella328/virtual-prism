'use client'
import { useState } from 'react'
import { apiHeaders } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ModelResult {
  model_name: string
  image_url: string
  generation_time: number
  cost_estimate: number
  error?: string
}

const PRESET_PROMPTS = {
  gym: "A raw grainy mobile phone photo of a young Asian woman lying on a gym mat, exhausted after workout, drenched in sweat with glistening skin, visible beads of perspiration on forehead and collarbone, flushed red cheeks, mouth slightly open panting for air, clumped wet hair matted and sticking to sweaty forehead and neck, shot from high-angle selfie perspective with iPhone front camera, wide-angle lens distortion with face center slightly bulging, harsh overhead gym fluorescent lighting creating blown-out highlights on sweaty skin, low dynamic range, high ISO noise, messy gym equipment in background, water bottles visible, cluttered environment, unstaged accidental selfie",
  portrait: "A young Asian woman at messy Taipei coffee shop, caught mid-sentence with mouth slightly open, glistening forehead with light perspiration, cheap oxidized silver necklace, small mole on cheek, wrinkled t-shirt with coffee stain, messy hair strands stuck to face, eyes looking at menu off-camera, shot on iPhone with wide-angle distortion, harsh overhead fluorescent creating uneven lighting, half face in shadow, cluttered cafe background visible, cups and bags on table, social media compression artifacts",
  extreme: "A low-quality grainy iPhone selfie of young Asian woman eating noodles, mid-chew with mouth open, sauce stain on shirt, sweaty forehead glistening, matted hair stuck to face from humidity, small mole visible, eyes looking down at bowl, wide-angle front camera distortion, harsh fluorescent overhead creating blown-out highlights, crushed blacks in shadows, messy night market stall background with equipment and bottles visible, not overly blurred, bad lighting, unstaged candid moment",
}

export default function ModelComparisonPage() {
  const [prompt, setPrompt] = useState(PRESET_PROMPTS.portrait)
  const [seed, setSeed] = useState(42)
  const [results, setResults] = useState<ModelResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const runComparison = async () => {
    setLoading(true)
    setError('')
    setResults([])

    try {
      const res = await fetch(`${API}/api/poc/model-comparison`, {
        method: 'POST',
        credentials: 'include',
        headers: apiHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ prompt, seed }),
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail || 'API request failed')
      }

      const data = await res.json()
      setResults(data)
    } catch (err: any) {
      setError(err.message || 'Failed to generate comparison')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🔬 Flux Realism POC (V7 LDR物理缺陷版)
          </h1>
          <p className="text-gray-600 mb-1">
            flux-dev-realism V7：低動態範圍 (LDR) + 物理缺陷三大面向
          </p>
          <p className="text-sm text-gray-500">
            ✨ 新增：JPEG壓縮痕跡 | 死白高光+死黑陰影 | 閃光燈藍調/室內黃綠偏色
            <br />
            CFG 2.5 | Steps 28 | 從「完美AI圖」→「真實手機照片」
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              測試場景（V7 LDR物理缺陷版）
            </label>
            <div className="flex gap-3 mb-4 flex-wrap">
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.gym)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.gym
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                💪 健身房（閃光燈模式）⭐
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.portrait)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.portrait
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                ☕ 咖啡廳（平淡日常模式）
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.extreme)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.extreme
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🍜 極限測試（LDR+壓縮）
              </button>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              rows={4}
              placeholder="Enter your prompt..."
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Seed (隨機種子)
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
              className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <button
            onClick={runComparison}
            disabled={loading || !prompt}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 text-white py-4 rounded-xl font-semibold text-lg hover:shadow-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '🔄 生成中... (需要 1-3 分鐘)' : '▶️ 開始對比測試'}
          </button>

          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              ❌ {error}
            </div>
          )}
        </div>

        {/* Results */}
        {results.length > 0 && (
          <div className="max-w-3xl mx-auto">
            {results.map((result, idx) => (
              <div
                key={idx}
                className="bg-white rounded-2xl shadow-lg overflow-hidden"
              >
                <div className="p-4 bg-gradient-to-r from-purple-100 to-blue-100">
                  <h3 className="font-bold text-lg text-gray-900">
                    {result.model_name}
                  </h3>
                  <div className="flex justify-between text-sm text-gray-600 mt-2">
                    <span>⏱️ {result.generation_time.toFixed(1)}s</span>
                    <span>💰 ${result.cost_estimate.toFixed(3)}</span>
                  </div>
                </div>

                <div className="p-4">
                  {result.error ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                      ❌ {result.error}
                    </div>
                  ) : result.image_url ? (
                    <img
                      src={result.image_url}
                      alt={result.model_name}
                      className="w-full rounded-lg shadow-md"
                    />
                  ) : (
                    <div className="aspect-[4/5] bg-gray-100 rounded-lg flex items-center justify-center text-gray-400">
                      No image generated
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-purple-600 border-t-transparent"></div>
            <p className="mt-4 text-gray-600">
              正在生成圖片（LDR 物理缺陷注入中）...
              <br />
              <span className="text-sm text-gray-500">
                (flux-dev-realism V7 | LDR | 壓縮痕跡+死白死黑+色偏 | 預計 30-40 秒)
              </span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
