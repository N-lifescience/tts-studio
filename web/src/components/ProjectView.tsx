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
  onDeleted: () => void
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

  const tabs: [Tab, string][] = [
    ['lines', `줄 ${project.lines.length}`],
    ['script', '대본'],
    ['settings', '설정·자막'],
    ['export', '내보내기'],
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
        <div className="head-stats">
          <span>
            {made}/{project.lines.length}줄 완성
          </span>
          {bad > 0 && <span className="pill bad">발음 확인 {bad}</span>}
        </div>
      </header>

      <nav className="tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'on' : ''}`} onClick={() => setTab(k)}>
            {label}
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
