'use client'
import { useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ModelResult {
  model_name: string
  image_url: string
  generation_time: number
  cost_estimate: number
  error?: string
}

const PRESET_PROMPTS = {
  portrait: "A young Asian woman in her mid-20s, caught off-guard mid-conversation at a Taipei coffee shop, wearing a slightly wrinkled white t-shirt, oily forehead from humidity, messy hair with flyaways, positioned off-center in lower left third of frame, harsh overhead fluorescent lighting casting unflattering shadows under eyes and nose, side lighting from window leaving half her face darker, diagonal composition, accidental snapshot",
  outdoor: "A young Asian woman walking through a Taipei night market, wearing a casual jacket, caught mid-bite eating street food, slight motion blur from movement, positioned in right third of frame with messy background, backlit by neon signs creating lens flare, strong shadows from top lighting, natural tired expression, visible skin texture and forehead shine, triangular composition with food stalls, chromatic aberration at edges",
  extreme: "A candid photo of a young Asian woman caught off-guard while eating noodles, mid-chew, messy hair, oily skin forehead, sitting in a dimly lit Taipei night market stall, harsh fluorescent light from above casting long shadows",
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
        headers: { 'Content-Type': 'application/json' },
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
            🔬 Flux Realism POC (2026光學缺陷優化版)
          </h1>
          <p className="text-gray-600 mb-1">
            flux-dev-realism + 光學物理瑕疵（色散/動態模糊/鏡頭炫光/非對稱光影）
          </p>
          <p className="text-sm text-gray-500">
            CFG 2.8 | 從「描述臉」→「描述鏡頭」| 破除塑膠感
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              測試場景（2026光學缺陷優化版）
            </label>
            <div className="flex gap-3 mb-4 flex-wrap">
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.portrait)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.portrait
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                👤 咖啡廳（側光+頂光）
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.outdoor)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.outdoor
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🌃 夜市（逆光+動態模糊）
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.extreme)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.extreme
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🍜 極限測試（吃麵中）
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
              正在生成圖片（光學缺陷優化中）...
              <br />
              <span className="text-sm text-gray-500">
                (flux-dev-realism | CFG 2.8 | 預計 30-40 秒)
              </span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
