/** @type {import('next').NextConfig} */

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Build a single-line CSP string (newlines confuse some browsers/proxies)
const csp = [
  "default-src 'self'",
  // Next.js App Router requires unsafe-inline for hydration scripts
  "script-src 'self' 'unsafe-inline'",
  // Tailwind utility classes and Next.js inject inline styles
  "style-src 'self' 'unsafe-inline'",
  // self  — Next.js self-hosts Google Fonts at /_next/static/
  // data: — URL.createObjectURL previews in onboarding/dashboard
  // blob: — Web Share API image blobs
  // Cloudinary — reference face uploads (cloudinary_service.py)
  // replicate.delivery — AI-generated image CDN
  `img-src 'self' data: blob: https://res.cloudinary.com https://*.replicate.delivery`,
  // Fonts are self-hosted by next/font/google at build time
  "font-src 'self'",
  // Fetch calls go only to our own backend
  `connect-src 'self' ${apiUrl}`,
  // Prevent this app from being embedded in iframes
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ')

const securityHeaders = [
  { key: 'Content-Security-Policy',   value: csp },
  { key: 'X-Frame-Options',           value: 'DENY' },
  { key: 'X-Content-Type-Options',    value: 'nosniff' },
  { key: 'Referrer-Policy',           value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy',        value: 'camera=(), microphone=(), geolocation=()' },
]

const nextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: securityHeaders,
      },
    ]
  },
}

module.exports = nextConfig
