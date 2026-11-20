import React from 'react'
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilterBar from '../components/FilterBar'
import CsvImportSection from '../components/modal/CsvImportSection'
import SlackConfigSection from '../components/modal/SlackConfigSection'
import AnalyticsOverview from '../components/AnalyticsOverview'

beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

describe('Phase 1 Frontend Components', () => {
  it('renders all Phase 1 source options in FilterBar', () => {
    const setFilters = vi.fn()
    const filters = {
      source: 'All',
      sentiment: 'All',
      theme: 'All',
      date: 'All',
      search: '',
    }
    render(
      <FilterBar
        filters={filters}
        setFilters={setFilters}
        totalCount={10}
        filteredCount={10}
      />
    )

    const channelSelect = screen.getByLabelText(/Channel/i)
    expect(channelSelect).toBeInTheDocument()

    const options = Array.from(channelSelect.querySelectorAll('option')).map((o) => o.value)
    expect(options).toEqual([
      'All',
      'Google Play',
      'Apple App Store',
      'Reddit',
      'Discord',
      'X (Twitter)',
      'CSV / Other',
    ])

    fireEvent.change(channelSelect, { target: { value: 'Reddit' } })
    expect(setFilters).toHaveBeenCalledWith(expect.objectContaining({ source: 'Reddit' }))
  })

  it('renders source dropdown in CsvImportSection with auto and all sources', () => {
    render(<CsvImportSection onUploadSuccess={vi.fn()} />)

    const sourceSelect = screen.getByLabelText(/Assign feedback source/i)
    expect(sourceSelect).toBeInTheDocument()
    expect(sourceSelect.value).toBe('auto')

    const options = Array.from(sourceSelect.querySelectorAll('option')).map((o) => o.value)
    expect(options).toContain('auto')
    expect(options).toContain('Google Play')
    expect(options).toContain('Apple App Store')
    expect(options).toContain('Reddit')
    expect(options).toContain('Discord')
    expect(options).toContain('X (Twitter)')
    expect(options).toContain('CSV / Other')

    fireEvent.change(sourceSelect, { target: { value: 'Apple App Store' } })
    expect(sourceSelect.value).toBe('Apple App Store')
  })

  it('renders Z-Score anomaly threshold slider in SlackConfigSection and responds to changes', () => {
    const alertConfig = {
      slack_webhook_url: 'https://hooks.slack.com/services/T00/B00/X00',
      negative_threshold_pct: 35.0,
      z_score_threshold: 2.8,
      is_enabled: true,
      has_slack_webhook: true,
    }

    render(
      <SlackConfigSection
        alertConfig={alertConfig}
        onUpdateAlertConfig={vi.fn()}
      />
    )

    const slider = screen.getByLabelText(/Time-based anomaly Z-score threshold/i)
    expect(slider).toBeInTheDocument()
    expect(slider.value).toBe('2.8')

    expect(screen.getByText(/Z ≥ 2.8/i)).toBeInTheDocument()

    fireEvent.change(slider, { target: { value: '3.2' } })
    expect(slider.value).toBe('3.2')
    expect(screen.getByText(/Z ≥ 3.2/i)).toBeInTheDocument()
  })

  it('renders Anomaly Sentinel status card in AnalyticsOverview when anomaly is present', () => {
    const summary = {
      total_reviews: 15,
      channels: {
        'Google Play': { total: 5, negative: 1 },
        'Apple App Store': { total: 10, negative: 8 },
      },
      anomaly_detection: {
        is_anomaly: true,
        z_score: 3.45,
        threshold: 2.5,
        current_window_count: 8,
        historical_mean: 1.2,
        historical_std: 0.8,
        theme: 'Login Crash',
        representative_review: 'App crashes immediately on startup after update.',
        window_start: '2026-03-30T10:00:00Z',
        window_end: '2026-03-30T11:00:00Z',
        details: 'Negative review spike detected: 8 negative reviews (baseline mean: 1.20, std: 0.80, Z: 3.45 >= 2.50).',
        status: 'anomaly_detected',
      },
    }

    const reviews = [
      {
        id: 1,
        content: 'App crashes immediately on startup after update.',
        rating: 1,
        sentiment_label: 'Negative',
        category_theme: 'Login Crash',
        source: 'Apple App Store',
        status: 'New',
        created_at: '2026-03-30T10:15:00Z',
      },
    ]

    render(
      <AnalyticsOverview
        reviews={reviews}
        totalReviewsCount={1}
        summary={summary}
        onSelectTheme={vi.fn()}
        onClearFilters={vi.fn()}
        onOpenModal={vi.fn()}
      />
    )

    expect(screen.getByTestId('anomaly-sentinel-card')).toBeInTheDocument()
    expect(screen.getByText(/Anomaly Detected/i)).toBeInTheDocument()
    expect(screen.getAllByText(/3.45/i).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/App crashes immediately on startup after update/i)).toBeInTheDocument()
  })

  it('triggers onSelectChannel when clicking a channel row in AnalyticsOverview', () => {
    const onSelectChannel = vi.fn()
    const reviews = [
      {
        id: 1,
        content: 'Works great',
        rating: 5,
        sentiment_label: 'Positive',
        category_theme: 'General',
        source: 'Google Play',
        status: 'New',
        created_at: '2026-03-30T10:15:00Z',
      },
    ]

    render(
      <AnalyticsOverview
        reviews={reviews}
        totalReviewsCount={1}
        onSelectChannel={onSelectChannel}
        onSelectTheme={vi.fn()}
        onClearFilters={vi.fn()}
        onOpenModal={vi.fn()}
      />
    )

    const googlePlayRow = screen.getByText('Google Play')
    fireEvent.click(googlePlayRow)
    expect(onSelectChannel).toHaveBeenCalledWith('Google Play')
  })

  it('triggers onSelectTheme when clicking a theme in AnalyticsOverview', () => {
    const onSelectTheme = vi.fn()
    const reviews = [
      {
        id: 1,
        content: 'Cannot login',
        rating: 1,
        sentiment_label: 'Negative',
        category_theme: 'Login Crash',
        source: 'Google Play',
        status: 'New',
        created_at: '2026-03-30T10:15:00Z',
      },
    ]

    render(
      <AnalyticsOverview
        reviews={reviews}
        totalReviewsCount={1}
        onSelectTheme={onSelectTheme}
        onClearFilters={vi.fn()}
        onOpenModal={vi.fn()}
      />
    )

    const loginCrashThemeBtn = screen.getByRole('button', { name: /Login Crash/i })
    fireEvent.click(loginCrashThemeBtn)
    expect(onSelectTheme).toHaveBeenCalledWith('Login Crash')
  })

  it('renders and clears date filter chip in FilterBar', () => {
    const setFilters = vi.fn()
    const filters = {
      source: 'All',
      sentiment: 'All',
      theme: 'All',
      date: '2026-03-30',
      search: '',
    }

    render(
      <FilterBar
        filters={filters}
        setFilters={setFilters}
        totalCount={50}
        filteredCount={10}
      />
    )

    expect(screen.getByText(/Date: 2026-03-30/i)).toBeInTheDocument()

    const removeBtn = screen.getByLabelText(/Remove date filter 2026-03-30/i)
    fireEvent.click(removeBtn)
    expect(setFilters).toHaveBeenCalledWith(expect.objectContaining({ date: 'All' }))
  })
})
