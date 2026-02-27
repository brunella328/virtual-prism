'use client'
import { Toast, ToastType } from '@/hooks/useToast'

const STYLES: Record<ToastType, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-700',
  info: 'bg-blue-50 border-blue-200 text-blue-700',
}

const ICONS: Record<ToastType, string> = {
  success: '✓',
  error: '✗',
  info: 'ℹ',
}

interface ToastContainerProps {
  toasts: Toast[]
  onDismiss: (id: string) => void
}

export default function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 px-4 py-3 border rounded-xl shadow-md text-sm animate-in slide-in-from-right ${STYLES[toast.type]}`}
        >
          <span className="font-bold mt-0.5">{ICONS[toast.type]}</span>
          <p className="flex-1">{toast.message}</p>
          <button onClick={() => onDismiss(toast.id)} className="opacity-50 hover:opacity-100 ml-1">✕</button>
        </div>
      ))}
    </div>
  )
}
