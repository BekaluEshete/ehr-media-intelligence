const BADGE = {
  DocumentReference: { label: 'Document',    cls: 'bg-blue-100 text-blue-700 ring-blue-200'   },
  DiagnosticReport:  { label: 'Diagnostic',  cls: 'bg-violet-100 text-violet-700 ring-violet-200' },
  Summary:           { label: 'AI Summary',  cls: 'bg-amber-100 text-amber-700 ring-amber-200' },
}

export default function ResourceBadge({ type, size = 'sm' }) {
  const { label, cls } = BADGE[type] || { label: type, cls: 'bg-slate-100 text-slate-600 ring-slate-200' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-medium ring-1
                      ${size === 'sm' ? 'text-xs' : 'text-sm px-2.5 py-1'}
                      ${cls}`}>
      {label}
    </span>
  )
}
