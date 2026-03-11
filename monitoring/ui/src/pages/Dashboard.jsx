import React, { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api.js'
import MetricCard from '../components/MetricCard.jsx'

export default function Dashboard() {
  const [hRate, setHRate] = useState(null)
  const [aRate, setARate] = useState(null)
  const [modelUsage, setModelUsage] = useState({})
  const [volumeData, setVolumeData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.getHallucinationRate(24),
      api.getAdversarialRate(24),
      api.getModelUsage(),
      api.getTraceVolume('hour'),
    ])
      .then(([h, a, m, v]) => {
        setHRate(h.hallucination_rate)
        setARate(a.adversarial_rate)
        setModelUsage(m.model_usage || {})
        setVolumeData(v)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const totalModels = Object.keys(modelUsage).length
  const totalTraces = Object.values(modelUsage).reduce((s, v) => s + v, 0)

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          Could not connect to API: {error}
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Hallucination Rate (24h)"
          value={loading ? '…' : `${((hRate || 0) * 100).toFixed(1)}%`}
          color={hRate > 0.1 ? 'text-red-500' : 'text-green-600'}
          subtitle="of evaluated traces"
        />
        <MetricCard
          title="Adversarial Rate (24h)"
          value={loading ? '…' : `${((aRate || 0) * 100).toFixed(1)}%`}
          color={aRate > 0.05 ? 'text-orange-500' : 'text-green-600'}
          subtitle="injection patterns"
        />
        <MetricCard
          title="Total Traces"
          value={loading ? '…' : totalTraces.toLocaleString()}
          subtitle="all time"
        />
        <MetricCard
          title="Models Tracked"
          value={loading ? '…' : totalModels}
          subtitle="distinct model names"
        />
      </div>

      {/* Trace volume chart */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="text-sm font-semibold text-gray-600 mb-4 uppercase tracking-wide">
          Trace Volume (hourly)
        </h2>
        {volumeData.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-8">No data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={volumeData} margin={{ top: 4, right: 24, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="bucket"
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => v.slice(11, 16) || v.slice(5, 10)}
              />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#6366f1"
                strokeWidth={2}
                dot={false}
                name="Traces"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Model usage */}
      {Object.keys(modelUsage).length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-sm font-semibold text-gray-600 mb-4 uppercase tracking-wide">
            Traces by Model
          </h2>
          <ul className="divide-y divide-gray-50">
            {Object.entries(modelUsage).map(([model, count]) => (
              <li key={model} className="flex justify-between items-center py-2 text-sm">
                <span className="font-medium text-gray-700">{model}</span>
                <span className="text-gray-500 tabular-nums">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
