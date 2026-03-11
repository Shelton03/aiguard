import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'

const LABEL_COLOR = {
  safe: 'text-green-600 bg-green-50',
  hallucinated: 'text-red-600 bg-red-50',
  injection_detected: 'text-orange-600 bg-orange-50',
}

function Badge({ label }) {
  if (!label) return <span className="text-gray-400">—</span>
  const cls = LABEL_COLOR[label] || 'text-gray-600 bg-gray-50'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
  )
}

function Field({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">{label}</span>
      <span className="text-sm text-gray-800 break-words">{value ?? '—'}</span>
    </div>
  )
}

export default function TraceDetail() {
  const { traceId } = useParams()
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .getTrace(traceId)
      .then(setTrace)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [traceId])

  if (loading) return <p className="text-gray-400 py-16 text-center">Loading…</p>
  if (error)
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
        {error}
      </div>
    )
  if (!trace) return <p className="text-gray-400">Trace not found.</p>

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link to="/traces" className="text-brand-600 text-sm hover:underline">
        ← Back to traces
      </Link>

      <h1 className="text-xl font-bold text-gray-800 font-mono break-all">{trace.id}</h1>

      {/* Core fields */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 grid grid-cols-2 md:grid-cols-3 gap-5">
        <Field label="Timestamp" value={trace.timestamp && new Date(trace.timestamp).toLocaleString()} />
        <Field label="Model" value={trace.model_name} />
        <Field label="Model Version" value={trace.model_version} />
        <Field label="Latency (ms)" value={trace.latency_ms != null ? Number(trace.latency_ms).toFixed(0) : null} />
        <Field label="Tokens Used" value={trace.tokens_used} />
        <Field label="Environment" value={trace.environment} />
      </div>

      {/* Prompt & Response */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-xs font-semibold text-gray-500 uppercase mb-3">Prompt</h2>
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{trace.prompt || '—'}</pre>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-xs font-semibold text-gray-500 uppercase mb-3">Response</h2>
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{trace.response || '—'}</pre>
        </div>
      </div>

      {/* Evaluations */}
      {trace.evaluations && trace.evaluations.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">
            Evaluation Results
          </h2>
          {trace.evaluations.map((ev) => (
            <div
              key={ev.id}
              className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-3"
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold capitalize text-gray-800">{ev.module}</span>
                <Badge label={ev.risk_level} />
                <span className="text-xs text-gray-400">{ev.mode} / {ev.execution_mode}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {ev.scores &&
                  Object.entries(ev.scores).map(([k, v]) => (
                    <div key={k} className="text-xs">
                      <span className="text-gray-500">{k}: </span>
                      <span className="font-semibold text-gray-800">
                        {v != null ? Number(v).toFixed(3) : '—'}
                      </span>
                    </div>
                  ))}
              </div>
              {ev.confidence != null && (
                <p className="text-xs text-gray-500">
                  Confidence: <span className="font-semibold">{Number(ev.confidence).toFixed(3)}</span>
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
