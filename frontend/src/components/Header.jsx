import React from 'react'
import { RefreshCw } from 'lucide-react'
import ThemeToggle from './ThemeToggle'

export default function Header({
  activeTab,
  setActiveTab,
  onOpenModal,
  onRefresh,
  isRefreshing,
  totalReviews,
}) {
  return (
    <header className="border-b border-line bg-surface sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Brand & Tabs */}
          <div className="flex items-center gap-8 h-full">
            <span className="font-semibold text-base text-ink tracking-tight">
              FeedPulse
            </span>

            <nav className="flex items-center gap-6 h-full" aria-label="Main navigation">
              <button
                type="button"
                onClick={() => setActiveTab('analytics')}
                className={`h-full flex items-center px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'analytics'
                    ? 'border-action text-ink font-semibold'
                    : 'border-transparent text-muted hover:text-ink'
                }`}
              >
                Analytics
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('kanban')}
                className={`h-full flex items-center px-1 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'kanban'
                    ? 'border-action text-ink font-semibold'
                    : 'border-transparent text-muted hover:text-ink'
                }`}
              >
                <span>Triage board</span>
                {totalReviews > 0 && (
                  <span className="ml-1.5 text-muted text-xs font-normal">
                    {totalReviews}
                  </span>
                )}
              </button>
            </nav>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <ThemeToggle />

            <button
              type="button"
              onClick={onRefresh}
              disabled={isRefreshing}
              aria-label="Refresh data"
              title="Refresh data"
              className="p-1.5 text-muted hover:text-ink rounded border border-line bg-surface hover:bg-paper transition-colors duration-150 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>

            <button
              type="button"
              onClick={onOpenModal}
              className="px-3 py-1.5 text-sm font-medium text-ink bg-surface hover:bg-paper border border-line rounded transition-colors"
            >
              Import and alerts
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
