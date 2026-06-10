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

function Field({ label, value, hint }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">{label}</span>
      <span className="text-sm text-gray-800 break-words">{value ?? '—'}</span>
      {hint && <span className="text-[11px] text-gray-400">{hint}</span>}
    </div>
  )
}

function TaxonomyRow({ label, value }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-800">{value || '—'}</span>
    </div>
  )
}

function deriveTaxonomy(category) {
  if (!category || typeof category !== 'string') {
    return { family: '—', subtype: '—', source: 'unknown' }
  }
  if (!category.includes('/')) {
    return { family: category, subtype: '—', source: 'unknown' }
  }
  const [family, subtype] = category.split('/')
  return { family, subtype, source: 'unknown' }
}

export default function TraceDetail() {
  const { traceId } = useParams()
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [rejudgeLoading, setRejudgeLoading] = useState(false)
  const [rejudgeError, setRejudgeError] = useState(null)

  useEffect(() => {
    api
      .getTrace(traceId)
      .then(setTrace)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [traceId])

  const handleRejudge = async () => {
    setRejudgeError(null)
    setRejudgeLoading(true)
    try {
      await api.rejudgeTrace(traceId, true)
      const refreshed = await api.getTrace(traceId)
      setTrace(refreshed)
    } catch (e) {
      setRejudgeError(e.message)
    } finally {
      setRejudgeLoading(false)
    }
  }

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

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-xl font-bold text-gray-800 font-mono break-all">{trace.id}</h1>
          <p className="text-sm text-gray-500">
            Full trace record including prompt, model response, and evaluation signals.
          </p>
        </div>
        <div className="flex flex-col items-start gap-2">
          <button
            type="button"
            onClick={handleRejudge}
            disabled={rejudgeLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 hover:bg-brand-100 disabled:opacity-60"
          >
            {rejudgeLoading ? 'Re-evaluating…' : 'Force judge re-evaluation'}
          </button>
          {rejudgeError && <span className="text-xs text-red-500">{rejudgeError}</span>}
        </div>
      </div>

      {/* Core fields */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 grid grid-cols-2 md:grid-cols-3 gap-5">
        <Field
          label="Timestamp"
          value={trace.timestamp && new Date(trace.timestamp).toLocaleString()}
          hint="When the request completed (local time)."
        />
        <Field label="Model" value={trace.model_name} hint="Provider model identifier." />
        <Field label="Model Version" value={trace.model_version} hint="Optional version tag." />
        <Field
          label="Latency (ms)"
          value={trace.latency_ms != null ? Number(trace.latency_ms).toFixed(0) : null}
          hint="Round-trip time for the model call."
        />
        <Field label="Tokens Used" value={trace.tokens_used} hint="Total token usage if available." />
        <Field label="Environment" value={trace.environment} hint="Runtime environment tag." />
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

      {/* Metadata */}
      {trace.metadata && Object.keys(trace.metadata).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
          <h2 className="text-xs font-semibold text-gray-500 uppercase mb-3">Metadata</h2>
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">
            {JSON.stringify(trace.metadata, null, 2)}
          </pre>
        </div>
      )}

        {/* Evaluations */}
        {trace.evaluations && trace.evaluations.length > 0 && (
          <div className="space-y-4">
            <div>
              <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">
                Evaluation Results
              </h2>
              <p className="text-xs text-gray-500 mt-1">
                Labels summarize risk signals per module. Scores are normalized to 0–1.
              </p>
            </div>
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
                
                {/* Hallucination-specific details - only when detected */}
                {ev.module === 'hallucination' && ev.label && ev.label !== 'safe' && (
                  <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">
                      Hallucination Details
                    </div>
                    <div className="space-y-1">
                      {/* Show family (e.g., "factuality") */}
                      {ev.hallucination_family && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Category:</span>{' '}
                          <span className="font-medium">{ev.hallucination_family}</span>
                        </div>
                      )}
                      {/* Show subtype (e.g., "entity_error") - only if available */}
                      {ev.hallucination_subtype && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Subtype:</span>{' '}
                          <span className="font-medium">{ev.hallucination_subtype}</span>
                        </div>
                      )}
                      {ev.source && ev.source !== 'unknown' && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Source:</span>{' '}
                          <span className="font-medium capitalize">{ev.source}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Adversarial-specific details - only when detected */}
                {ev.module === 'adversarial' && ev.label && ev.label !== 'safe' && (
                  <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                    <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide mb-2">
                      Attack Details
                    </div>
                    <div className="space-y-1">
                      {ev.attack_type && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Attack Type:</span>{' '}
                          <span className="font-medium">{ev.attack_type}</span>
                        </div>
                      )}
                      {ev.subtype && ev.subtype !== 'unknown' && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Subtype:</span>{' '}
                          <span className="font-medium">{ev.subtype}</span>
                        </div>
                      )}
                      {ev.compliance_status && ev.compliance_status !== 'complied' && (
                        <div className="text-xs text-slate-700">
                          <span className="font-semibold text-slate-500">Compliance:</span>{' '}
                          <span className="font-medium capitalize">{ev.compliance_status}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Risk reason - only if not "none" */}
                {ev.risk_reason && ev.risk_reason.toLowerCase() !== 'none' && (
                  <div className="rounded-md bg-white/60 px-2 py-1 text-[11px] text-slate-600">
                    <span className="font-semibold text-slate-500">Risk reason:</span>{' '}
                    {ev.risk_reason}
                  </div>
                )}
                
                {/* Explanation - only if not safe */}
                {ev.explanation && ev.label && ev.label !== 'safe' && (
                  <div className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-700">
                    <span className="font-semibold text-slate-500 block mb-1">Explanation:</span>
                    {ev.explanation}
                  </div>
                )}
                
                {/* Full Judge Response - expandable */}
                <details className="mt-3">
                  <summary className="text-xs text-brand-600 cursor-pointer hover:underline">
                    View full judge response
                  </summary>
                  <pre className="mt-2 text-[10px] text-gray-600 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded max-h-64 overflow-y-auto">
                    {JSON.stringify(ev.metadata, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}
