'use client'

import { useEffect, useState } from 'react'

export default function DebugPage() {
  const [data, setData] = useState<any>({})

  useEffect(() => {
    const vpUserId = localStorage.getItem('vp_user_id')
    const vpUsername = localStorage.getItem('vp_ig_username')
    const vpPersonaId = localStorage.getItem('vp_persona_id')
    
    setData({
      vp_user_id: vpUserId,
      vp_ig_username: vpUsername,
      vp_persona_id: vpPersonaId,
    })

    // Test API call
    if (vpUserId) {
      fetch(`http://localhost:8000/api/instagram/status?persona_id=${vpUserId}`)
        .then(res => res.json())
        .then(status => {
          setData(prev => ({ ...prev, api_status: status }))
        })
        .catch(err => {
          setData(prev => ({ ...prev, api_error: err.message }))
        })
    }
  }, [])

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-bold mb-4">Debug Info</h1>
      <pre className="bg-gray-100 p-4 rounded-lg overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </main>
  )
}
