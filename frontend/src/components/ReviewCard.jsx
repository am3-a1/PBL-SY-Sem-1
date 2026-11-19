import React, { useRef } from 'react'

export default function ReviewCard({ review, onSelectReview }) {
  const isDraggingRef = useRef(false)

  const handleDragStart = (e) => {
    isDraggingRef.current = true
    e.dataTransfer.setData(
      'text/plain',
      JSON.stringify({ reviewId: review.id, currentStatus: review.status })
    )
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragEnd = () => {
    setTimeout(() => {
      isDraggingRef.current = false
    }, 100)
  }

  const handleClick = () => {
    if (isDraggingRef.current) return
    onSelectReview(review)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelectReview(review)
    }
  }

  const formattedDate = review.created_at
    ? new Date(review.created_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      })
    : 'Recent'

  const sentimentEdgeClass =
    review.sentiment_label === 'Positive'
      ? 'border-l-positive'
      : review.sentiment_label === 'Negative'
      ? 'border-l-negative'
      : 'border-l-neutral'

  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      aria-label={`Review by ${review.author}: ${review.content.slice(0, 50)}...`}
      className={`group bg-surface border border-line ${sentimentEdgeClass} border-l-[3px] rounded-md p-3 transition-colors hover:border-muted cursor-pointer select-none focus-visible:outline-none`}
    >
      {/* Hidden sentiment text for screen readers */}
      <span className="sr-only">Sentiment: {review.sentiment_label}</span>

      {/* Review text clamped to 4 lines */}
      <p className="text-xs text-ink leading-relaxed line-clamp-4">
        {review.content}
      </p>

      {/* Meta line: channel, rating, date */}
      <div className="mt-2.5 text-xs text-muted flex items-center gap-3">
        <span>{review.source}</span>
        <span>{review.rating ? `${review.rating}/5` : 'Thread'}</span>
        <span>{formattedDate}</span>
      </div>
    </div>
  )
}
