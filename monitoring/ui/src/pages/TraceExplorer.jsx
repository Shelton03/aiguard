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
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-800">Trace Explorer</h1>
        <p className="text-sm text-gray-500">
          Live request traces captured by the SDK. Filter by model, time window, or
          evaluation labels to spot risky behavior quickly.
        </p>
      </div>

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Model</label>
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="gpt-4o"
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <span className="text-[11px] text-gray-400">Exact model identifier.</span>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">From</label>
          <input
            type="datetime-local"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            title="From date"
          />
          <span className="text-[11px] text-gray-400">Start of time range.</span>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">To</label>
          <input
            type="datetime-local"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            title="To date"
          />
          <span className="text-[11px] text-gray-400">End of time range.</span>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Hallucination</label>
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={hLabel}
            onChange={(e) => setHLabel(e.target.value)}
          >
            <option value="">Any label</option>
            <option value="safe">Safe</option>
            <option value="hallucinated">Hallucinated</option>
          </select>
          <span className="text-[11px] text-gray-400">Correctness risk signal.</span>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Adversarial</label>
          <select
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={aLabel}
            onChange={(e) => setALabel(e.target.value)}
          >
            <option value="">Any label</option>
            <option value="safe">Safe</option>
            <option value="injection_detected">Injection detected</option>
          </select>
          <span className="text-[11px] text-gray-400">Prompt injection signal.</span>
        </div>
        <div className="flex flex-col gap-1 justify-end">
          <button
            className="bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2 text-sm font-semibold transition-colors"
            onClick={fetchTraces}
          >
            {loading ? 'Loading…' : 'Search'}
          </button>
          <span className="text-[11px] text-gray-400">Refreshes trace list.</span>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {[
          {
            title: 'Trace ID',
            body: 'Unique identifier per request. Click to inspect full prompt + response.',
          },
          {
            title: 'Latency',
            body: 'End-to-end model response time in milliseconds (lower is faster).',
          },
          {
            title: 'Labels',
            body: 'Risk signals from hallucination and adversarial evaluators.',
          },
        ].map((item) => (
          <div key={item.title} className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
            <div className="text-sm font-semibold text-gray-800">{item.title}</div>
            <div className="text-xs text-gray-500 mt-1">{item.body}</div>
          </div>
        ))}
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
