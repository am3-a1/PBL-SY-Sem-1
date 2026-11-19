import React, { useState } from 'react'
import ReviewCard from './ReviewCard'
import ReviewDrawer from './ReviewDrawer'

const COLUMNS = [
  { id: 'New', title: 'New' },
  { id: 'Investigating', title: 'Investigating' },
  { id: 'Escalated', title: 'Escalated' },
  { id: 'Resolved', title: 'Resolved' },
]

export default function KanbanBoard({ reviews, allReviews = [], onStatusChange }) {
  const [dragOverCol, setDragOverCol] = useState(null)
  const [selectedReview, setSelectedReview] = useState(null)

  const handleDragOver = (e, columnId) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (dragOverCol !== columnId) {
      setDragOverCol(columnId)
    }
  }

  const handleDragLeave = (e, columnId) => {
    if (e.currentTarget.contains(e.relatedTarget)) return
    if (dragOverCol === columnId) {
      setDragOverCol(null)
    }
  }

  const handleDrop = (e, columnId) => {
    e.preventDefault()
    setDragOverCol(null)
    try {
      const raw = e.dataTransfer.getData('text/plain')
      if (!raw) return
      const { reviewId, currentStatus } = JSON.parse(raw)
      if (reviewId && currentStatus !== columnId) {
        onStatusChange(reviewId, columnId)
        if (selectedReview && selectedReview.id === reviewId) {
          setSelectedReview((prev) => (prev ? { ...prev, status: columnId } : null))
        }
      }
    } catch (err) {
      console.error('Failed to parse dropped review', err)
    }
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-line pb-12">
        {COLUMNS.map((col) => {
          const colReviews = reviews.filter((r) => r.status === col.id)
          const isTarget = dragOverCol === col.id

          return (
            <div
              key={col.id}
              onDragOver={(e) => handleDragOver(e, col.id)}
              onDragLeave={(e) => handleDragLeave(e, col.id)}
              onDrop={(e) => handleDrop(e, col.id)}
              className={`flex flex-col py-4 md:py-0 px-0 md:px-4 first:pl-0 last:pr-0 border-t-2 transition-colors ${
                isTarget ? 'border-t-action bg-surface' : 'border-t-transparent'
              }`}
            >
              {/* Column Header: Plain title and count */}
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-line">
                <h2 className="text-sm font-semibold text-ink">{col.title}</h2>
                <span className="text-xs text-muted tabular-nums">
                  {colReviews.length}
                </span>
              </div>

              {/* Column Cards (Page scrolls as one) */}
              <div className="flex-1 space-y-3">
                {colReviews.length === 0 ? (
                  <p className="text-xs text-muted py-6">
                    Nothing here. Drag a review in.
                  </p>
                ) : (
                  colReviews.map((review) => (
                    <ReviewCard
                      key={review.id}
                      review={review}
                      onSelectReview={(r) => setSelectedReview(r)}
                    />
                  ))
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Review Details Drawer */}
      <ReviewDrawer
        isOpen={Boolean(selectedReview)}
        review={selectedReview}
        allReviews={allReviews.length > 0 ? allReviews : reviews}
        onClose={() => setSelectedReview(null)}
        onStatusChange={(id, newStatus) => {
          onStatusChange(id, newStatus)
          setSelectedReview((prev) => (prev && prev.id === id ? { ...prev, status: newStatus } : prev))
        }}
        onSelectReview={(r) => setSelectedReview(r)}
      />
    </>
  )
}
