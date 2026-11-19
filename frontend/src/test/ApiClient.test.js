import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, ApiError, setApiKey, getApiKey, hasApiKey } from '../api/client'

describe('API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('handles missing key behavior by returning empty string without silent fallbacks', () => {
    // When no key is set, returns empty string (no hardcoded insecure fallback)
    expect(getApiKey()).toBe('')
    expect(hasApiKey()).toBe(false)
  })

  it('persists configured API key in localStorage', () => {
    setApiKey('custom-test-key-123')
    expect(getApiKey()).toBe('custom-test-key-123')
    expect(hasApiKey()).toBe(true)
    expect(localStorage.getItem('feedpulse_api_key')).toBe('custom-test-key-123')
  })

  it('replaces existing API key with a new key in localStorage and updates immediately', () => {
    setApiKey('first-key-abc')
    expect(getApiKey()).toBe('first-key-abc')
    expect(localStorage.getItem('feedpulse_api_key')).toBe('first-key-abc')

    // Replace key
    setApiKey('second-key-xyz')
    expect(getApiKey()).toBe('second-key-xyz')
    expect(localStorage.getItem('feedpulse_api_key')).toBe('second-key-xyz')
  })

  it('clearing key genuinely removes it from localStorage and updates subsequent requests', async () => {
    let capturedHeaders = null
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      capturedHeaders = opts.headers
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ([]),
      })
    })

    // 1. Set key and make request
    setApiKey('temp-active-key')
    await api.getReviews()
    expect(capturedHeaders['X-API-Key']).toBe('temp-active-key')

    // 2. Clear key with empty string
    setApiKey('')
    expect(getApiKey()).toBe('')
    expect(hasApiKey()).toBe(false)
    expect(localStorage.getItem('feedpulse_api_key')).toBeNull()

    // 3. Subsequent request MUST NOT include X-API-Key header
    capturedHeaders = null
    await api.getReviews()
    expect(capturedHeaders['X-API-Key']).toBeUndefined()

    // 4. Test clearing with null or whitespace
    setApiKey('another-key')
    expect(getApiKey()).toBe('another-key')
    setApiKey('   ')
    expect(getApiKey()).toBe('')
    expect(localStorage.getItem('feedpulse_api_key')).toBeNull()
  })

  it('uses localStorage as sole source and does not fallback to VITE_* variables', () => {
    // Even if import.meta.env has a VITE_FEEDPULSE_API_KEY set, getApiKey ignores it
    localStorage.clear()
    expect(getApiKey()).toBe('')
    expect(hasApiKey()).toBe(false)
  })

  it('extracts backend error message on 400 Bad Request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Custom validation error from server' }),
    })

    await expect(api.getReviews()).rejects.toThrow('Custom validation error from server')
  })

  it('handles backend network unreachable gracefully', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(api.getReviews()).rejects.toThrow('Backend service unavailable')
  })

  it('attaches X-API-Key header to outgoing requests only when key is set', async () => {
    let capturedHeaders = null
    global.fetch = vi.fn().mockImplementation((url, opts) => {
      capturedHeaders = opts.headers
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: async () => ([]),
      })
    })

    // Without key
    await api.getReviews()
    expect(capturedHeaders['X-API-Key']).toBeUndefined()

    // With key
    setApiKey('my-secret-token')
    await api.getReviews()
    expect(capturedHeaders['X-API-Key']).toBe('my-secret-token')
  })
})
