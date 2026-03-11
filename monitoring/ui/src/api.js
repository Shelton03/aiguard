import axios from 'axios'

const BASE = '/api'

export const api = {
  // Traces
  getTraces: (params = {}) => axios.get(`${BASE}/traces`, { params }).then((r) => r.data),
  getTrace: (id) => axios.get(`${BASE}/traces/${id}`).then((r) => r.data),

  // Metrics
  getHallucinationRate: (windowHours = 24) =>
    axios.get(`${BASE}/metrics/hallucination_rate`, { params: { window_hours: windowHours } }).then((r) => r.data),
  getAdversarialRate: (windowHours = 24) =>
    axios.get(`${BASE}/metrics/adversarial_rate`, { params: { window_hours: windowHours } }).then((r) => r.data),
  getModelUsage: () => axios.get(`${BASE}/metrics/model_usage`).then((r) => r.data),
  getTraceVolume: (bucket = 'hour') =>
    axios.get(`${BASE}/metrics/trace_volume`, { params: { bucket } }).then((r) => r.data),

  // Review
  getReviewQueue: () => axios.get(`${BASE}/review/queue`).then((r) => r.data),
  getAllReviewItems: () => axios.get(`${BASE}/review/queue/all`).then((r) => r.data),
}
