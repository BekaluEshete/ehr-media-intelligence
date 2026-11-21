import { useEffect, useRef } from 'react'
import { X, User, Calendar, AlertTriangle, FileText, Stethoscope, FlaskConical, Cpu } from 'lucide-react'
import ResourceBadge from './ResourceBadge'

function formatDate(d) {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) }
  catch { return d }
}

function Section({ icon: Icon, title, colour = 'brand', children }) {
  const colours = {
    brand:  'bg-brand-50  border-brand-100  text-brand-800',
    amber:  'bg-amber-50  border-amber-100  text-amber-800',
    red:    'bg-red-50    border-red-100    text-red-800',
    slate:  'bg-slate-50  border-slate-100  text-slate-700',
  }
  return (
    <div className={`rounded-xl border p-4 ${colours[colour]}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 opacity-70" aria-hidden />
        <h3 className="text-xs font-semibold uppercase tracking-wide opacity-70">{title}</h3>
      </div>
      {children}
    </div>
  )
}

function PatientHeader({ bundle }) {
  const patRes = bundle?.entry?.find(e => e.resource?.resourceType === 'Patient')?.resource
  if (!patRes) return null
  const name = patRes.name?.[0]
  const full = `${(name?.given || []).join(' ')} ${name?.family || ''}`.trim()
  return (
    <Section icon={User} title="Patient Demographics" colour="brand">
      <p className="text-lg font-bold text-brand-900">{full}</p>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span className="text-brand-600 font-medium">MRN</span>
        <span className="font-mono text-brand-800">{patRes.identifier?.[0]?.value || '—'}</span>
        <span className="text-brand-600 font-medium">Date of Birth</span>
        <span>{formatDate(patRes.birthDate)}</span>
        <span className="text-brand-600 font-medium">Gender</span>
        <span className="capitalize">{patRes.gender || '—'}</span>
      </div>
    </Section>
  )
}

function AISummary({ summary }) {
  if (!summary) return null
  return (
    <Section icon={Cpu} title="AI Clinical Summary" colour="amber">
      {summary.error ? (
        <p className="text-sm text-red-600">{summary.error}</p>
      ) : (
        <div className="space-y-3">
          <div>
            <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Chief Concern</p>
            <p className="text-sm text-slate-800 leading-relaxed">{summary.chief_concern || '—'}</p>
          </div>

          {summary.key_diagnoses?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">Key Diagnoses</p>
              <ul className="space-y-1">
                {summary.key_diagnoses.map((d, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.recent_records?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">Recent Records</p>
              <div className="space-y-2">
                {summary.recent_records.map((r, i) => (
                  <div key={i} className="border-l-2 border-amber-300 pl-3">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-medium text-amber-800 capitalize">
                        {r.type?.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs text-slate-400">{r.date}</span>
                    </div>
                    <p className="text-xs text-slate-600">{r.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.flagged_anomalies?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-red-600 uppercase tracking-wide mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Flagged Anomalies
              </p>
              <ul className="space-y-1">
                {summary.flagged_anomalies.map((a, i) => (
                  <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {summary.cached && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded-full">
              ⚡ Cached response
            </span>
          )}

          <p className="text-xs text-slate-400 border-t border-amber-200 pt-3 italic leading-relaxed">
            {summary.disclaimer}
          </p>
        </div>
      )}
    </Section>
  )
}

function FHIRResources({ bundle }) {
  const entries = bundle?.entry?.filter(e =>
    ['DocumentReference', 'DiagnosticReport'].includes(e.resource?.resourceType)
  ) || []

  if (!entries.length) return null

  return (
    <Section icon={FileText} title={`Linked FHIR Resources (${entries.length})`} colour="slate">
      <div className="space-y-2">
        {entries.map((e, i) => {
          const r = e.resource
          const rtype = r.resourceType
          const date  = (r.date || r.effectiveDateTime || r.issued || '').slice(0, 10)
          const coding = (r.type || r.code || {}).coding?.[0]
          const title  = r.description || coding?.display || rtype
          const Icon   = rtype === 'DiagnosticReport' ? FlaskConical : Stethoscope

          return (
            <div key={i} className="flex items-center gap-3 p-3 bg-white rounded-lg border border-slate-200">
              <div className="p-1.5 rounded-lg bg-slate-100">
                <Icon className="w-3.5 h-3.5 text-slate-500" aria-hidden />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 truncate">{title}</p>
                {date && (
                  <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                    <Calendar className="w-3 h-3" aria-hidden />
                    {formatDate(date)}
                  </p>
                )}
              </div>
              <ResourceBadge type={rtype} />
            </div>
          )
        })}
      </div>
    </Section>
  )
}

export default function PatientDrawer({ open, patient, loading, error, onClose }) {
  const drawerRef = useRef(null)

  // Focus trap + Escape key
  useEffect(() => {
    if (!open) return
    drawerRef.current?.focus()
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity duration-200
                    ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      />

      {/* Drawer */}
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Patient detail"
        tabIndex={-1}
        className={`fixed right-0 top-0 h-full w-full max-w-lg bg-slate-50 shadow-2xl z-50
                    transform transition-transform duration-250 ease-out overflow-y-auto scrollbar-thin
                    focus:outline-none
                    ${open ? 'translate-x-0 animate-slide-in' : 'translate-x-full'}`}
      >
        {/* Sticky header */}
        <div className="sticky top-0 bg-white/90 backdrop-blur border-b border-slate-200 px-5 py-4
                        flex items-center justify-between z-10">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-brand-500" />
            <h2 className="font-semibold text-slate-800">
              {patient ? `${patient.bundle?.entry?.[0]?.resource?.name?.[0]?.family || 'Patient'} · ${patient.mrn}` : 'Patient Record'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100
                       transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500"
            aria-label="Close panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {loading && (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="animate-pulse bg-white rounded-xl border border-slate-200 p-4 h-32" />
              ))}
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
              {error}
            </div>
          )}

          {patient && !loading && (
            <>
              <PatientHeader bundle={patient.bundle} />
              <AISummary summary={patient.summary} />
              <FHIRResources bundle={patient.bundle} />
            </>
          )}
        </div>
      </aside>
    </>
  )
}
