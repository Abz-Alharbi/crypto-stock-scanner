import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''
const ACCESS_TOKEN_KEY = 'access_token'

let unauthorizedHandler = null

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler
}

const api = axios.create({
  baseURL: `${API_URL}/api`,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// JWT interceptor
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 handler
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
      localStorage.removeItem('auth_user')
      unauthorizedHandler?.()
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
  changePassword: (data) => api.post('/auth/change-password', data),
}

export const marketAPI = {
  health: () => api.get('/health'),
  getFilters: () => api.get('/filters'),
  scan: (data) => api.post('/scan', data, { timeout: 600000 }),
  getScanStatus: (jobId) => api.get(`/scan/status/${jobId}`),
  cancelScan: (jobId) => api.delete(`/scan/${jobId}`),
  search: (query, market, config = {}) => api.get('/search', { ...config, params: { ...config.params, q: query, market } }),
  getStockDetail: (symbol, timeframe) => api.get(`/stock/${symbol}`, { params: { timeframe }, timeout: 120000 }),
}

export const newsAPI = {
  getNews: (symbol, params = {}) => api.get(`/news/${symbol}`, { params, timeout: 60000 }),
}

export const fundamentalsAPI = {
  get: (symbol) => api.get(`/fundamentals/${symbol}`, { timeout: 120000 }),
}

export const watchlistAPI = {
  get: () => api.get('/watchlist'),
  add: (data) => api.post('/watchlist', data),
  update: (id, data) => api.patch(`/watchlist/${id}`, data),
  remove: (id) => api.delete(`/watchlist/${id}`),
}

export const adminAPI = {
  getUsers: (params) => api.get('/admin/users', { params }),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  getStats: () => api.get('/admin/stats'),
  getScans: () => api.get('/admin/scans'),
  getAuditLogs: () => api.get('/admin/audit-logs'),
}

export const healthAPI = {
  check: () => api.get('/health'),
}

export default api
