import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
}

function StatusBadge({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>
      {status || 'unknown'}
    </span>
  )
}

export default function ReviewQueue() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAll, setShowAll] = useState(false)

  const fetchItems = () => {
    setLoading(true)
    const fn = showAll ? api.getAllReviewItems : api.getReviewQueue
    fn()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchItems()
  }, [showAll]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Review Queue</h1>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-500 flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAll(e.target.checked)}
              className="rounded"
            />
            Show all
          </label>
          <button
            className="text-sm bg-brand-600 text-white rounded-lg px-4 py-2 hover:bg-brand-700 transition-colors"
            onClick={fetchItems}
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray-400 py-16 text-center">Loading…</p>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          {showAll ? 'No review items found.' : 'No pending items in the review queue.'}
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.id}
              className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-brand-600">{item.id}</span>
                <StatusBadge status={item.status} />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-500">Module</p>
                  <p className="font-medium capitalize">{item.module_type || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Raw Score</p>
                  <p className="font-medium tabular-nums">
                    {item.raw_score != null ? Number(item.raw_score).toFixed(3) : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Trigger</p>
                  <p className="font-medium">{item.trigger_reason || '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Created</p>
                  <p className="font-medium">
                    {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}
                  </p>
                </div>
              </div>
              {item.model_response && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">Model Response</p>
                  <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans bg-gray-50 rounded-lg p-3 max-h-40 overflow-y-auto">
                    {item.model_response}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
