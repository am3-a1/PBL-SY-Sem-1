import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, ApiError, setApiKey, getApiKey, hasApiKey } from '../api/client'

describe('API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('sets and retrieves API key properly without silent fallback', () => {
    // When no key is set, returns empty string (no hardcoded insecure fallback)
    expect(getApiKey()).toBe('')
    expect(hasApiKey()).toBe(false)

    setApiKey('custom-test-key')
    expect(getApiKey()).toBe('custom-test-key')
    expect(hasApiKey()).toBe(true)

    setApiKey('')
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
