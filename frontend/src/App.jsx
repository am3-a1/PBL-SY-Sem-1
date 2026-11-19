import React, { useState, useEffect, useMemo } from 'react'
import Header from './components/Header'
import FilterBar from './components/FilterBar'
import AnalyticsOverview from './components/AnalyticsOverview'
import KanbanBoard from './components/KanbanBoard'
import ImportSettingsModal from './components/ImportSettingsModal'
import { X } from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState('analytics') // 'analytics' | 'kanban'
  const [reviews, setReviews] = useState([])
  const [summary, setSummary] = useState(null)
  const [alertConfig, setAlertConfig] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Loading states
  const [isLoading, setIsLoading] = useState(true)
  const [isSeeding, setIsSeeding] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Banner alert notification (e.g., negative spike alert)
  const [spikeAlert, setSpikeAlert] = useState(null)

  // Filters state
  const [filters, setFilters] = useState({
    source: 'All',
    sentiment: 'All',
    theme: 'All',
    search: '',
  })

  // Fetch reviews from backend
  const fetchReviews = async () => {
    try {
      const res = await fetch('/api/reviews?limit=500')
      if (res.ok) {
        const data = await res.json()
        setReviews(data)
      }
    } catch (err) {
      console.error('Failed to fetch reviews:', err)
    }
  }

  // Fetch analytics summary from backend
  const fetchSummary = async () => {
    try {
      const res = await fetch('/api/analytics/summary')
      if (res.ok) {
        const data = await res.json()
        setSummary(data)
      }
    } catch (err) {
      console.error('Failed to fetch summary:', err)
    }
  }

  // Fetch alert configuration
  const fetchAlertConfig = async () => {
    try {
      const res = await fetch('/api/alerts/config')
      if (res.ok) {
        const data = await res.json()
        setAlertConfig(data)
      }
    } catch (err) {
      console.error('Failed to fetch alert config:', err)
    }
  }

  // Initial load
  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true)
      await Promise.all([fetchReviews(), fetchSummary(), fetchAlertConfig()])
      setIsLoading(false)
    }
    initialize()
  }, [])

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true)
    await Promise.all([fetchReviews(), fetchSummary()])
    setIsRefreshing(false)
  }

  // Seed demo data handler
  const handleSeedData = async () => {
    setIsSeeding(true)
    setSpikeAlert(null)
    try {
      const res = await fetch('/api/reviews/seed', { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        await Promise.all([fetchReviews(), fetchSummary()])
        if (data.alert_triggered) {
          const negCount = Math.round((data.negative_percentage / 100) * data.total_seeded)
          setSpikeAlert({
            message: `Spike alert sent to Slack. ${negCount} of ${data.total_seeded} new reviews are negative (${data.negative_percentage}%).`,
          })
        }
      }
    } catch (err) {
      console.error('Seeding failed:', err)
    } finally {
      setIsSeeding(false)
    }
  }

  // Clear all reviews handler
  const handleClearAll = async () => {
    try {
      const res = await fetch('/api/reviews', { method: 'DELETE' })
      if (res.ok) {
        await Promise.all([fetchReviews(), fetchSummary()])
        setSpikeAlert(null)
      }
    } catch (err) {
      console.error('Clear failed:', err)
    }
  }

  // Update status (optimistic UI update + PATCH request)
  const handleStatusChange = async (reviewId, newStatus) => {
    // Optimistic local state update
    setReviews((prev) =>
      prev.map((r) => (r.id === reviewId ? { ...r, status: newStatus } : r))
    )

    try {
      const res = await fetch(`/api/reviews/${reviewId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
      if (!res.ok) {
        // Revert on failure
        await fetchReviews()
      } else {
        fetchSummary()
      }
    } catch (err) {
      console.error('Status update failed:', err)
      await fetchReviews()
    }
  }

  // Filtered reviews (applies to both Kanban board and Analytics)
  const filteredReviews = useMemo(() => {
    return reviews.filter((r) => {
      if (filters.source !== 'All' && r.source !== filters.source) return false
      if (filters.sentiment !== 'All' && r.sentiment_label !== filters.sentiment) return false
      if (filters.theme !== 'All' && r.category_theme !== filters.theme) return false
      if (filters.search) {
        const query = filters.search.toLowerCase()
        const matchContent = r.content.toLowerCase().includes(query)
        const matchAuthor = r.author.toLowerCase().includes(query)
        if (!matchContent && !matchAuthor) return false
      }
      return true
    })
  }, [reviews, filters])

  // Click on theme from Analytics list sets theme filter and switches to Kanban board
  const handleSelectTheme = (theme) => {
    setFilters((prev) => ({ ...prev, theme }))
    setActiveTab('kanban')
  }

  const handleClearFilters = () => {
    setFilters({
      source: 'All',
      sentiment: 'All',
      theme: 'All',
      search: '',
    })
  }

  return (
    <div className="min-h-screen bg-paper text-ink flex flex-col font-sans">
      {/* Header Bar */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenModal={() => setIsModalOpen(true)}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
        totalReviews={reviews.length}
      />

      {/* Negative Spike Notification Banner */}
      {spikeAlert && (
        <div className="border-b border-line bg-surface px-4 py-2 text-xs border-l-4 border-l-negative flex items-center justify-between">
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
            onSelectTheme={handleSelectTheme}
            onClearFilters={handleClearFilters}
            onOpenModal={() => setIsModalOpen(true)}
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
