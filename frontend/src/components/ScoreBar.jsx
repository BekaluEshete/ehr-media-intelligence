export default function ScoreBar({ score }) {
  const pct  = Math.min(100, Math.round(score * 100))
  const colour = pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-400' : 'bg-slate-300'

  return (
    <div className="flex items-center gap-2" aria-label={`Relevance ${pct}%`}>
      <div className="flex-1 h-1 bg-slate-100 rounded-full overflow-hidden">
        <div className={`${colour} h-full rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-slate-400 w-8 text-right">{pct}%</span>
    </div>
  )
}
