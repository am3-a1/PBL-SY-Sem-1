/**
 * Centralized FeedPulse API Client
 * --------------------------------
 * Provides unified request handling, error message extraction,
 * timeout management, and API key authentication injection.
 *
 * Security Note:
 * Browser localStorage is the sole source for configuring the frontend API key.
 * Secrets are never bundled into client-side Vite environment variables.
 * This client token acts as a shared API passphrase to protect destructive operations,
 * not as strong user authentication or multi-tenant session management.
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
    const localKey = localStorage.getItem('feedpulse_api_key')
    if (localKey && localKey.trim()) {
      return localKey.trim()
    }
  }
  return ''
}

export function hasApiKey() {
  return Boolean(getApiKey())
}

export function setApiKey(key) {
  if (typeof localStorage !== 'undefined') {
    if (key && key.trim()) {
      localStorage.setItem('feedpulse_api_key', key.trim())
    } else {
      localStorage.removeItem('feedpulse_api_key')
    }
  }
}

async function request(endpoint, options = {}) {
  const apiKey = getApiKey()
  const headers = { ...(options.headers || {}) }

  // Inject authentication header only when an API key is actually configured
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
        if (data.detail) {
          errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        } else if (data.message) {
          errorMessage = data.message
        }
      } else if (typeof data === 'string' && data.trim()) {
        errorMessage = data.trim()
      }
      throw new ApiError(errorMessage, response.status, data)
    }

    return data
  } catch (err) {
    if (err instanceof ApiError) {
      throw err
    }
    // Network or client errors (e.g. Failed to fetch)
    const message = err.message ? err.message : 'Backend service unavailable. Please check your connection.'
    throw new ApiError(
      message.includes('Failed to fetch') || message.includes('NetworkError')
        ? 'Backend service unavailable. Ensure the server is running.'
        : message,
      null,
      err
    )
  }
}

export const api = {
  // Reviews
  async getReviews(params = {}) {
    const query = new URLSearchParams()
    if (params.source) query.set('source', params.source)
    if (params.sentiment) query.set('sentiment', params.sentiment)
    if (params.theme) query.set('theme', params.theme)
    if (params.status) query.set('status', params.status)
    if (params.search) query.set('search', params.search)
    if (params.sort_by) query.set('sort_by', params.sort_by)
    if (params.sort_order) query.set('sort_order', params.sort_order)
    if (params.page) query.set('page', params.page)
    if (params.page_size) query.set('page_size', params.page_size)

    const qs = query.toString()
    return request(`/api/reviews${qs ? `?${qs}` : ''}`)
  },

  async updateReviewStatus(reviewId, status) {
    return request(`/api/reviews/${reviewId}/status`, {
      method: 'PATCH',
      body: { status },
    })
  },

  async deleteReview(reviewId) {
    return request(`/api/reviews/${reviewId}`, {
      method: 'DELETE',
    })
  },

  async clearAllReviews() {
    return request('/api/reviews', {
      method: 'DELETE',
    })
  },

  async seedReviews() {
    return request('/api/reviews/seed', {
      method: 'POST',
    })
  },

  async seedMockReviews() {
    return this.seedReviews()
  },

  async uploadCsv(file) {
    const formData = new FormData()
    formData.append('file', file)
    return request('/api/reviews/upload', {
      method: 'POST',
      body: formData,
    })
  },

  // Themes
  async getThemes() {
    return request('/api/themes')
  },

  async escalateTheme(themeId) {
    return request(`/api/themes/${themeId}/escalate`, {
      method: 'POST',
    })
  },

  // Analytics
  async getAnalyticsSummary(timeframe = '30d') {
    return request(`/api/analytics/summary?timeframe=${encodeURIComponent(timeframe)}`)
  },

  // Alerts
  async getAlertConfig() {
    return request('/api/alerts/config')
  },

  async updateAlertConfig(config) {
    return request('/api/alerts/config', {
      method: 'PUT',
      body: config,
    })
  },

  async sendTestAlert(data = {}) {
    return request('/api/alerts/test', {
      method: 'POST',
      body: data,
    })
  },

  // Health
  async getHealth() {
    return request('/health')
  },
}

export default api
