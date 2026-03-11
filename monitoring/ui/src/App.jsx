import React from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import ReviewQueue from './pages/ReviewQueue.jsx'
import TraceDetail from './pages/TraceDetail.jsx'
import TraceExplorer from './pages/TraceExplorer.jsx'

const NAV_LINKS = [
  { to: '/', label: 'Dashboard' },
  { to: '/traces', label: 'Traces' },
  { to: '/review', label: 'Review Queue' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Top nav */}
        <nav className="bg-brand-600 text-white shadow">
          <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-8">
            <Link to="/" className="font-bold text-lg tracking-tight">
              ✦ AIGuard
            </Link>
            {NAV_LINKS.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `text-sm font-medium transition-opacity ${isActive ? 'opacity-100 underline underline-offset-4' : 'opacity-70 hover:opacity-100'}`
                }
              >
                {label}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Page content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/traces" element={<TraceExplorer />} />
            <Route path="/traces/:traceId" element={<TraceDetail />} />
            <Route path="/review" element={<ReviewQueue />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
