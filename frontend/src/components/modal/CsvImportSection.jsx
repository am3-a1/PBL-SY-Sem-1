import React, { useState } from 'react'
import { UploadCloud, FileText } from 'lucide-react'
import api from '../../api/client'

export default function CsvImportSection({ onUploadSuccess }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedSource, setSelectedSource] = useState('auto')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadFeedback, setUploadFeedback] = useState(null)
  const [dragOver, setDragOver] = useState(false)

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

  const handleUploadSubmit = async () => {
    if (!selectedFile) return
    setIsUploading(true)
    setUploadFeedback(null)

    try {
      const data = await api.uploadCsv(selectedFile, selectedSource)
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
        message: err.message || 'CSV upload failed',
      })
    } finally {
      setIsUploading(false)
    }
  }

  const downloadSampleCsv = () => {
    const csvContent =
      'source,author,rating,content\n' +
      'Google Play,BobK,5,"Super smooth experience and fast loading."\n' +
      'Apple App Store,AliceB,1,"The app crashes immediately after I enter my password."\n' +
      'Reddit,u/sam_dev,, "Memory consumption skyrockets when loading long charts."\n' +
      'Discord,Zane#0001,, "Subscription renewed but my account shows inactive."\n' +
      'X (Twitter),@tech_user,4,"Great dark mode update, love the clean typography."\n' +
      'CSV / Other,InternalTester,2,"Search returns empty results intermittently."\n'

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'feedpulse_sample_reviews.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="pt-4 border-t border-line space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-ink">CSV file upload</h3>
        <button
          type="button"
          onClick={downloadSampleCsv}
          className="text-action hover:underline inline-flex items-center gap-1"
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Download CSV template</span>
        </button>
      </div>

      {/* Source Selection */}
      <div>
        <label htmlFor="csv-source-select" className="block text-xs font-medium text-ink mb-1.5">
          Assign feedback source
        </label>
        <select
          id="csv-source-select"
          value={selectedSource}
          onChange={(e) => setSelectedSource(e.target.value)}
          className="w-full bg-surface border border-line text-ink rounded px-3 py-1.5 text-xs focus:border-action focus-visible:outline-none cursor-pointer"
        >
          <option value="auto">Auto-detect from CSV (or default to CSV / Other)</option>
          <option value="Google Play">Google Play</option>
          <option value="Apple App Store">Apple App Store</option>
          <option value="Reddit">Reddit</option>
          <option value="Discord">Discord</option>
          <option value="X (Twitter)">X (Twitter)</option>
          <option value="CSV / Other">CSV / Other</option>
        </select>
        <p className="text-muted mt-1 text-[11px]">
          Associate this channel with all imported reviews in the batch.
        </p>
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
          Columns: source, author, rating, content (Max 5 MB, 5,000 rows)
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

      {/* Upload Feedback */}
      {uploadFeedback && (
        <div
          className={`p-3 rounded border ${
            uploadFeedback.type === 'success'
              ? 'border-positive/30 bg-positive/5 text-positive'
              : 'border-negative/30 bg-negative/5 text-negative'
          }`}
        >
          <p className="font-medium">{uploadFeedback.message}</p>
          {uploadFeedback.details?.reasons?.length > 0 && (
            <ul className="mt-1 list-disc list-inside text-xs space-y-0.5 text-muted">
              {uploadFeedback.details.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
          {uploadFeedback.details?.alert_triggered && (
            <p className="mt-1 font-normal text-ink">
              Spike alert notification dispatched to Slack.
            </p>
          )}
          {uploadFeedback.details?.anomaly_detected && (
            <p className="mt-1 font-normal text-negative">
              Time-based anomaly flagged (Z-Score: {uploadFeedback.details.anomaly_details?.z_score}, Theme: {uploadFeedback.details.anomaly_details?.triggering_theme || 'General'}).
            </p>
          )}
        </div>
      )}
    </div>
  )
}
