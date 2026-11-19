import React, { useState, useEffect } from 'react'
import api from '../../api/client'

export default function SlackConfigSection({
  alertConfig,
  onUpdateAlertConfig,
}) {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [threshold, setThreshold] = useState(30.0)
  const [isEnabled, setIsEnabled] = useState(true)

  // Status message states
  const [testStatus, setTestStatus] = useState(null)
  const [isTestingSlack, setIsTestingSlack] = useState(false)
  const [isSavingConfig, setIsSavingConfig] = useState(false)

  // Sync state whenever alertConfig changes (fixes stale modal configuration bug)
  useEffect(() => {
    if (alertConfig) {
      setWebhookUrl(alertConfig.slack_webhook_url || '')
      setThreshold(alertConfig.negative_threshold_pct ?? 30.0)
      setIsEnabled(alertConfig.is_enabled ?? true)
    }
  }, [alertConfig])

  // Save Slack Alert Config
  const handleSaveConfig = async () => {
    setIsSavingConfig(true)
    setTestStatus(null)
    try {
      const data = await api.updateAlertConfig({
        slack_webhook_url: webhookUrl,
        negative_threshold_pct: parseFloat(threshold),
        is_enabled: isEnabled,
      })
      if (onUpdateAlertConfig) onUpdateAlertConfig(data)
      setTestStatus({
        type: 'success',
        message: 'Alert configuration saved successfully.',
      })
    } catch (err) {
      setTestStatus({
        type: 'error',
        message: err.message || 'Failed to save configuration.',
      })
    } finally {
      setIsSavingConfig(false)
    }
  }

  // Send Test Slack notification
  const handleTestSlack = async () => {
    setIsTestingSlack(true)
    setTestStatus(null)

    try {
      const data = await api.testSlackAlert({
        webhook_url: webhookUrl,
        sample_text: 'The app crashes repeatedly on the 2FA login verification code step.',
      })
      setTestStatus({
        type: data.status === 'error' ? 'error' : 'success',
        message: data.message,
        payload: data.payload,
        is_sandbox: data.is_sandbox,
      })
    } catch (err) {
      setTestStatus({
        type: 'error',
        message: err.message || 'Network error calling test endpoint.',
      })
    } finally {
      setIsTestingSlack(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <label
          htmlFor="slack-webhook-input"
          className="block text-xs font-medium text-ink mb-1.5"
        >
          Slack incoming webhook URL
        </label>
        <input
          id="slack-webhook-input"
          type="url"
          placeholder="https://hooks.slack.com/services/..."
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          className="w-full bg-surface border border-line text-ink placeholder-muted rounded px-3 py-2 text-xs focus:border-action focus-visible:outline-none"
        />
        <p className="text-muted mt-1">
          {alertConfig?.has_slack_webhook ? (
            <span className="text-positive font-medium">✓ Active webhook configured. </span>
          ) : null}
          Leave blank to use the built-in sandbox simulator without a live Slack webhook.
        </p>
      </div>

      {/* Threshold Slider */}
      <div>
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="font-medium text-ink">
            Negative feedback spike threshold
          </span>
          <span className="font-semibold text-ink tabular-nums">
            {threshold}%
          </span>
        </div>
        <input
          type="range"
          min="10"
          max="80"
          step="5"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
          className="w-full accent-action cursor-pointer"
        />
        <div className="flex justify-between text-muted text-xs mt-1">
          <span>10% (Sensitive)</span>
          <span>30% (Standard)</span>
          <span>80% (Strict)</span>
        </div>
      </div>

      {/* Enable Toggle */}
      <div className="pt-2">
        <label className="flex items-start gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={(e) => setIsEnabled(e.target.checked)}
            className="accent-action w-4 h-4 rounded mt-0.5"
          />
          <div>
            <span className="font-medium text-ink block">
              Enable automated spike sentinel
            </span>
            <span className="text-muted block mt-0.5">
              Automatically dispatches a Slack alert when incoming batches exceed the negative threshold.
            </span>
          </div>
        </label>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-3">
        <button
          type="button"
          onClick={handleSaveConfig}
          disabled={isSavingConfig}
          className="px-3.5 py-1.5 rounded bg-action text-surface font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isSavingConfig ? 'Saving...' : 'Save changes'}
        </button>
        <button
          type="button"
          onClick={handleTestSlack}
          disabled={isTestingSlack}
          className="px-3.5 py-1.5 rounded border border-line bg-surface hover:bg-paper text-ink font-medium transition-colors disabled:opacity-50"
        >
          {isTestingSlack ? 'Sending...' : 'Send test notification'}
        </button>
      </div>

      {/* Test Result Box */}
      {testStatus && (
        <div
          className={`p-3 rounded border text-xs space-y-2 ${
            testStatus.type === 'success'
              ? 'border-positive/30 bg-positive/5 text-positive'
              : 'border-negative/30 bg-negative/5 text-negative'
          }`}
        >
          <p className="font-medium">{testStatus.message}</p>
          {testStatus.is_sandbox && (
            <p className="text-muted">
              Sandbox simulator active. No external Slack call was required.
            </p>
          )}
          {testStatus.payload && (
            <details className="mt-2 text-muted">
              <summary className="cursor-pointer text-action hover:underline">
                View dispatched Slack Block Kit payload
              </summary>
              <pre className="mt-2 p-2.5 rounded bg-surface border border-line text-ink font-mono text-xs max-h-40 overflow-x-auto">
                {JSON.stringify(testStatus.payload, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
