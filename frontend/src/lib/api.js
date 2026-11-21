const BASE = '/api/v1'

async function request(path, options = {}) {
  // Pipeline endpoint calls Gemini 11x — give it 90 seconds
  const timeout = path.includes('pipeline') ? 90000 : 15000
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)

  try {
    const res = await fetch(`${BASE}${path}`, { ...options, signal: controller.signal })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return res.json()
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  runPipeline: () =>
    request('/pipeline/run', { method: 'POST' }),

  listPatients: () =>
    request('/patients'),

  getPatient: (mrn) =>
    request(`/patients/${encodeURIComponent(mrn)}`),

  search: ({ query, top_k = 5, resource_type, date_from, date_to }) =>
    request('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        top_k,
        resource_type: resource_type || null,
        date_from: date_from || null,
        date_to: date_to || null,
      }),
    }),
}
