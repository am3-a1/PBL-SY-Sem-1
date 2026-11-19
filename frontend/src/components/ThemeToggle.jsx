import React from 'react'
import { Sun, Moon } from 'lucide-react'
import useTheme from '../hooks/useTheme'

export default function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme()

  const isDark = resolvedTheme === 'dark'
  const label = isDark ? 'Switch to light theme' : 'Switch to dark theme'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className="p-1.5 text-muted hover:text-ink rounded border border-line bg-surface hover:bg-paper transition-colors duration-150"
    >
      {isDark ? (
        <Sun className="w-4 h-4" />
      ) : (
        <Moon className="w-4 h-4" />
      )}
    </button>
  )
}
