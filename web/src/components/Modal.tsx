import { X } from 'lucide-react'
import type { ReactNode } from 'react'

export default function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" onMouseDown={onClose}>
    <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-800" onMouseDown={(event) => event.stopPropagation()}>
      <div className="mb-5 flex items-center justify-between"><h2 className="text-xl font-semibold text-gray-900 dark:text-white">{title}</h2><button onClick={onClose} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100"><X className="h-5 w-5" /></button></div>
      {children}
    </div>
  </div>
}

export function ErrorBanner({ error }: { error: any }) {
  if (!error) return null
  return <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error.response?.data?.detail || error.message || 'Request failed'}</div>
}

export const inputClass = 'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-gray-600 dark:bg-gray-900 dark:text-white'
