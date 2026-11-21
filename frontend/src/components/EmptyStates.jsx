import { Search, Database, FileSearch } from 'lucide-react'

export function WelcomeState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center px-4">
      <div className="w-16 h-16 rounded-2xl bg-brand-50 border border-brand-100 flex items-center
                      justify-center mb-5">
        <Search className="w-8 h-8 text-brand-400" aria-hidden />
      </div>
      <h2 className="text-lg font-semibold text-slate-700 mb-2">Search patient records</h2>
      <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
        Use natural language — <em>"elevated HbA1c"</em>, <em>"chest pain 2024"</em>,
        or <em>"abnormal CBC"</em>. Click <strong>Load Sample Data</strong> first to ingest records.
      </p>
    </div>
  )
}

export function EmptyResults({ query, dataLoaded }) {
  if (!dataLoaded) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4">
        <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-100
                        flex items-center justify-center mb-4">
          <Database className="w-7 h-7 text-amber-400" aria-hidden />
        </div>
        <h2 className="text-base font-semibold text-slate-700 mb-1">No data loaded yet</h2>
        <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
          Click <strong className="text-slate-600">Load Sample Data</strong> in the
          header first, then search.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center px-4">
      <div className="w-14 h-14 rounded-2xl bg-red-50 border border-red-100
                      flex items-center justify-center mb-4">
        <FileSearch className="w-7 h-7 text-red-300" aria-hidden />
      </div>
      <h2 className="text-base font-semibold text-slate-700 mb-1">No records found</h2>
      <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
        No patient records matched <em>"{query}"</em>.
        Try clinical terms like <em>"chest pain"</em>, <em>"HbA1c diabetes"</em>,
        or <em>"discharge pneumonia"</em>.
      </p>
    </div>
  )
}

export function LoadingSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading results">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-white border border-slate-200 rounded-2xl p-5 animate-pulse">
          <div className="flex gap-4">
            <div className="w-7 h-7 rounded-full bg-slate-200" />
            <div className="flex-1 space-y-2">
              <div className="flex gap-2">
                <div className="h-5 w-24 bg-slate-200 rounded-full" />
                <div className="h-5 w-20 bg-slate-100 rounded-full" />
              </div>
              <div className="h-4 w-48 bg-slate-200 rounded" />
              <div className="h-3 w-full bg-slate-100 rounded" />
              <div className="h-3 w-3/4 bg-slate-100 rounded" />
              <div className="h-1 w-full bg-slate-100 rounded-full mt-3" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
