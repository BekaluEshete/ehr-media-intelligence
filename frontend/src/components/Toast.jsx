import { useEffect } from 'react'
import { CheckCircle, XCircle, Info, X } from 'lucide-react'

const ICONS = {
  success: <CheckCircle className="w-5 h-5 text-emerald-500" />,
  error:   <XCircle    className="w-5 h-5 text-red-500"     />,
  info:    <Info       className="w-5 h-5 text-brand-500"   />,
}

const BG = {
  success: 'bg-white border-emerald-200',
  error:   'bg-white border-red-200',
  info:    'bg-white border-brand-200',
}

export default function Toast({ toast, onDismiss }) {
  useEffect(() => {
    if (!toast || toast.type === 'error') return
    const t = setTimeout(onDismiss, 5000)
    return () => clearTimeout(t)
  }, [toast, onDismiss])

  if (!toast) return null

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`fixed bottom-5 left-1/2 -translate-x-1/2 z-50 flex items-start gap-3
                  min-w-72 max-w-md border rounded-xl shadow-lg px-4 py-3 animate-fade-in
                  ${BG[toast.type] || BG.info}`}
    >
      {ICONS[toast.type] || ICONS.info}
      <p className="flex-1 text-sm text-slate-700 leading-snug">{toast.message}</p>
      <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600 mt-0.5"
        aria-label="Dismiss notification">
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}
