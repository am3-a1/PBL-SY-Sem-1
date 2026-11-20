import React, { useState, useEffect, useMemo } from 'react'
import { AlertCircle, X, Key } from 'lucide-react'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import AnalyticsOverview from './components/AnalyticsOverview'
import KanbanBoard from './components/KanbanBoard'
import ImportSettingsModal from './components/ImportSettingsModal'
import { api, ApiError } from './api/client'

export default function App() {
  // Navigation & Modal state
  const [activeTab, setActiveTab] = useState('analytics') // 'analytics' | 'kanban'
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalTab, setModalTab] = useState('data') // 'data' | 'slack' | 'key'

  // Data state
  const [reviews, setReviews] = useState([])
  const [summary, setSummary] = useState(null)
  const [alertConfig, setAlertConfig] = useState(null)

  // Loading & Action states
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSeeding, setIsSeeding] = useState(false)
  const [spikeAlert, setSpikeAlert] = useState(null)
  const [appError, setAppError] = useState(null) // { message: string, is401: boolean }

  // Filter state
  const [filters, setFilters] = useState({
    source: 'All',
    sentiment: 'All',
    theme: 'All',
    date: 'All',
    search: '',
  })

  const openModalWithTab = (tab = 'data') => {
    setModalTab(tab)
    setIsModalOpen(true)
  }

  const handleError = (err, fallbackMessage) => {
    console.error(fallbackMessage, err)
    const is401 = err?.status === 401
    const message = is401
      ? 'Authentication required: Your API key is missing or invalid. Please configure your API key to perform this action.'
      : err?.message || fallbackMessage
    setAppError({ message, is401 })
  }

  // Fetch reviews list
  const fetchReviews = async () => {
    try {
      const data = await api.getReviews({ limit: 500 })
      setReviews(Array.isArray(data) ? data : data.items || [])
    } catch (err) {
      console.error('Failed to fetch reviews:', err)
      handleError(err, 'Failed to fetch reviews')
    }
  }

  // Fetch analytics summary
  const fetchSummary = async () => {
    try {
      const data = await api.getAnalyticsSummary()
      setSummary(data)
    } catch (err) {
      console.error('Failed to fetch summary:', err)
      handleError(err, 'Failed to fetch analytics summary')
    }
  }

  // Fetch alert configuration
  const fetchAlertConfig = async () => {
    try {
      const data = await api.getAlertConfig()
      setAlertConfig(data)
    } catch (err) {
      console.error('Failed to fetch alert config:', err)
      handleError(err, 'Failed to fetch alert configuration')
    }
  }

  // Initial load
  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true)
      try {
        await Promise.all([fetchReviews(), fetchSummary(), fetchAlertConfig()])
      } finally {
        setIsLoading(false)
      }
    }
    initialize()
  }, [])

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await Promise.all([fetchReviews(), fetchSummary()])
    } finally {
      setIsRefreshing(false)
    }
  }

  // Seed demo data handler
  const handleSeedData = async () => {
    setIsSeeding(true)
    setSpikeAlert(null)
    setAppError(null)
    try {
      const data = await api.seedReviews()
      await Promise.all([fetchReviews(), fetchSummary()])
      if (data.alert_triggered) {
        const negCount = Math.round((data.negative_percentage / 100) * data.total_seeded)
        setSpikeAlert({
          message: `Spike alert sent to Slack. ${negCount} of ${data.total_seeded} new reviews are negative (${data.negative_percentage}%).`,
        })
      }
    } catch (err) {
      handleError(err, 'Failed to load demo data.')
    } finally {
      setIsSeeding(false)
    }
  }

  // Clear all reviews handler
  const handleClearAll = async () => {
    try {
      await api.clearAllReviews()
      await Promise.all([fetchReviews(), fetchSummary()])
      setSpikeAlert(null)
      setAppError(null)
    } catch (err) {
      handleError(err, 'Failed to clear database.')
    }
  }

  // Update status (optimistic UI update + rollback on failure)
  const handleStatusChange = async (reviewId, newStatus) => {
    const previousReviews = reviews

    // Optimistic local state update
    setReviews((prev) =>
      prev.map((r) => (r.id === reviewId ? { ...r, status: newStatus } : r))
    )

    try {
      await api.updateReviewStatus(reviewId, newStatus)
      fetchSummary()
    } catch (err) {
      // Revert to previous state on failure
      setReviews(previousReviews)
      handleError(err, `Failed to update review status: ${err.message}`)
    }
  }

  // Filtered reviews (applies to both Kanban board and Analytics)
  const filteredReviews = useMemo(() => {
    const normalizeSrc = (src) => {
      if (!src) return 'CSV / Other'
      if (src === 'App Store' || src === 'Apple App Store') return 'Apple App Store'
      if (src === 'Twitter' || src === 'X (Twitter)') return 'X (Twitter)'
      if (src === 'CSV' || src === 'Other' || src === 'CSV / Other') return 'CSV / Other'
      return src
    }

    return reviews.filter((r) => {
      if (filters.source !== 'All' && normalizeSrc(r.source) !== filters.source) return false
      if (filters.sentiment !== 'All' && r.sentiment_label !== filters.sentiment) return false
      if (filters.theme !== 'All' && r.category_theme !== filters.theme) return false
      if (filters.date && filters.date !== 'All') {
        const reviewDate = r.created_at ? r.created_at.slice(0, 10) : 'Recent'
        if (reviewDate !== filters.date) return false
      }
      if (filters.search) {
        const query = filters.search.toLowerCase()
        const matchContent = r.content.toLowerCase().includes(query)
        const matchAuthor = r.author.toLowerCase().includes(query)
        if (!matchContent && !matchAuthor) return false
      }
      return true
    })
  }, [reviews, filters])

  // Click on theme from Analytics list filters in-place without redirecting
  const handleSelectTheme = (theme) => {
    setFilters((prev) => ({
      ...prev,
      theme: prev.theme === theme ? 'All' : theme,
    }))
  }

  // Click on channel from Analytics list filters in-place
  const handleSelectChannel = (channel) => {
    setFilters((prev) => ({
      ...prev,
      source: prev.source === channel ? 'All' : channel,
    }))
  }

  // Click on chart bar from Analytics graph filters by date in-place
  const handleSelectDate = (date) => {
    setFilters((prev) => ({
      ...prev,
      date: prev.date === date ? 'All' : date,
    }))
  }

  const handleClearFilters = () => {
    setFilters({
      source: 'All',
      sentiment: 'All',
      theme: 'All',
      date: 'All',
      search: '',
    })
  }

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col font-sans">
      {/* Header Bar */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenModal={() => openModalWithTab('data')}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
        totalReviews={reviews.length}
      />

      {/* Global Error Banner */}
      {appError && (
        <div
          role="alert"
          className="border-b border-line bg-surface px-4 py-2.5 text-xs border-l-4 border-l-negative flex items-center justify-between text-negative"
        >
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span className="font-medium">{appError.message}</span>
              {appError.is401 && (
                <button
                  type="button"
                  onClick={() => openModalWithTab('key')}
                  className="ml-2 font-semibold underline hover:text-ink flex items-center gap-1 cursor-pointer"
                >
                  <Key className="w-3 h-3" />
                  Configure API Key
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => setAppError(null)}
              aria-label="Dismiss error"
              className="text-muted hover:text-ink p-1 ml-4"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Negative Spike Notification Banner */}
      {spikeAlert && (
        <div
          role="status"
          className="border-b border-line bg-surface px-4 py-2 text-xs border-l-4 border-l-negative flex items-center justify-between"
        >
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between">
            <span className="text-ink">{spikeAlert.message}</span>
            <button
              type="button"
              onClick={() => setSpikeAlert(null)}
              aria-label="Dismiss alert"
              className="text-muted hover:text-ink p-1 ml-4"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Anomaly Detection Banner */}
      {summary?.anomaly_detection?.is_anomaly && (
        <div
          role="status"
          data-testid="anomaly-banner"
          className="border-b border-line bg-negative/10 px-4 py-2.5 text-xs border-l-4 border-l-negative flex items-center justify-between"
        >
          <div className="max-w-7xl mx-auto w-full flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-negative uppercase tracking-wider text-[10px] px-1.5 py-0.5 rounded bg-negative text-surface">
                Anomaly Active
              </span>
              <span className="text-ink font-medium">
                {summary.anomaly_detection.details}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Filter bar for both Analytics and Kanban views */}
        <FilterBar
          filters={filters}
          setFilters={setFilters}
          totalCount={reviews.length}
          filteredCount={filteredReviews.length}
        />

        {/* View Switcher */}
        {activeTab === 'analytics' ? (
          <AnalyticsOverview
            reviews={filteredReviews}
            totalReviewsCount={reviews.length}
            alertConfig={alertConfig}
            summary={summary}
            filters={filters}
            onSelectTheme={handleSelectTheme}
            onSelectChannel={handleSelectChannel}
            onSelectDate={handleSelectDate}
            onClearFilters={handleClearFilters}
            onOpenModal={() => openModalWithTab('data')}
            isLoading={isLoading}
          />
        ) : (
          <KanbanBoard
            reviews={filteredReviews}
            allReviews={reviews}
            onStatusChange={handleStatusChange}
          />
        )}
      </main>

      {/* Import & Alert Settings Modal */}
      <ImportSettingsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        initialTab={modalTab}
        alertConfig={alertConfig}
        onUpdateAlertConfig={(newCfg) => setAlertConfig(newCfg)}
        onSeedData={handleSeedData}
        isSeeding={isSeeding}
        onClearAll={handleClearAll}
        onUploadSuccess={() => {
          fetchReviews()
          fetchSummary()
        }}
      />
    </div>
  )
}
