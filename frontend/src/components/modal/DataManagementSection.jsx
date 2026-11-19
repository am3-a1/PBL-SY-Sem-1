import React, { useState } from 'react'

export default function DataManagementSection({
  onSeedData,
  isSeeding,
  onClearAll,
}) {
  const [confirmClear, setConfirmClear] = useState(false)
  const [isClearing, setIsClearing] = useState(false)

  const handleExecuteClear = async () => {
    setIsClearing(true)
    try {
      await onClearAll()
      setConfirmClear(false)
    } finally {
      setIsClearing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Section: Demo Data */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-ink">Demo data</h3>
        <p className="text-muted leading-relaxed">
          Populate the dashboard with 65 realistic sample reviews across Apple App Store, Google Play Store, Reddit, and Discord.
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
              disabled={isClearing}
              className="px-3 py-1.5 rounded bg-negative text-surface font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {isClearing ? 'Deleting...' : 'Yes, delete all reviews'}
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
  )
}
