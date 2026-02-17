'use client'
import { useState } from 'react'

interface Persona {
  name: string
  occupation: string
  personality_tags: string[]
  speech_pattern: string
  values: string[]
  weekly_lifestyle: string
}

interface AppearanceFeatures {
  facial_features: string
  skin_tone: string
  hair: string
  style: string
  image_prompt: string
}

interface PersonaCardProps {
  persona: Persona
  appearance?: AppearanceFeatures
  onConfirm: (persona: Persona) => void
}

function EditableField({ label, value, onChange }: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  const [editing, setEditing] = useState(false)
  return (
    <div className="group">
      <label className="text-xs text-gray-400 uppercase tracking-wide">{label}</label>
      {editing ? (
        <input
          autoFocus
          value={value}
          onChange={e => onChange(e.target.value)}
          onBlur={() => setEditing(false)}
          className="block w-full border-b border-gray-300 py-1 focus:outline-none focus:border-black"
        />
      ) : (
        <p
          className="py-1 cursor-text hover:bg-gray-50 rounded px-1 -mx-1"
          onClick={() => setEditing(true)}
        >
          {value} <span className="text-gray-300 text-xs opacity-0 group-hover:opacity-100">✏️</span>
        </p>
      )}
    </div>
  )
}

export default function PersonaCard({ persona: initialPersona, appearance, onConfirm }: PersonaCardProps) {
  const [persona, setPersona] = useState(initialPersona)
  const [locked, setLocked] = useState(false)

  const update = (field: keyof Persona) => (value: string) => {
    setPersona(prev => ({ ...prev, [field]: value }))
  }

  const handleConfirm = () => {
    setLocked(true)
    onConfirm(persona)
  }

  return (
    <div className={`bg-white border-2 rounded-2xl p-6 space-y-4 transition-all ${locked ? 'border-green-400 bg-green-50' : 'border-gray-200'}`}>
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-lg">🪞 人設卡</h3>
        {locked && <span className="text-green-600 text-sm font-medium">✅ 已鎖定</span>}
        {!locked && <span className="text-xs text-gray-400">點擊欄位可直接編輯</span>}
      </div>

      <EditableField label="姓名" value={persona.name} onChange={update('name')} />
      <EditableField label="職業 / 身分" value={persona.occupation} onChange={update('occupation')} />

      <div>
        <label className="text-xs text-gray-400 uppercase tracking-wide">個性標籤</label>
        <div className="flex flex-wrap gap-2 mt-1">
          {persona.personality_tags.map((tag, i) => (
            <span key={i} className="bg-gray-100 rounded-full px-3 py-1 text-sm">{tag}</span>
          ))}
        </div>
      </div>

      <EditableField label="口癖 / 說話習慣" value={persona.speech_pattern} onChange={update('speech_pattern')} />
      <EditableField label="生活風格" value={persona.weekly_lifestyle} onChange={update('weekly_lifestyle')} />

      {appearance && (
        <div className="border-t pt-4">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">外觀分析（生圖 Prompt）</p>
          <p className="text-sm text-gray-600 bg-gray-50 rounded p-2">{appearance.image_prompt}</p>
        </div>
      )}

      {!locked && (
        <button
          onClick={handleConfirm}
          className="w-full bg-black text-white py-3 rounded-xl font-medium hover:bg-gray-800 transition-colors"
        >
          確認鎖定人設 🔒
        </button>
      )}
    </div>
  )
}
