import { useState, type ReactNode } from 'react'
import type { ProjectSummary, QueueState, Voice } from '../types'

interface Props {
  projects: ProjectSummary[]
  voices: Voice[]
  view: { kind: string; id?: string; focus?: string }
  queue: QueueState | null
  busyProject?: string
  online: boolean
  onOpen: (id: string) => void
  onCreate: (title: string) => Promise<unknown>
  onDeleteProject: (p: ProjectSummary) => void
  onOpenVoice: (name?: string) => void
  onDeleteVoice: (name: string) => void
  inboxOn: boolean
  onOpenInbox: () => void
}

const OPEN_KEY = 'tts-studio:sections'

function readOpen(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(OPEN_KEY) || '{}')
  } catch {
    return {}
  }
}

export function Sidebar(props: Props) {
  const { projects, voices, view, queue, busyProject, online } = props
  const [open, setOpen] = useState<Record<string, boolean>>(() => ({ episodes: true, voices: true, ...readOpen() }))
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')

  const toggle = (k: string) =>
    setOpen((o) => {
      const next = { ...o, [k]: !o[k] }
      try {
        localStorage.setItem(OPEN_KEY, JSON.stringify(next))
      } catch {
        /* 저장 안 돼도 괜찮다 */
      }
      return next
    })

  const submit = async () => {
    if (!title.trim()) return
    await props.onCreate(title.trim())
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

      <Section id="episodes" label="에피소드" count={projects.length} open={open.episodes} onToggle={toggle}>
        <ul className="side-list">
          {projects.map((p) => (
            <Row
              key={p.id}
              active={view.kind === 'project' && view.id === p.id}
              onClick={() => props.onOpen(p.id)}
              onDelete={() => props.onDeleteProject(p)}
              deleteLabel={`${p.title} 삭제`}
              meta={
                <>
                  {busyProject === p.id && <span className="dot live" aria-label="생성 중" />}
                  {p.lines}줄
                </>
              }
            >
              {p.title}
            </Row>
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
      </Section>

      <Section id="voices" label="목소리" count={voices.length} open={open.voices} onToggle={toggle}>
        <ul className="side-list">
          {voices.map((v) => (
            <Row
              key={v.name}
              active={view.kind === 'voices' && view.focus === v.name}
              onClick={() => props.onOpenVoice(v.name)}
              onDelete={() => props.onDeleteVoice(v.name)}
              deleteLabel={`목소리 ${v.name} 삭제`}
              meta={<>{v.duration.toFixed(0)}초</>}
            >
              {v.name}
            </Row>
          ))}
        </ul>
        <button
          className={`side-add ${view.kind === 'voices' && !view.focus ? 'on' : ''}`}
          onClick={() => props.onOpenVoice()}
        >
          + 새 목소리 녹음
        </button>
      </Section>

      <section className="side-section">
        <ul className="side-list">
          <li className={`side-row ${view.kind === 'inbox' ? 'active' : ''}`}>
            <button className="side-item" onClick={props.onOpenInbox}>
              <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden>
                <path d="M1.5 4.5a1 1 0 0 1 1-1h3.2l1.3 1.5h6.5a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" strokeWidth="1.3" />
              </svg>
              <span className="side-title">대본 폴더</span>
              <span className="side-meta">
                {props.inboxOn && <span className="dot on" />}
                {props.inboxOn ? '켜짐' : '꺼짐'}
              </span>
            </button>
          </li>
        </ul>
      </section>

      <div className="side-foot">
        {!online ? (
          <span className="bad-text">서버 연결 끊김 — 앱이 켜져 있는지 확인</span>
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

function Section({
  id,
  label,
  count,
  open,
  onToggle,
  children,
}: {
  id: string
  label: string
  count: number
  open: boolean
  onToggle: (id: string) => void
  children: ReactNode
}) {
  return (
    <section className={`side-section ${open ? 'open' : ''}`}>
      <button className="side-head" aria-expanded={open} aria-controls={`sec-${id}`} onClick={() => onToggle(id)}>
        <svg className="chev" viewBox="0 0 12 12" width="12" height="12" aria-hidden>
          <path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {label}
        <span className="side-count">{count}</span>
      </button>
      {open && (
        <div className="side-body" id={`sec-${id}`}>
          {children}
        </div>
      )}
    </section>
  )
}

function Row({
  active,
  onClick,
  onDelete,
  deleteLabel,
  meta,
  children,
}: {
  active: boolean
  onClick: () => void
  onDelete: () => void
  deleteLabel: string
  meta: ReactNode
  children: ReactNode
}) {
  return (
    <li className={`side-row ${active ? 'active' : ''}`}>
      <button className="side-item" onClick={onClick}>
        <span className="side-title">{children}</span>
        <span className="side-meta">{meta}</span>
      </button>
      <button className="side-del" aria-label={deleteLabel} title="삭제" onClick={onDelete}>
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden>
          <path
            d="M6 2h4M2.5 4h11M4 4l.7 9.2a1 1 0 0 0 1 .8h4.6a1 1 0 0 0 1-.8L12 4M6.5 7v4.5M9.5 7v4.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </li>
  )
}
