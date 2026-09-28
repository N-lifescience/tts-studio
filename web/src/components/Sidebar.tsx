import { useState } from 'react'
import type { ProjectSummary, QueueState, Voice } from '../types'

interface Props {
  projects: ProjectSummary[]
  voices: Voice[]
  view: { kind: string; id?: string }
  queue: QueueState | null
  busyProject?: string
  online: boolean
  onOpen: (id: string) => void
  onCreate: (title: string) => Promise<unknown>
  onVoices: () => void
}

export function Sidebar({ projects, voices, view, queue, busyProject, online, onOpen, onCreate, onVoices }: Props) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')

  const submit = async () => {
    if (!title.trim()) return
    await onCreate(title.trim())
    setTitle('')
    setAdding(false)
  }

  const working = queue && (queue.current || queue.pending > 0)

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/favicon.svg" alt="" width={26} height={26} />
        <span>TTS 작업실</span>
      </div>

      <div className="side-section">
        <div className="side-head">에피소드</div>
        <ul className="side-list">
          {projects.map((p) => (
            <li key={p.id}>
              <button
                className={`side-item ${view.kind === 'project' && view.id === p.id ? 'active' : ''}`}
                onClick={() => onOpen(p.id)}
              >
                <span className="side-title">{p.title}</span>
                <span className="side-meta">
                  {busyProject === p.id && <span className="dot live" aria-label="생성 중" />}
                  {p.lines}줄
                </span>
              </button>
            </li>
          ))}
        </ul>
        {adding ? (
          <form
            className="side-new"
            onSubmit={(e) => {
              e.preventDefault()
              submit()
            }}
          >
            <input
              autoFocus
              placeholder="제목 (예: ep02 사마귀)"
              value={title}
              maxLength={100}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setAdding(false)}
            />
            <div className="row gap-s">
              <button className="btn primary sm" type="submit">
                만들기
              </button>
              <button className="btn ghost sm" type="button" onClick={() => setAdding(false)}>
                취소
              </button>
            </div>
          </form>
        ) : (
          <button className="side-add" onClick={() => setAdding(true)}>
            + 새 에피소드
          </button>
        )}
      </div>

      <div className="side-section">
        <div className="side-head">목소리</div>
        <button className={`side-item ${view.kind === 'voices' ? 'active' : ''}`} onClick={onVoices}>
          <span className="side-title">목소리 관리</span>
          <span className="side-meta">{voices.length}개</span>
        </button>
      </div>

      <div className="side-foot">
        {!online ? (
          <span className="bad-text">서버 연결 끊김 — ./studio 가 켜져 있는지 확인</span>
        ) : working ? (
          <span>
            <span className="dot live" /> 생성 중 · 대기 {queue!.pending}줄
          </span>
        ) : (
          <span className="muted">
            {queue?.models.tts === 'ready' ? '모델 준비됨' : queue?.models.tts === 'loading' ? '모델 불러오는 중…' : '대기 중'}
          </span>
        )}
      </div>
    </aside>
  )
}
