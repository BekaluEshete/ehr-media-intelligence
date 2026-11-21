import { useState, useCallback } from 'react'
import { api } from '../lib/api'

export function useSearch() {
  const [results, setResults]   = useState(null)   // null = not searched yet
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [meta, setMeta]         = useState(null)   // { total, elapsed_ms, query }

  const search = useCallback(async (params) => {
    if (!params.query?.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.search(params)
      setResults(data.results)
      setMeta({
        total: data.total,
        elapsed_ms: data.elapsed_ms,
        query: data.query,
        data_loaded: data.data_loaded,
        embedding_provider: data.embedding_provider,
      })
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setResults(null)
    setError(null)
    setMeta(null)
  }, [])

  return { results, loading, error, meta, search, reset }
}
