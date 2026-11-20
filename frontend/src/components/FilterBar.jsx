import React from 'react'
import { Search, X } from 'lucide-react'

export default function FilterBar({
  filters,
  setFilters,
  totalCount,
  filteredCount,
}) {
  const hasActiveFilters =
    filters.source !== 'All' ||
    filters.sentiment !== 'All' ||
    filters.theme !== 'All' ||
    (filters.date && filters.date !== 'All') ||
    filters.search !== ''

  const handleReset = () => {
    setFilters({
      source: 'All',
      sentiment: 'All',
      theme: 'All',
      date: 'All',
      search: '',
    })
  }

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 mb-6">
      {/* Filters group */}
      <div className="flex flex-wrap items-center gap-3 flex-1">
        {/* Search Input */}
        <div className="relative min-w-[220px] max-w-xs flex-1">
          <Search className="w-4 h-4 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search reviews..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full bg-surface border border-line text-ink placeholder-muted rounded pl-8 pr-7 py-1.5 text-xs transition-colors focus:border-action focus-visible:outline-none"
          />
          {filters.search && (
            <button
              type="button"
              onClick={() => setFilters({ ...filters, search: '' })}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-ink p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Source / Channel Filter */}
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <span>Channel</span>
          <select
            value={filters.source}
            onChange={(e) => setFilters({ ...filters, source: e.target.value })}
            aria-label="Channel"
            className="bg-surface border border-line text-ink rounded px-2 py-1.5 text-xs focus:border-action focus-visible:outline-none cursor-pointer"
          >
            <option value="All">All Sources</option>
            <option value="Google Play">Google Play</option>
            <option value="Apple App Store">Apple App Store</option>
            <option value="Reddit">Reddit</option>
            <option value="Discord">Discord</option>
            <option value="X (Twitter)">X (Twitter)</option>
            <option value="CSV / Other">CSV / Other</option>
          </select>
        </label>

        {/* Sentiment Filter */}
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <span>Sentiment</span>
          <select
            value={filters.sentiment}
            onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}
            aria-label="Sentiment"
            className="bg-surface border border-line text-ink rounded px-2 py-1.5 text-xs focus:border-action focus-visible:outline-none cursor-pointer"
          >
            <option value="All">All</option>
            <option value="Positive">Positive</option>
            <option value="Neutral">Neutral</option>
            <option value="Negative">Negative</option>
          </select>
        </label>

        {/* Theme Filter */}
        <label className="flex items-center gap-1.5 text-xs text-muted">
          <span>Theme</span>
          <select
            value={filters.theme}
            onChange={(e) => setFilters({ ...filters, theme: e.target.value })}
            aria-label="Theme"
            className="bg-surface border border-line text-ink rounded px-2 py-1.5 text-xs focus:border-action focus-visible:outline-none cursor-pointer"
          >
            <option value="All">All</option>
            <option value="Login Crash">Login Crash</option>
            <option value="Billing & Payments">Billing & Payments</option>
            <option value="Performance & Lag">Performance & Lag</option>
            <option value="UI/UX">UI/UX</option>
            <option value="General">General</option>
          </select>
        </label>

        {/* Theme Filter Removable Chip */}
        {filters.theme !== 'All' && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-surface border border-line rounded text-xs text-ink">
            <span>Theme: {filters.theme}</span>
            <button
              type="button"
              onClick={() => setFilters({ ...filters, theme: 'All' })}
              aria-label={`Remove theme filter ${filters.theme}`}
              className="text-muted hover:text-ink ml-0.5 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        )}

        {/* Date Filter Removable Chip */}
        {filters.date && filters.date !== 'All' && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-surface border border-line rounded text-xs text-ink">
            <span>Date: {filters.date}</span>
            <button
              type="button"
              onClick={() => setFilters({ ...filters, date: 'All' })}
              aria-label={`Remove date filter ${filters.date}`}
              className="text-muted hover:text-ink ml-0.5 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        )}

        {/* Reset All Filters Button */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={handleReset}
            className="text-action hover:underline text-xs font-medium ml-1"
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Review Count Summary */}
      <div className="text-xs text-muted whitespace-nowrap">
        Showing {filteredCount} of {totalCount} reviews
      </div>
    </div>
  )
}
