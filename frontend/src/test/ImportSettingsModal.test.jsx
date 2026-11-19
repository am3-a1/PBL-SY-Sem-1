import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ImportSettingsModal from '../components/ImportSettingsModal'
import { getApiKey } from '../api/client'

describe('ImportSettingsModal Component', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  const mockAlertConfig = {
    id: 1,
    slack_webhook_url: 'https://hooks.slack.com/services/T1***/B2***/******',
    has_slack_webhook: true,
    negative_threshold_pct: 30.0,
    is_enabled: true,
  }

  it('renders modal when isOpen is true and closes on Escape key', () => {
    const onClose = vi.fn()
    render(
      <ImportSettingsModal
        isOpen={true}
        onClose={onClose}
        alertConfig={mockAlertConfig}
      />
    )

    expect(screen.getByText('Settings & Integrations')).toBeInTheDocument()
    expect(screen.getByText('Demo data')).toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('switches to Slack alerts tab and displays threshold', () => {
    render(
      <ImportSettingsModal
        isOpen={true}
        onClose={vi.fn()}
        alertConfig={mockAlertConfig}
      />
    )

    const slackTab = screen.getByRole('button', { name: /Slack alerts/i })
    fireEvent.click(slackTab)

    expect(screen.getByText(/Negative feedback spike threshold/i)).toBeInTheDocument()
    expect(screen.getByText('30%')).toBeInTheDocument()
    expect(screen.getByText(/Active webhook configured/i)).toBeInTheDocument()
  })

  it('switches to API Key tab and allows configuring and clearing a key', () => {
    render(
      <ImportSettingsModal
        isOpen={true}
        onClose={vi.fn()}
        alertConfig={mockAlertConfig}
      />
    )

    const keyTab = screen.getByRole('button', { name: /API Key/i })
    fireEvent.click(keyTab)

    expect(screen.getByText(/API Key Configuration/i)).toBeInTheDocument()
    expect(screen.getByText('Not configured')).toBeInTheDocument()

    // Enter and save a key
    const input = screen.getByPlaceholderText(/Enter your FEEDPULSE_API_KEY/i)
    fireEvent.change(input, { target: { value: 'my-new-secret-token-123' } })

    const saveBtn = screen.getByRole('button', { name: /Save API Key/i })
    fireEvent.click(saveBtn)

    expect(getApiKey()).toBe('my-new-secret-token-123')
    expect(screen.getByText('Configured')).toBeInTheDocument()

    // Clear key
    const clearBtn = screen.getByRole('button', { name: /Clear key/i })
    fireEvent.click(clearBtn)
    expect(getApiKey()).toBe('')
    expect(screen.getByText('Not configured')).toBeInTheDocument()
  })

  it('requires confirmation before clearing database', async () => {
    const onClearAll = vi.fn().mockResolvedValue({})
    render(
      <ImportSettingsModal
        isOpen={true}
        onClose={vi.fn()}
        alertConfig={mockAlertConfig}
        onClearAll={onClearAll}
      />
    )

    const clearBtn = screen.getByRole('button', { name: /Clear all reviews/i })
    fireEvent.click(clearBtn)

    expect(screen.getByText(/Are you sure\?/i)).toBeInTheDocument()
    const confirmBtn = screen.getByRole('button', { name: /Yes, delete all reviews/i })

    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(onClearAll).toHaveBeenCalled()
  })
})
