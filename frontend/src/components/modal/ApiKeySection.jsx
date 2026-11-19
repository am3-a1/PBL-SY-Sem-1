import React, { useState } from 'react'
import { Eye, EyeOff, Key, CheckCircle, AlertTriangle } from 'lucide-react'
import { getApiKey, setApiKey, hasApiKey } from '../../api/client'

export default function ApiKeySection() {
  const [keyInput, setKeyInput] = useState('')
  const [isConfigured, setIsConfigured] = useState(hasApiKey())
  const [showKey, setShowKey] = useState(false)
  const [feedback, setFeedback] = useState(null)

  const handleSave = (e) => {
    e.preventDefault()
    const trimmed = keyInput.trim()
    if (!trimmed) {
      setFeedback({ type: 'error', message: 'Please enter a non-empty API key to save.' })
      return
    }
    setApiKey(trimmed)
    setIsConfigured(true)
    setKeyInput('')
    setFeedback({ type: 'success', message: 'API key saved to browser local storage. Requests will use this key.' })
  }

  const handleClear = () => {
    setApiKey('')
    setIsConfigured(false)
    setKeyInput('')
    setFeedback({ type: 'info', message: 'API key removed from local storage. Mutating operations will require authentication.' })
  }

  return (
    <div className="space-y-6">
      {/* Overview & Security Context */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-ink flex items-center gap-2">
          <Key className="w-3.5 h-3.5 text-action" />
          API Key Configuration
        </h3>
        <p className="text-muted leading-relaxed">
          FeedPulse secures data-modifying endpoints (CSV ingestion, status updates, deletions, demo data, and alert configuration) using an API key.
        </p>
      </div>

      {/* Configuration Status Indicator (Never exposes the raw key value) */}
      <div className="p-3 rounded border border-line bg-surface flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isConfigured ? (
            <CheckCircle className="w-4 h-4 text-positive flex-shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />
          )}
          <div>
            <span className="font-medium text-ink">
              Status:{' '}
              {isConfigured ? (
                <span className="text-positive font-semibold">Configured</span>
              ) : (
                <span className="text-warning font-semibold">Not configured</span>
              )}
            </span>
            <p className="text-muted text-[11px] mt-0.5">
              {isConfigured
                ? 'An API key is active in your browser and attached to mutating API calls.'
                : 'No key is currently stored. Mutating requests will fail with HTTP 401.'}
            </p>
          </div>
        </div>
        {isConfigured && (
          <button
            type="button"
            onClick={handleClear}
            className="px-2.5 py-1 text-xs rounded border border-line text-muted hover:text-negative hover:border-negative transition-colors"
          >
            Clear key
          </button>
        )}
      </div>

      {/* Input Form */}
      <form onSubmit={handleSave} className="space-y-4">
        <div>
          <label htmlFor="apiKeyInput" className="block text-ink font-medium mb-1">
            {isConfigured ? 'Replace API Key' : 'Enter API Key'}
          </label>
          <div className="relative">
            <input
              id="apiKeyInput"
              type={showKey ? 'text' : 'password'}
              value={keyInput}
              onChange={(e) => {
                setKeyInput(e.target.value)
                if (feedback) setFeedback(null)
              }}
              placeholder={isConfigured ? '••••••••••••••••' : 'Enter your FEEDPULSE_API_KEY'}
              autoComplete="off"
              className="w-full px-3 py-2 pr-10 rounded border border-line bg-paper text-ink focus:outline-none focus:ring-1 focus:ring-action font-mono text-xs"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              aria-label={showKey ? 'Hide API key' : 'Show API key'}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-ink p-1"
            >
              {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {feedback && (
          <div
            className={`p-2 rounded text-xs border ${
              feedback.type === 'error'
                ? 'border-negative/30 bg-negative/5 text-negative'
                : feedback.type === 'success'
                ? 'border-positive/30 bg-positive/5 text-positive'
                : 'border-line bg-surface text-ink'
            }`}
          >
            {feedback.message}
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!keyInput.trim()}
            className="px-3.5 py-1.5 rounded bg-action text-white hover:bg-action/90 font-medium transition-colors disabled:opacity-40"
          >
            Save API Key
          </button>
        </div>
      </form>

      {/* Documentation Note */}
      <div className="pt-4 border-t border-line text-[11px] text-muted space-y-1">
        <p className="font-medium text-ink">About API Key Security:</p>
        <p>
          Keys entered here are persisted in your browser&apos;s <code>localStorage</code> and transmitted via the <code>X-API-Key</code> request header. In production, configure the matching key via <code>FEEDPULSE_API_KEY</code> on your backend server.
        </p>
      </div>
    </div>
  )
}
