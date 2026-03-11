import React from 'react'
import { Link } from 'react-router-dom'

const LABEL_COLORS = {
  safe: 'bg-green-100 text-green-700',
  hallucinated: 'bg-red-100 text-red-700',
  injection_detected: 'bg-orange-100 text-orange-700',
}

function LabelBadge({ label }) {
  if (!label) return <span className="text-gray-300 text-xs">—</span>
  const cls = LABEL_COLORS[label] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>
      {label}
    </span>
  )
}

/**
 * TraceTable — renders a list of trace summaries.
 *
 * Props:
 *   traces {Array}  — array of trace objects from GET /traces
 */
export default function TraceTable({ traces = [] }) {
  if (traces.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400 text-sm">
        No traces found.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100 shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-xs uppercase text-gray-500 tracking-wide">
          <tr>
            {['Trace ID', 'Timestamp', 'Model', 'Latency (ms)', 'Hallucination', 'Adversarial'].map(
              (h) => (
                <th key={h} className="text-left px-4 py-3 font-semibold">
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {traces.map((t) => (
            <tr key={t.id} className="bg-white hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 font-mono text-xs text-brand-600">
                <Link to={`/traces/${t.id}`} className="hover:underline">
                  {t.id?.slice(0, 16)}…
                </Link>
              </td>
              <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                {t.timestamp ? new Date(t.timestamp).toLocaleString() : '—'}
              </td>
              <td className="px-4 py-3 font-medium">{t.model_name || '—'}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                {t.latency_ms != null ? Number(t.latency_ms).toFixed(0) : '—'}
              </td>
              <td className="px-4 py-3">
                <LabelBadge label={t.hallucination_label} />
              </td>
              <td className="px-4 py-3">
                <LabelBadge label={t.adversarial_label} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
