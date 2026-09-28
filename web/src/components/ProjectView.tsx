import { useState } from 'react'
import { api } from '../api'
import type { ExportState, Line, Project, QueueState, Voice } from '../types'
import { ExportTab } from './ExportTab'
import { LinesTab } from './LinesTab'
import { ScriptTab } from './ScriptTab'
import { SettingsTab } from './SettingsTab'

export interface ProjectProps {
  project: Project
  voices: Voice[]
  queue: QueueState | null
  exportState: ExportState
  setProject: (p: Project) => void
  onLine: (l: Line) => void
  onGoVoices: () => void
  notify: (msg: string, bad?: boolean) => void
  fail: (e: unknown) => void
}

type Tab = 'lines' | 'script' | 'settings' | 'export'

export function ProjectView(props: ProjectProps) {
  const { project, setProject, fail } = props
  const [tab, setTab] = useState<Tab>(project.lines.length ? 'lines' : 'script')
  const [editingTitle, setEditingTitle] = useState(false)
  const [title, setTitle] = useState(project.title)

  const saveTitle = async () => {
    setEditingTitle(false)
    if (title.trim() && title.trim() !== project.title) {
      try {
        setProject(await api.patchProject(project.id, { title: title.trim() }))
      } catch (e) {
        fail(e)
      }
    } else setTitle(project.title)
  }

  const made = project.lines.filter((l) => l.chosen).length
  const bad = project.lines.filter((l) => l.check === 'bad').length

  // 작업 순서대로: 목소리·자막을 정하고 → 대본을 넣고 → 줄마다 듣고 다듬고 → 내보낸다
  const tabs: [Tab, string, string][] = [
    ['settings', '목소리·자막', ''],
    ['script', '대본', ''],
    ['lines', '음성 다듬기', project.lines.length ? `${made}/${project.lines.length}` : ''],
    ['export', '내보내기', ''],
  ]

  return (
    <div className="project">
      <header className="project-head">
        {editingTitle ? (
          <input
            className="title-input"
            autoFocus
            value={title}
            maxLength={100}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing) saveTitle()
              if (e.key === 'Escape') {
                setTitle(project.title)
                setEditingTitle(false)
              }
            }}
          />
        ) : (
          <h1 className="title" onClick={() => setEditingTitle(true)} title="눌러서 제목 바꾸기">
            {project.title}
          </h1>
        )}
        {bad > 0 && (
          <button className="pill bad" onClick={() => setTab('lines')}>
            발음 확인 {bad}줄
          </button>
        )}
      </header>

      <nav className="tabs" role="tablist">
        {tabs.map(([k, label, badge], i) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>
            <span className="tab-no">{i + 1}</span>
            {label}
            {badge && <span className="tab-badge">{badge}</span>}
          </button>
        ))}
      </nav>

      <div className="tab-body">
        {tab === 'lines' && <LinesTab {...props} goScript={() => setTab('script')} goExport={() => setTab('export')} />}
        {tab === 'script' && <ScriptTab {...props} goLines={() => setTab('lines')} />}
        {tab === 'settings' && <SettingsTab {...props} />}
        {tab === 'export' && <ExportTab {...props} goLines={() => setTab('lines')} />}
      </div>
    </div>
  )
}
