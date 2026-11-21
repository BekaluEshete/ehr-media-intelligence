import { useState, useCallback } from 'react'
import { api } from '../lib/api'

export function usePatient() {
  const [patient, setPatient]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [open, setOpen]         = useState(false)

  const fetchPatient = useCallback(async (mrn) => {
    setOpen(true)
    setLoading(true)
    setError(null)
    setPatient(null)
    try {
      const data = await api.getPatient(mrn)
      setPatient(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const close = useCallback(() => {
    setOpen(false)
    setPatient(null)
  }, [])

  return { patient, loading, error, open, fetchPatient, close }
}
