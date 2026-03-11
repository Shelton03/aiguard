import React from 'react'

/**
 * MetricCard — displays a single KPI value.
 *
 * Props:
 *   title    {string}
 *   value    {string|number}
 *   subtitle {string}  optional
 *   color    {string}  Tailwind text colour class, e.g. "text-red-500"
 */
export default function MetricCard({ title, value, subtitle, color = 'text-brand-600' }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col gap-1">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</p>
      <p className={`text-3xl font-bold ${color}`}>{value ?? '—'}</p>
      {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
    </div>
  )
}
