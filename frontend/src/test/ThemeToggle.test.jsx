import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ThemeToggle from '../components/ThemeToggle'

describe('ThemeToggle Component', () => {
  it('renders theme toggle button with accessible label', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label')
    expect(button.getAttribute('aria-label')).toMatch(/theme/i)
  })

  it('cycles theme when clicked', () => {
    render(<ThemeToggle />)
    const button = screen.getByRole('button')
    const initialLabel = button.getAttribute('aria-label')

    fireEvent.click(button)
    const nextLabel = button.getAttribute('aria-label')
    expect(nextLabel).not.toBe(initialLabel)
  })
})
