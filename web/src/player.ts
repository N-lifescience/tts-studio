import { useEffect, useRef, useState, useSyncExternalStore } from 'react'

// 화면 전체에서 소리는 한 번에 하나만 난다. 무엇이 재생 중인지(key)를 모두가 볼 수 있게 한다.
type State = { key: string | null; time: number; duration: number }

let state: State = { key: null, time: 0, duration: 0 }
const listeners = new Set<() => void>()
const audio = new Audio()
audio.preload = 'auto'

function set(next: Partial<State>) {
  state = { ...state, ...next }
  listeners.forEach((l) => l())
}

audio.addEventListener('timeupdate', () => set({ time: audio.currentTime }))
audio.addEventListener('loadedmetadata', () => set({ duration: audio.duration }))
audio.addEventListener('ended', () => set({ key: null, time: 0 }))
audio.addEventListener('error', () => set({ key: null }))

export const player = {
  play(key: string, url: string, rate = 1) {
    if (state.key === key && !audio.paused) {
      audio.pause()
      set({ key: null })
      return
    }
    audio.src = url
    audio.playbackRate = rate
    audio.preservesPitch = true
    set({ key, time: 0, duration: 0 })
    audio.play().catch(() => set({ key: null }))
  },
  stop() {
    audio.pause()
    set({ key: null, time: 0 })
  },
  seek(t: number) {
    audio.currentTime = t
  },
}

export function usePlayer() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    () => state,
  )
}

/** 30초까지 마이크 녹음. */
export function useRecorder(maxSec = 30) {
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const rec = useRef<MediaRecorder | null>(null)
  const timer = useRef<number | null>(null)

  const stop = () => {
    if (rec.current && rec.current.state !== 'inactive') rec.current.stop()
    if (timer.current) window.clearInterval(timer.current)
    setRecording(false)
  }

  const start = async () => {
    setError(null)
    setBlob(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      })
      const r = new MediaRecorder(stream)
      const chunks: Blob[] = []
      r.ondataavailable = (e) => chunks.push(e.data)
      r.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        setBlob(new Blob(chunks, { type: r.mimeType }))
      }
      rec.current = r
      r.start()
      const t0 = Date.now()
      setElapsed(0)
      setRecording(true)
      timer.current = window.setInterval(() => {
        const s = (Date.now() - t0) / 1000
        setElapsed(s)
        if (s >= maxSec) stop()
      }, 100)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => () => stop(), [])

  return { recording, elapsed, blob, error, start, stop, clear: () => setBlob(null) }
}
