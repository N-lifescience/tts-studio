import { useRef, useState } from 'react'
import { SIDEBAR_DEFAULT, SIDEBAR_MIN } from '../useSidebarWidth'

interface Props {
  width: number
  maxWidth: number
  onChange: (width: number) => void
}

export function SidebarResize({ width, maxWidth, onChange }: Props) {
  const drag = useRef<{ id: number; x: number; width: number } | null>(null)
  const [dragging, setDragging] = useState(false)

  const stop = () => {
    drag.current = null
    setDragging(false)
  }

  return (
    <div
      className={`sidebar-resize ${dragging ? 'dragging' : ''}`}
      role="separator"
      tabIndex={0}
      aria-label="사이드바 너비 조절"
      aria-controls="studio-sidebar"
      aria-orientation="vertical"
      aria-valuemin={SIDEBAR_MIN}
      aria-valuemax={maxWidth}
      aria-valuenow={width}
      title="드래그하거나 방향키로 너비를 조절하세요. 두 번 누르면 기본 너비로 돌아갑니다."
      onPointerDown={(e) => {
        if (e.button !== 0 || !e.isPrimary) return
        e.preventDefault()
        e.currentTarget.focus()
        drag.current = { id: e.pointerId, x: e.clientX, width }
        e.currentTarget.setPointerCapture(e.pointerId)
        setDragging(true)
      }}
      onPointerMove={(e) => {
        const start = drag.current
        if (start && start.id === e.pointerId) onChange(start.width + e.clientX - start.x)
      }}
      onPointerUp={stop}
      onPointerCancel={stop}
      onLostPointerCapture={stop}
      onDoubleClick={() => onChange(SIDEBAR_DEFAULT)}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 48 : 16
        if (e.key === 'ArrowLeft') onChange(width - step)
        else if (e.key === 'ArrowRight') onChange(width + step)
        else if (e.key === 'Home') onChange(SIDEBAR_MIN)
        else if (e.key === 'End') onChange(maxWidth)
        else if (e.key === 'Escape' && drag.current) {
          onChange(drag.current.width)
          stop()
        } else return
        e.preventDefault()
      }}
    />
  )
}
