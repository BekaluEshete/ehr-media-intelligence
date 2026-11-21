import { useState, useCallback } from 'react'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import ResultCard from './components/ResultCard'
import PatientDrawer from './components/PatientDrawer'
import Toast from './components/Toast'
import { WelcomeState, EmptyResults, LoadingSkeleton } from './components/EmptyStates'
import { useSearch } from './hooks/useSearch'
import { usePatient } from './hooks/usePatient'
import { api } from './lib/api'

export default function App() {
  // All search state lives here
  const [query,        setQuery]    = useState('')
  const [resourceType, setType]     = useState('')
  const [dateFrom,     setDateFrom] = useState('')
  const [dateTo,       setDateTo]   = useState('')

  const { results, loading: searching, error: apiError, meta, search, reset } = useSearch()
  const { patient, loading: patientLoading, error: patientError, open, fetchPatient, close } = usePatient()

  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [searchError, setSearchError] = useState(null)

  const showToast    = (message, type = 'info') => setToast({ message, type })
  const dismissToast = () => setToast(null)

  // ---------------------------------------------------------------------------
  // Core search — validates query before hitting the API
  // ---------------------------------------------------------------------------
  const doSearch = useCallback((overrides = {}) => {
    const q    = overrides.query        !== undefined ? overrides.query        : query
    const type = overrides.resourceType !== undefined ? overrides.resourceType : resourceType
    const from = overrides.dateFrom     !== undefined ? overrides.dateFrom     : dateFrom
    const to   = overrides.dateTo       !== undefined ? overrides.dateTo       : dateTo

    const trimmed = q.trim()
    if (!trimmed) return

    // Block gibberish: query must have at least 3 chars, at least 2 distinct
    // characters, and not be a single repeated character (e.g. "yyyyy", "aaaa")
    const distinctChars = new Set(trimmed.toLowerCase().replace(/\s/g, '')).size
    if (trimmed.length < 3 || distinctChars < 2) {
      setSearchError('Please enter a meaningful search term — e.g. "chest pain" or "HbA1c".')
      return
    }
    setSearchError(null)

    search({
      query:         trimmed,
      resource_type: type || null,
      date_from:     from || null,
      date_to:       to   || null,
    })
  }, [query, resourceType, dateFrom, dateTo, search])

  // ---------------------------------------------------------------------------
  // Handlers — update state AND immediately search with the new value
  // ---------------------------------------------------------------------------
  const handleQueryChange = useCallback((v) => {
    setQuery(v)
    if (searchError) setSearchError(null)  // clear validation error as user types
  }, [searchError])

  const handleTypeChange = useCallback((v) => {
    setType(v)
    doSearch({ resourceType: v })
  }, [doSearch])

  const handleDateFromChange = useCallback((v) => {
    setDateFrom(v)
    doSearch({ dateFrom: v })
  }, [doSearch])

  const handleDateToChange = useCallback((v) => {
    setDateTo(v)
    doSearch({ dateTo: v })
  }, [doSearch])

  const handleClearFilters = useCallback(() => {
    setType('')
    setDateFrom('')
    setDateTo('')
    if (query.trim()) {
      doSearch({ resourceType: '', dateFrom: '', dateTo: '' })
    } else {
      reset()
    }
  }, [query, doSearch, reset])

  // ---------------------------------------------------------------------------
  // Pipeline
  // ---------------------------------------------------------------------------
  const handleLoadData = useCallback(async () => {
    setPipelineLoading(true)
    showToast('Generating AI summaries with Gemini — ~20 seconds on first run…', 'info')
    try {
      const data = await api.runPipeline()
      showToast(
        `✓ ${data.patients_processed} patients · ${data.summaries_built} summaries · ${data.indexed_docs} docs indexed`,
        'success'
      )
    } catch (e) {
      showToast(`Pipeline failed: ${e.message}`, 'error')
    } finally {
      setPipelineLoading(false)
    }
  }, [])

  return (
    <div className="min-h-screen bg-slate-50">
      <a href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2
                   bg-brand-700 text-white px-4 py-2 rounded z-50 text-sm">
        Skip to main content
      </a>

      <Header onLoadData={handleLoadData} loading={pipelineLoading} />

      <main id="main" className="max-w-3xl mx-auto px-4 sm:px-6 py-8">

        {/* Search + filters */}
        <div className="mb-6">
          <SearchBar
            query={query}               onQueryChange={handleQueryChange}
            resourceType={resourceType} onTypeChange={handleTypeChange}
            dateFrom={dateFrom}         onDateFromChange={handleDateFromChange}
            dateTo={dateTo}             onDateToChange={handleDateToChange}
            onSearch={() => doSearch()} onClearFilters={handleClearFilters}
            loading={searching}
          />
        </div>

        {/* Validation error — bad query input */}
        {searchError && (
          <div role="alert"
            className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm flex items-center gap-2">
            <span>⚠</span> {searchError}
          </div>
        )}

        {/* API error — network or backend failure */}
        {apiError && !searchError && (
          <div role="alert"
            className="mb-4 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
            {apiError}
          </div>
        )}

        {/* Results meta */}
        {meta && !searching && (
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-medium text-slate-600">
              {meta.total > 0
                ? <>{meta.total} result{meta.total !== 1 ? 's' : ''} for <em>"{meta.query}"</em></>
                : <>No results for <em>"{meta.query}"</em></>}
            </p>
            <span className="text-xs text-slate-400 tabular-nums">{meta.elapsed_ms} ms</span>
          </div>
        )}

        {/* States */}
        {searching && <LoadingSkeleton />}

        {!searching && results === null && <WelcomeState />}

        {!searching && results?.length === 0 && <EmptyResults query={meta?.query} dataLoaded={meta?.data_loaded ?? true} />}

        {!searching && results?.length > 0 && (
          <ul className="space-y-3" role="list" aria-label="Search results">
            {results.map((r, i) => (
              <li key={r.doc_id}>
                <ResultCard result={r} index={i} onClick={fetchPatient} />
              </li>
            ))}
          </ul>
        )}
      </main>

      <PatientDrawer
        open={open}
        patient={patient}
        loading={patientLoading}
        error={patientError}
        onClose={close}
      />

      <Toast toast={toast} onDismiss={dismissToast} />

      {/* Footer — subtle tech info, not shown to end users prominently */}
      <footer className="mt-16 pb-6 text-center">
        <p className="text-xs text-slate-300">
          EHR Media Intelligence · AI-generated summaries are not validated clinical advice
          {meta?.embedding_provider && meta.embedding_provider !== 'stub' && (
            <span className="ml-2 inline-flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
              Semantic search active
            </span>
          )}
        </p>
      </footer>
    </div>
  )
}
