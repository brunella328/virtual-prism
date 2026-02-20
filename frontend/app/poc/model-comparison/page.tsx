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
  portrait: "A young Asian woman in her mid-20s, caught mid-sentence with mouth slightly open, at a messy Taipei coffee shop, wearing a wrinkled white t-shirt with small coffee stain near collar, cheap oxidized silver necklace, simple ring on finger, small mole on cheek, oily forehead with uneven skin pigmentation, messy hair with stray strands stuck to face, eyes looking at menu off-camera with natural gaze, positioned awkwardly off-center, mixed lighting from flickering fluorescent overhead creating ugly yellow color cast and deep messy shadows",
  outdoor: "A young Asian woman walking through a Taipei night market, caught mid-bite with mouth open, wearing casual jacket with fabric creases, cheap accessories visible, small mole on face, slight motion blur from shaky handheld camera, eyes looking at food stall off-camera, positioned in right third of frame, messy background slightly out of focus, mixed lighting from neon signs creating harsh color cast, stray hair covering parts of face, visible skin blemishes and forehead shine, lens smudge creating soft haze",
  extreme: "A low-quality grainy photo of a young Asian woman caught off-guard while eating noodles, mid-chew with mouth open, wrinkled t-shirt with sauce stain, oxidized necklace, small mole visible, messy hair stuck to face, oily forehead, eyes looking down at noodles naturally, sitting in dimly lit Taipei night market stall, harsh flickering fluorescent creating ugly yellow-green cast, shaky handheld motion blur, slightly out of focus, lens smudge, purple fringing, awkwardly cropped",
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
            🔬 Flux Realism POC (V5不完美光線版)
          </h1>
          <p className="text-gray-600 mb-1">
            flux-dev-realism + 不完美光線（強陰影+暗部+背景可辨識）
          </p>
          <p className="text-sm text-gray-500">
            CFG 2.5 | Steps 28 | 強陰影+crushed blacks+背景f/2.8淺景深（不過度虛化）
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-8">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              測試場景（V5不完美光線版）
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
                👤 咖啡廳（半臉陰影+暗部）
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.outdoor)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.outdoor
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🌃 夜市（強陰影+背景可見）
              </button>
              <button
                onClick={() => setPrompt(PRESET_PROMPTS.extreme)}
                className={`px-4 py-2 rounded-lg font-medium ${
                  prompt === PRESET_PROMPTS.extreme
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🍜 極限測試（暗部丟失細節）
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
              正在生成圖片（不完美光線優化中）...
              <br />
              <span className="text-sm text-gray-500">
                (flux-dev-realism | CFG 2.5 | Steps 28 | 強陰影+暗部+背景可見 | 預計 30-40 秒)
              </span>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
