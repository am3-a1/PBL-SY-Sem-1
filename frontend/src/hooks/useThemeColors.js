import { useState, useEffect } from 'react'

const TOKEN_NAMES = [
  'paper',
  'surface',
  'ink',
  'muted',
  'line',
  'negative',
  'neutral',
  'positive',
  'action',
  'track',
]

const LIGHT_COLORS = {
  paper: '#F5F6F8',
  surface: '#FFFFFF',
  ink: '#1B232B',
  muted: '#5B6670',
  line: '#DDE1E6',
  negative: '#C23B2A',
  neutral: '#8C96A0',
  positive: '#2F7A63',
  action: '#2A46C9',
  track: 'rgba(27,35,43,0.10)',
}

const DARK_COLORS = {
  paper: '#12161B',
  surface: '#1A2027',
  ink: '#E8ECEF',
  muted: '#9AA5B0',
  line: '#2B333B',
  negative: '#E0624F',
  neutral: '#8C96A0',
  positive: '#4CAF8E',
  action: '#7C93FF',
  track: 'rgba(232,236,239,0.12)',
}

function getComputedThemeColors() {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return LIGHT_COLORS
  }

  try {
    const isDark = document.documentElement.dataset.theme === 'dark'
    const fallback = isDark ? DARK_COLORS : LIGHT_COLORS
    const styles = getComputedStyle(document.documentElement)
    const colors = {}
    for (const name of TOKEN_NAMES) {
      const val = styles.getPropertyValue(`--${name}`).trim()
      colors[name] = val || fallback[name]
    }
    return colors
  } catch (e) {
    return LIGHT_COLORS
  }
}

export function useThemeColors() {
  // Safe defaults for first render, updated in effect
  const [colors, setColors] = useState(() => {
    try {
      const isDark =
        typeof document !== 'undefined' &&
        document.documentElement?.dataset?.theme === 'dark'
      return isDark ? DARK_COLORS : LIGHT_COLORS
    } catch (e) {
      return LIGHT_COLORS
    }
  })

  useEffect(() => {
    const updateColors = () => {
      setColors(getComputedThemeColors())
    }

    // Observe theme attribute changes on <html>
    let observer = null
    try {
      observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          if (
            mutation.type === 'attributes' &&
            (mutation.attributeName === 'data-theme' || mutation.attributeName === 'class')
          ) {
            updateColors()
          }
        }
      })

      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme', 'class'],
      })
    } catch (e) {}

    // Listen to OS preference changes
    let mediaQuery = null
    try {
      mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      mediaQuery.addEventListener('change', updateColors)
    } catch (e) {}

    // Synchronize once on mount
    updateColors()

    return () => {
      if (observer) observer.disconnect()
      if (mediaQuery) mediaQuery.removeEventListener('change', updateColors)
    }
  }, [])

  return colors
}

export default useThemeColors
