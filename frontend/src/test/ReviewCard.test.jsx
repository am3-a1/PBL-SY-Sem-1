import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ReviewCard from '../components/ReviewCard'

describe('ReviewCard Component', () => {
  const mockReview = {
    id: 1,
    source: 'App Store',
    author: 'Elena R',
    rating: 1,
    content: 'Application crashed immediately after I entered my credentials.',
    sentiment_label: 'Negative',
    sentiment_score: -0.75,
    category_theme: 'Login Crash',
    status: 'New',
  }

  it('renders review content, author, rating, and accessible sentiment', () => {
    const onSelect = vi.fn()
    render(<ReviewCard review={mockReview} onSelectReview={onSelect} />)

    expect(screen.getByText(/Application crashed immediately/i)).toBeInTheDocument()
    expect(screen.getByText('App Store')).toBeInTheDocument()
    expect(screen.getByText('1/5')).toBeInTheDocument()
    expect(screen.getByText(/Sentiment: Negative/i)).toBeInTheDocument()
  })

  it('triggers onSelectReview when clicked or activated with Enter key', () => {
    const onSelect = vi.fn()
    render(<ReviewCard review={mockReview} onSelectReview={onSelect} />)

    const card = screen.getByRole('button')
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith(mockReview)

    fireEvent.keyDown(card, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledTimes(2)
  })
})
