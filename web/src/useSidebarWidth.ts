import { useCallback, useEffect, useState } from 'react'

export const SIDEBAR_MIN = 240
export const SIDEBAR_DEFAULT = 300
const SIDEBAR_MAX = 480
const WIDTH_KEY = 'tts-studio:sidebar-width'

function clamp(width: number, max = SIDEBAR_MAX) {
  return Math.round(Math.max(SIDEBAR_MIN, Math.min(max, width)))
}

function readWidth() {
  try {
    const saved = localStorage.getItem(WIDTH_KEY)
    const width = saved === null ? SIDEBAR_DEFAULT : Number(saved)
    return Number.isFinite(width) ? clamp(width) : SIDEBAR_DEFAULT
  } catch {
    return SIDEBAR_DEFAULT
  }
}

function availableWidth() {
  return Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, window.innerWidth - 368))
}

export function useSidebarWidth() {
  const [preferredWidth, setPreferredWidth] = useState(readWidth)
  const [maxWidth, setMaxWidth] = useState(availableWidth)

  useEffect(() => {
    const resize = () => setMaxWidth(availableWidth())
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])

  const setWidth = useCallback((value: number) => {
    const next = clamp(value, maxWidth)
    setPreferredWidth(next)
    try {
      localStorage.setItem(WIDTH_KEY, String(next))
    } catch {
      // Resizing still works when browser storage is unavailable.
    }
  }, [maxWidth])

  return { width: clamp(preferredWidth, maxWidth), maxWidth, setWidth }
}
