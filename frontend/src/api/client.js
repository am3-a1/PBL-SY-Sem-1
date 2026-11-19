/**
 * Centralized FeedPulse API Client
 * --------------------------------
 * Provides unified request handling, error message extraction,
 * timeout management, and API key authentication injection.
 */

export class ApiError extends Error {
  constructor(message, status = null, details = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export function getApiKey() {
  if (typeof localStorage !== 'undefined') {
    return localStorage.getItem('feedpulse_api_key') || (import.meta.env && import.meta.env.VITE_API_KEY) || 'feedpulse-dev-secret-key'
  }
  return (import.meta.env && import.meta.env.VITE_API_KEY) || 'feedpulse-dev-secret-key'
}

export function setApiKey(key) {
  if (typeof localStorage !== 'undefined') {
    if (key) {
      localStorage.setItem('feedpulse_api_key', key.trim())
    } else {
      localStorage.removeItem('feedpulse_api_key')
    }
  }
}

async function request(endpoint, options = {}) {
  const apiKey = getApiKey()
  const headers = { ...(options.headers || {}) }

  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }

  // Handle JSON body
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }

  try {
    const response = await fetch(endpoint, {
      ...options,
      headers,
    })

    // Handle 204 No Content
    if (response.status === 204) {
      return null
    }

    let data
    const contentType = response.headers.get('content-type')
    if (contentType && contentType.includes('application/json')) {
      data = await response.json()
    } else {
      data = await response.text()
    }

    if (!response.ok) {
      let errorMessage = `Request failed with status ${response.status}`
      if (typeof data === 'object' && data !== null) {
        errorMessage = data.detail || data.message || errorMessage
      } else if (typeof data === 'string' && data.length > 0) {
        errorMessage = data
      }
      throw new ApiError(errorMessage, response.status, data)
    }

    return data
  } catch (err) {
    if (err instanceof ApiError) {
      throw err
    }
    // Network or abort errors
    const isNetworkError = err.name === 'TypeError' && err.message.includes('fetch')
    const message = isNetworkError
      ? 'Backend service unavailable. Please check that the server is running on port 8000.'
      : err.message || 'An unexpected network error occurred.'
    throw new ApiError(message, null, err)
  }
}

export const api = {
  // Reviews
  getReviews: (params = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val)
      }
    })
    const qs = query.toString()
    return request(`/api/reviews${qs ? `?${qs}` : ''}`)
  },

  updateReviewStatus: (reviewId, newStatus) =>
    request(`/api/reviews/${reviewId}/status`, {
      method: 'PATCH',
      body: { status: newStatus },
    }),

  deleteReview: (reviewId) =>
    request(`/api/reviews/${reviewId}`, {
      method: 'DELETE',
    }),

  clearAllReviews: () =>
    request('/api/reviews', {
      method: 'DELETE',
    }),

  seedReviews: () =>
    request('/api/reviews/seed', {
      method: 'POST',
    }),

  uploadCsv: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/api/reviews/upload', {
      method: 'POST',
      body: formData,
    })
  },

  // Analytics
  getAnalyticsSummary: () => request('/api/analytics/summary'),

  // Themes
  getThemes: () => request('/api/themes'),
  escalateTheme: (themeId) => request(`/api/themes/${themeId}/escalate`, { method: 'POST' }),

  // Alerts
  getAlertConfig: () => request('/api/alerts/config'),
  updateAlertConfig: (payload) =>
    request('/api/alerts/config', {
      method: 'PUT',
      body: payload,
    }),
  testSlackAlert: (payload) =>
    request('/api/alerts/test', {
      method: 'POST',
      body: payload,
    }),

  // Health
  getHealth: () => request('/api/health'),
}

export default api
