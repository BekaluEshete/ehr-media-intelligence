import { Activity } from 'lucide-react'

export default function Header({ onLoadData, loading }) {
  return (
    <header className="bg-brand-950 border-b border-brand-800 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">

        {/* Logo + title */}
        <div className="flex items-center gap-3">
          <div className="bg-brand-600 p-1.5 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-white font-semibold text-sm leading-tight">
              EHR Media Intelligence
            </h1>
            <p className="text-brand-300 text-xs">AI-Powered Clinical Search</p>
          </div>
        </div>

        {/* Load sample data */}
        <button
          onClick={onLoadData}
          disabled={loading}
          className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-60
                     disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-lg
                     transition-colors focus:outline-none focus:ring-2 focus:ring-brand-400 focus:ring-offset-2
                     focus:ring-offset-brand-950"
          aria-label="Load sample patient data"
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Loading…
            </>
          ) : (
            'Load Sample Data'
          )}
        </button>
      </div>
    </header>
  )
}
