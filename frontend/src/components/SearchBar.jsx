import { Search, X, SlidersHorizontal } from 'lucide-react'

/**
 * All state lives in App.jsx and is passed down as props.
 * This component is purely presentational — no internal state.
 */
export default function SearchBar({
  query, onQueryChange,
  resourceType, onTypeChange,
  dateFrom, onDateFromChange,
  dateTo, onDateToChange,
  onSearch, onClearFilters,
  loading,
}) {
  const hasFilters  = resourceType || dateFrom || dateTo
  const canSearch   = query.trim().length > 0

  function handleSubmit(e) {
    e.preventDefault()
    if (!canSearch) return
    onSearch()
  }

  return (
    <form onSubmit={handleSubmit} className="w-full" role="search" aria-label="Search patient records">

      {/* Search input row */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={e => onQueryChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && canSearch && onSearch()}
            placeholder="e.g. elevated HbA1c, chest pain, discharge summary…"
            className="w-full pl-10 pr-10 py-3 bg-white border border-slate-200 rounded-xl text-sm
                       placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500
                       focus:border-transparent shadow-sm"
            aria-label="Search query"
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              onClick={() => { onQueryChange(''); onClearFilters() }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              aria-label="Clear search"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Search button */}
        <button
          type="submit"
          disabled={loading || !canSearch}
          className="px-6 py-3 bg-brand-700 hover:bg-brand-800 disabled:opacity-50 disabled:cursor-not-allowed
                     text-white text-sm font-semibold rounded-xl transition-colors shadow-sm
                     focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
        >
          {loading
            ? <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Searching
              </span>
            : 'Search'}
        </button>
      </div>

      {/* Filter row — always visible, compact */}
      <div className="flex flex-wrap items-end gap-3 mt-3" role="group" aria-label="Search filters">

        {/* Resource type */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-type" className="text-xs font-medium text-slate-400 uppercase tracking-wide">
            Type
          </label>
          <select
            id="filter-type"
            value={resourceType}
            onChange={e => onTypeChange(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[160px]"
          >
            <option value="">All types</option>
            <option value="DocumentReference">Document Reference</option>
            <option value="DiagnosticReport">Diagnostic Report</option>
            <option value="Summary">AI Summary</option>
          </select>
        </div>

        {/* Date from */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-from" className="text-xs font-medium text-slate-400 uppercase tracking-wide">
            From
          </label>
          <input
            id="filter-from"
            type="date"
            value={dateFrom}
            onChange={e => onDateFromChange(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Date to */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-to" className="text-xs font-medium text-slate-400 uppercase tracking-wide">
            To
          </label>
          <input
            id="filter-to"
            type="date"
            value={dateTo}
            onChange={e => onDateToChange(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white
                       focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Clear filters */}
        {hasFilters && (
          <button
            type="button"
            onClick={onClearFilters}
            className="mb-0.5 text-xs text-slate-400 hover:text-brand-600 underline
                       focus:outline-none focus:ring-1 focus:ring-brand-500 rounded"
            aria-label="Clear all filters"
          >
            Clear filters
          </button>
        )}

        {/* Active filter pills */}
        <div className="flex flex-wrap gap-1.5 ml-auto">
          {resourceType && (
            <span className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 text-xs
                             font-medium px-2 py-1 rounded-full border border-brand-200">
              {resourceType === 'DocumentReference' ? 'Document'
                : resourceType === 'DiagnosticReport' ? 'Diagnostic'
                : resourceType}
              <button onClick={() => onTypeChange('')}
                className="hover:text-brand-900" aria-label="Remove type filter">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
          {dateFrom && (
            <span className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 text-xs
                             font-medium px-2 py-1 rounded-full border border-brand-200">
              From {dateFrom}
              <button onClick={() => onDateFromChange('')}
                className="hover:text-brand-900" aria-label="Remove date from filter">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
          {dateTo && (
            <span className="inline-flex items-center gap-1 bg-brand-50 text-brand-700 text-xs
                             font-medium px-2 py-1 rounded-full border border-brand-200">
              To {dateTo}
              <button onClick={() => onDateToChange('')}
                className="hover:text-brand-900" aria-label="Remove date to filter">
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
        </div>
      </div>

    </form>
  )
}
