import React, { useState } from 'react'
import { X, UploadCloud, FileText } from 'lucide-react'

export default function ImportSettingsModal({
  isOpen,
  onClose,
  alertConfig,
  onUpdateAlertConfig,
  onSeedData,
  isSeeding,
  onClearAll,
  onUploadSuccess,
}) {
  const [activeSubTab, setActiveSubTab] = useState('data') // 'data' | 'slack'
  const [webhookUrl, setWebhookUrl] = useState(alertConfig?.slack_webhook_url || '')
  const [threshold, setThreshold] = useState(alertConfig?.negative_threshold_pct || 30.0)
  const [isEnabled, setIsEnabled] = useState(alertConfig?.is_enabled ?? true)

  // CSV Drag and drop state
  const [selectedFile, setSelectedFile] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadFeedback, setUploadFeedback] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  // Confirmation state for clearing database
  const [confirmClear, setConfirmClear] = useState(false)

  // Slack test status
  const [testStatus, setTestStatus] = useState(null)
  const [isTestingSlack, setIsTestingSlack] = useState(false)
  const [isSavingConfig, setIsSavingConfig] = useState(false)

  if (!isOpen) return null

  // Handle CSV file selection
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
      setUploadFeedback(null)
    }
  }

  const handleDropFile = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0])
      setUploadFeedback(null)
    }
  }

  // Upload CSV to backend
  const handleUploadSubmit = async () => {
    if (!selectedFile) return
    setIsUploading(true)
    setUploadFeedback(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch('/api/reviews/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Upload failed')
      }
      setUploadFeedback({
        type: 'success',
        message: data.message,
        details: data,
      })
      setSelectedFile(null)
      if (onUploadSuccess) onUploadSuccess()
    } catch (err) {
      setUploadFeedback({
        type: 'error',
        message: err.message,
      })
    } finally {
      setIsUploading(false)
    }
  }

  // Save Slack Alert Config
  const handleSaveConfig = async () => {
    setIsSavingConfig(true)
    try {
      const res = await fetch('/api/alerts/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slack_webhook_url: webhookUrl,
          negative_threshold_pct: parseFloat(threshold),
          is_enabled: isEnabled,
        }),
      })
      const data = await res.json()
      if (onUpdateAlertConfig) onUpdateAlertConfig(data)
      setTestStatus({
        type: 'success',
        message: 'Alert configuration saved successfully.',
      })
    } catch (err) {
      setTestStatus({
        type: 'error',
        message: `Failed to save configuration: ${err.message}`,
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
      const res = await fetch('/api/alerts/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          webhook_url: webhookUrl,
          sample_text: 'The app crashes repeatedly on the 2FA login verification code step.',
        }),
      })
      const data = await res.json()
      setTestStatus({
        type: data.status === 'error' ? 'error' : 'success',
        message: data.message,
        payload: data.payload,
        is_sandbox: data.is_sandbox,
      })
    } catch (err) {
      setTestStatus({
        type: 'error',
        message: `Network error calling test endpoint: ${err.message}`,
      })
    } finally {
      setIsTestingSlack(false)
    }
  }

  // Sample CSV template generator
  const downloadSampleCsv = () => {
    const csvContent =
      'source,author,rating,content\n' +
      'App Store,AliceB,1,"The app crashes immediately after I enter my password."\n' +
      'Google Play,BobK,5,"Super smooth experience and fast loading."\n' +
      'Reddit,u/sam_dev,, "Memory consumption skyrockets when loading long charts."\n' +
      'Discord,Zane#0001,, "Subscription renewed but my account shows inactive."\n'

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'feedpulse_sample_reviews.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const handleExecuteClear = async () => {
    await onClearAll()
    setConfirmClear(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-scrim">
      <div className="bg-surface border border-line rounded-md w-full max-w-xl max-h-[90vh] flex flex-col shadow-lg overflow-hidden text-xs">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">
            Import and alerts
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-muted hover:text-ink rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Tabs */}
        <div className="flex border-b border-line px-6 bg-surface">
          <button
            type="button"
            onClick={() => setActiveSubTab('data')}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-colors ${
              activeSubTab === 'data'
                ? 'border-action text-ink font-semibold'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            Data
          </button>
          <button
            type="button"
            onClick={() => setActiveSubTab('slack')}
            className={`py-3 px-3 text-xs font-medium border-b-2 transition-colors ${
              activeSubTab === 'slack'
                ? 'border-action text-ink font-semibold'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            Slack alerts
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {activeSubTab === 'data' ? (
            <div className="space-y-6">
              {/* Section: Demo Data */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-ink">Demo data</h3>
                <p className="text-muted leading-relaxed">
                  Populate the dashboard with 65 sample reviews across Apple App Store, Google Play Store, Reddit, and Discord.
                </p>
                <div>
                  <button
                    type="button"
                    onClick={onSeedData}
                    disabled={isSeeding}
                    className="px-3 py-1.5 rounded bg-surface border border-line text-ink hover:bg-paper font-medium transition-colors disabled:opacity-50"
                  >
                    {isSeeding ? 'Loading demo data...' : 'Load demo data'}
                  </button>
                </div>
              </div>

              {/* Section: CSV Upload Pipeline */}
              <div className="pt-4 border-t border-line space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-ink">
                    CSV file upload
                  </h3>
                  <button
                    type="button"
                    onClick={downloadSampleCsv}
                    className="text-action hover:underline inline-flex items-center gap-1"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Download CSV template</span>
                  </button>
                </div>

                {/* Dropzone */}
                <div
                  onDragOver={(e) => {
                    e.preventDefault()
                    setDragOver(true)
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDropFile}
                  onClick={() => document.getElementById('csvFileInput').click()}
                  className={`border border-dashed rounded p-6 text-center cursor-pointer transition-colors ${
                    dragOver
                      ? 'border-action bg-paper'
                      : 'border-line hover:border-muted bg-paper/50'
                  }`}
                >
                  <input
                    id="csvFileInput"
                    type="file"
                    accept=".csv,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <UploadCloud className="w-6 h-6 text-muted mx-auto mb-2" />
                  <p className="font-medium text-ink">
                    {selectedFile ? selectedFile.name : 'Click to select or drag and drop a CSV file'}
                  </p>
                  <p className="text-muted mt-1">
                    Columns: source, author, rating, content
                  </p>
                </div>

                {selectedFile && (
                  <div className="flex items-center justify-between bg-paper p-3 rounded border border-line">
                    <span className="text-ink font-medium truncate max-w-xs">
                      {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                    </span>
                    <button
                      type="button"
                      onClick={handleUploadSubmit}
                      disabled={isUploading}
                      className="px-3 py-1.5 rounded bg-action text-surface font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      {isUploading ? 'Ingesting...' : 'Process and ingest'}
                    </button>
                  </div>
                )}

                {/* Feedback */}
                {uploadFeedback && (
                  <div
                    className={`p-3 rounded border ${
                      uploadFeedback.type === 'success'
                        ? 'border-positive/30 bg-positive/5 text-positive'
                        : 'border-negative/30 bg-negative/5 text-negative'
                    }`}
                  >
                    <p className="font-medium">{uploadFeedback.message}</p>
                    {uploadFeedback.details?.alert_triggered && (
                      <p className="mt-1 font-normal text-ink">
                        Spike threshold breached ({uploadFeedback.details.negative_percentage}% negative). Spike notification dispatched to Slack.
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Section: Reset Data Store */}
              <div className="pt-4 border-t border-line space-y-2">
                <h3 className="text-xs font-semibold text-ink">Clear database</h3>
                <p className="text-muted">
                  Permanently delete all reviews from the local SQLite database.
                </p>

                {confirmClear ? (
                  <div className="flex items-center gap-3 pt-1">
                    <span className="text-ink font-medium">Are you sure?</span>
                    <button
                      type="button"
                      onClick={handleExecuteClear}
                      className="px-3 py-1.5 rounded bg-negative text-surface font-medium hover:opacity-90 transition-opacity"
                    >
                      Yes, delete all reviews
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmClear(false)}
                      className="px-3 py-1.5 rounded border border-line text-muted hover:text-ink transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div>
                    <button
                      type="button"
                      onClick={() => setConfirmClear(true)}
                      className="px-3 py-1.5 rounded border border-line text-negative hover:bg-paper font-medium transition-colors"
                    >
                      Clear all reviews
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* SubTab 2: Slack Webhook & Spike Alerts */
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
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-line bg-surface flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 rounded border border-line bg-surface hover:bg-paper text-ink font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
