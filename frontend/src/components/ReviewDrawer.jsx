import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

export default function ReviewDrawer({
  review,
  allReviews = [],
  isOpen,
  onClose,
  onStatusChange,
  onSelectReview,
}) {
  const drawerRef = useRef(null)
  const closeBtnRef = useRef(null)

  // Close on Escape & trap focus
  useEffect(() => {
    if (!isOpen) return

    // Focus close button on mount
    closeBtnRef.current?.focus()

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }

      if (e.key === 'Tab' && drawerRef.current) {
        const focusableEls = drawerRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusableEls.length === 0) return

        const firstEl = focusableEls[0]
        const lastEl = focusableEls[focusableEls.length - 1]

        if (e.shiftKey) {
          if (document.activeElement === firstEl) {
            e.preventDefault()
            lastEl.focus()
          }
        } else {
          if (document.activeElement === lastEl) {
            e.preventDefault()
            firstEl.focus()
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !review) return null

  // Format date
  const formattedDate = review.created_at
    ? new Date(review.created_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : 'Recent'

  // Other reviews in same theme (up to 5)
  const relatedReviews = allReviews
    .filter((r) => r.category_theme === review.category_theme && r.id !== review.id)
    .slice(0, 5)

  const sentimentTextColor =
    review.sentiment_label === 'Positive'
      ? 'text-positive'
      : review.sentiment_label === 'Negative'
      ? 'text-negative'
      : 'text-neutral'

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Light scrim */}
      <div
        className="fixed inset-0 bg-scrim transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Panel */}
      <aside
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className="relative z-10 w-full sm:max-w-md bg-surface border-l border-line h-full flex flex-col shadow-lg transition-transform duration-150 ease-out"
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h2 id="drawer-title" className="text-sm font-semibold text-ink">
            Review details
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            aria-label="Close review details"
            className="p-1 text-muted hover:text-ink rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
          {/* Review Text */}
          <div>
            <h3 className="text-xs font-medium text-muted mb-2">Review</h3>
            <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">
              {review.content}
            </p>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-line">
            <div>
              <span className="block text-muted mb-1">Author</span>
              <span className="text-ink font-medium">{review.author}</span>
            </div>
            <div>
              <span className="block text-muted mb-1">Channel</span>
              <span className="text-ink font-medium">{review.source}</span>
            </div>
            <div>
              <span className="block text-muted mb-1">Date</span>
              <span className="text-ink font-medium">{formattedDate}</span>
            </div>
            <div>
              <span className="block text-muted mb-1">Rating</span>
              <span className="text-ink font-medium">
                {review.rating ? `${review.rating}/5` : 'Thread'}
              </span>
            </div>
            <div>
              <span className="block text-muted mb-1">Sentiment</span>
              <span className={`font-semibold ${sentimentTextColor}`}>
                {review.sentiment_label}
              </span>
            </div>
            <div>
              <span className="block text-muted mb-1">Theme</span>
              <span className="text-ink font-medium">{review.category_theme}</span>
            </div>
          </div>

          {/* Status Select */}
          <div className="pt-4 border-t border-line">
            <label htmlFor="drawer-status-select" className="block text-xs font-medium text-muted mb-2">
              Status
            </label>
            <select
              id="drawer-status-select"
              value={review.status}
              onChange={(e) => onStatusChange(review.id, e.target.value)}
              className="w-full bg-surface border border-line text-ink rounded px-3 py-2 text-xs focus:border-action focus-visible:outline-none cursor-pointer font-medium"
            >
              <option value="New">New</option>
              <option value="Investigating">Investigating</option>
              <option value="Escalated">Escalated</option>
              <option value="Resolved">Resolved</option>
            </select>
          </div>

          {/* Related reviews in same theme */}
          <div className="pt-4 border-t border-line space-y-3">
            <h3 className="text-xs font-medium text-muted">
              Other reviews in {review.category_theme}
            </h3>
            {relatedReviews.length === 0 ? (
              <p className="text-muted">No other reviews in this theme.</p>
            ) : (
              <div className="space-y-2">
                {relatedReviews.map((rel) => (
                  <button
                    key={rel.id}
                    type="button"
                    onClick={() => onSelectReview(rel)}
                    className="w-full text-left p-2.5 rounded border border-line bg-surface hover:bg-paper transition-colors"
                  >
                    <p className="text-xs text-ink line-clamp-2 mb-1">
                      {rel.content}
                    </p>
                    <div className="text-muted flex items-center gap-3">
                      <span>{rel.source}</span>
                      <span>{rel.rating ? `${rel.rating}/5` : 'Thread'}</span>
                      <span className={
                        rel.sentiment_label === 'Positive'
                          ? 'text-positive font-medium'
                          : rel.sentiment_label === 'Negative'
                          ? 'text-negative font-medium'
                          : 'text-neutral font-medium'
                      }>
                        {rel.sentiment_label}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  )
}
