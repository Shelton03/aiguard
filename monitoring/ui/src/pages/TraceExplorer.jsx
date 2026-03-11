import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import TraceTable from '../components/TraceTable.jsx'

export default function TraceExplorer() {
  const [traces, setTraces] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Filter state
  const [model, setModel] = useState('')
  const [limit, setLimit] = useState(50)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [hLabel, setHLabel] = useState('')
  const [aLabel, setALabel] = useState('')

  const fetchTraces = () => {
    setLoading(true)
    setError(null)
    const params = {
      limit,
      ...(model && { model }),
      ...(dateFrom && { date_from: dateFrom }),
      ...(dateTo && { date_to: dateTo }),
      ...(hLabel && { hallucination_label: hLabel }),
      ...(aLabel && { adversarial_label: aLabel }),
    }
    api
      .getTraces(params)
      .then(setTraces)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchTraces()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Trace Explorer</h1>

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <input
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="Model name"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
        <input
          type="datetime-local"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          title="From date"
        />
        <input
          type="datetime-local"
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          title="To date"
        />
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={hLabel}
          onChange={(e) => setHLabel(e.target.value)}
        >
          <option value="">Any hallucination</option>
          <option value="safe">Safe</option>
          <option value="hallucinated">Hallucinated</option>
        </select>
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          value={aLabel}
          onChange={(e) => setALabel(e.target.value)}
        >
          <option value="">Any adversarial</option>
          <option value="safe">Safe</option>
          <option value="injection_detected">Injection detected</option>
        </select>
        <button
          className="bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
          onClick={fetchTraces}
        >
          {loading ? 'Loading…' : 'Search'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <TraceTable traces={traces} />
    </div>
  )
}
