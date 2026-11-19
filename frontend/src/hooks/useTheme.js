import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'feedpulse-theme'

function getInitialPreference() {
  if (typeof window === 'undefined') return 'system'
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
  } catch (e) {
    // Ignore localStorage access failures
  }
  return 'system'
}

function getSystemTheme() {
  if (typeof window === 'undefined') return 'light'
  try {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch (e) {
    return 'light'
  }
}

export function useTheme() {
  const [preference, setPreference] = useState(getInitialPreference)
  const [resolvedTheme, setResolvedTheme] = useState(() => {
    try {
      if (typeof document !== 'undefined' && document.documentElement?.dataset?.theme) {
        return document.documentElement.dataset.theme
      }
      const pref = getInitialPreference()
      return pref === 'system' ? getSystemTheme() : pref
    } catch (e) {
      return 'light'
    }
  })

  // Synchronize document.documentElement.dataset.theme on preference or system changes
  useEffect(() => {
    const currentTheme = preference === 'system' ? getSystemTheme() : preference
    setResolvedTheme(currentTheme)
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = currentTheme
    }
  }, [preference])

  // Real-time listener for system OS theme changes when in system mode
  useEffect(() => {
    if (preference !== 'system') return

    try {
      const mql = window.matchMedia('(prefers-color-scheme: dark)')
      const handleChange = (e) => {
        const newTheme = e.matches ? 'dark' : 'light'
        setResolvedTheme(newTheme)
        if (typeof document !== 'undefined') {
          document.documentElement.dataset.theme = newTheme
        }
      }

      mql.addEventListener('change', handleChange)
      return () => mql.removeEventListener('change', handleChange)
    } catch (e) {
      // Ignore
    }
  }, [preference])

  // Explicit toggle between light and dark
  const toggleTheme = useCallback(() => {
    const nextTheme = resolvedTheme === 'dark' ? 'light' : 'dark'
    setPreference(nextTheme)
    setResolvedTheme(nextTheme)
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = nextTheme
    }
    try {
      localStorage.setItem(STORAGE_KEY, nextTheme)
    } catch (e) {
      // Ignore
    }
  }, [resolvedTheme])

  const setTheme = useCallback((theme) => {
    setPreference(theme)
    const effective = theme === 'system' ? getSystemTheme() : theme
    setResolvedTheme(effective)
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = effective
    }
    try {
      if (theme === 'system') {
        localStorage.removeItem(STORAGE_KEY)
      } else {
        localStorage.setItem(STORAGE_KEY, theme)
      }
    } catch (e) {
      // Ignore
    }
  }, [])

  return {
    theme: preference,
    resolvedTheme,
    toggleTheme,
    setTheme,
  }
}

export default useTheme
