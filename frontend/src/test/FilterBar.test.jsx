import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilterBar from '../components/FilterBar'

describe('FilterBar Component', () => {
  const defaultFilters = {
    source: 'All',
    sentiment: 'All',
    theme: 'All',
    search: '',
  }

  it('renders filter controls and review count', () => {
    const setFilters = vi.fn()
    render(
      <FilterBar
        filters={defaultFilters}
        setFilters={setFilters}
        totalCount={50}
        filteredCount={35}
      />
    )

    expect(screen.getByText(/Showing 35 of 50 reviews/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Channel/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Sentiment/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Theme/i)).toBeInTheDocument()
  })

  it('triggers setFilters when source dropdown changes', () => {
    const setFilters = vi.fn()
    render(
      <FilterBar
        filters={defaultFilters}
        setFilters={setFilters}
        totalCount={10}
        filteredCount={10}
      />
    )

    const channelSelect = screen.getByLabelText(/Channel/i)
    fireEvent.change(channelSelect, { target: { value: 'Google Play' } })

    expect(setFilters).toHaveBeenCalled()
  })

  it('updates search query on user input', () => {
    const setFilters = vi.fn()
    render(
      <FilterBar
        filters={defaultFilters}
        setFilters={setFilters}
        totalCount={10}
        filteredCount={10}
      />
    )

    const searchInput = screen.getByPlaceholderText(/Search reviews.../i)
    fireEvent.change(searchInput, { target: { value: 'crash' } })

    expect(setFilters).toHaveBeenCalled()
  })
})
