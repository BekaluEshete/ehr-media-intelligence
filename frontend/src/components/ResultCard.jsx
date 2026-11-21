import { ChevronRight, Calendar, User } from 'lucide-react'
import ResourceBadge from './ResourceBadge'
import ScoreBar from './ScoreBar'

function formatDate(d) {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch { return d }
}

export default function ResultCard({ result, onClick, index }) {
  return (
    <article
      role="button"
      tabIndex={0}
      aria-label={`View record for ${result.patient_name}, MRN ${result.mrn}`}
      onClick={() => onClick(result.mrn)}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onClick(result.mrn)}
      className="group bg-white border border-slate-200 rounded-2xl p-5 cursor-pointer
                 hover:border-brand-400 hover:shadow-md transition-all duration-150
                 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2
                 animate-fade-in"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className="flex items-start gap-4">

        {/* Rank number */}
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-slate-100 group-hover:bg-brand-100
                        flex items-center justify-center transition-colors">
          <span className="text-xs font-semibold text-slate-500 group-hover:text-brand-700">
            {index + 1}
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Top row: badge + date */}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <ResourceBadge type={result.resource_type} />
            {result.date && (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Calendar className="w-3 h-3" aria-hidden />
                {formatDate(result.date)}
              </span>
            )}
          </div>

          {/* Patient name + MRN */}
          <div className="flex items-center gap-1.5 mb-1">
            <User className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" aria-hidden />
            <h3 className="text-sm font-semibold text-slate-800 group-hover:text-brand-700 truncate
                           transition-colors">
              {result.patient_name}
            </h3>
            <span className="text-xs text-slate-400 font-mono flex-shrink-0">· {result.mrn}</span>
          </div>

          {/* Title */}
          <p className="text-xs font-medium text-slate-500 mb-2">{result.title}</p>

          {/* Snippet */}
          <p className="text-sm text-slate-600 line-clamp-2 leading-relaxed">
            {result.summary_snippet}
          </p>

          {/* Score bar */}
          <div className="mt-3">
            <ScoreBar score={result.score} />
          </div>
        </div>

        {/* Arrow */}
        <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-brand-500 flex-shrink-0
                                  mt-1 transition-colors" aria-hidden />
      </div>
    </article>
  )
}
