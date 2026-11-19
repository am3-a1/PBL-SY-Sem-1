import React, { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import DataManagementSection from './modal/DataManagementSection'
import CsvImportSection from './modal/CsvImportSection'
import SlackConfigSection from './modal/SlackConfigSection'

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

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-scrim"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-surface border border-line rounded-md w-full max-w-xl max-h-[90vh] flex flex-col shadow-lg overflow-hidden text-xs">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <h2 id="modal-title" className="text-sm font-semibold text-ink">
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
              <DataManagementSection
                onSeedData={onSeedData}
                isSeeding={isSeeding}
                onClearAll={onClearAll}
              />
              <CsvImportSection onUploadSuccess={onUploadSuccess} />
            </div>
          ) : (
            <SlackConfigSection
              alertConfig={alertConfig}
              onUpdateAlertConfig={onUpdateAlertConfig}
            />
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
