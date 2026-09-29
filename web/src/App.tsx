import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { InboxView } from './components/InboxView'
import { ProjectView } from './components/ProjectView'
import { Sidebar } from './components/Sidebar'
import { VoicesView } from './components/VoicesView'
import type { ExportState, Line, Project, ProjectSummary, QueueState, ServerEvent, Voice } from './types'

type View = { kind: 'project'; id: string } | { kind: 'voices'; focus?: string } | { kind: 'inbox' } | { kind: 'empty' }

const LAST = 'tts-studio:last'

function readLast(): string | null {
  try {
    return localStorage.getItem(LAST)
  } catch {
    return null
  }
}

function writeLast(id: string) {
  try {
    localStorage.setItem(LAST, id)
  } catch {
    /* 저장 안 돼도 괜찮다 */
  }
}

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [voices, setVoices] = useState<Voice[]>([])
  const [view, setView] = useState<View>({ kind: 'empty' })
  const [project, setProject] = useState<Project | null>(null)
  const [queue, setQueue] = useState<QueueState | null>(null)
  const [exports, setExports] = useState<Record<string, ExportState>>({})
  const [toast, setToast] = useState<{ msg: string; bad?: boolean } | null>(null)
  const [online, setOnline] = useState(true)
  const [inboxOn, setInboxOn] = useState(false)
  const viewRef = useRef(view)
  useEffect(() => {
    viewRef.current = view
  }, [view])

  const notify = useCallback((msg: string, bad = false) => {
    setToast({ msg, bad })
    window.setTimeout(() => setToast((t) => (t?.msg === msg ? null : t)), bad ? 6000 : 3000)
  }, [])

  const fail = useCallback((e: unknown) => notify(e instanceof Error ? e.message : String(e), true), [notify])

  const loadProjects = useCallback(() => api.projects().then(setProjects).catch(fail), [fail])
  const loadVoices = useCallback(() => api.voices().then(setVoices).catch(fail), [fail])
  const loadInbox = useCallback(() => api.inbox().then((s) => setInboxOn(!!s.settings.folder)).catch(() => {}), [])

  const openProject = useCallback(
    (id: string) => {
      setView({ kind: 'project', id })
      writeLast(id)
      api
        .project(id)
        .then(setProject)
        .catch((e) => {
          setProject(null)
          setView({ kind: 'empty' })
          fail(e)
        })
    },
    [fail],
  )

  // 처음 켤 때
  useEffect(() => {
    Promise.all([api.projects(), api.voices(), api.status()])
      .then(([ps, vs, st]) => {
        setProjects(ps)
        setVoices(vs)
        setQueue(st)
        loadInbox()
        const last = readLast()
        const pick = ps.find((p) => p.id === last) ?? ps[0]
        if (pick) openProject(pick.id)
        else if (vs.length === 0) setView({ kind: 'voices' })
      })
      .catch(fail)
  }, [openProject, fail, loadInbox])

  // 서버에서 오는 진행 상황
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onopen = () => {
      setOnline(true)
      const v = viewRef.current
      if (v.kind === 'project') api.project(v.id).then(setProject).catch(() => {})
      api.status().then(setQueue).catch(() => {})
    }
    es.onerror = () => setOnline(false)
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as ServerEvent
      if (ev.type === 'projects') {
        api.projects().then(setProjects).catch(() => {})
      } else if (ev.type === 'line') {
        setProject((p) => (p && p.id === ev.project ? replaceLine(p, ev.line) : p))
      } else if (ev.type === 'queue') {
        setQueue({ pending: ev.pending, current: ev.current, models: ev.models })
      } else if (ev.type === 'export') {
        setExports((x) => ({
          ...x,
          [ev.project]:
            ev.state === 'done'
              ? { state: 'done', result: ev.result }
              : ev.state === 'running'
                ? { state: 'running', message: ev.message }
                : { state: 'error', message: ev.message },
        }))
      }
    }
    return () => es.close()
  }, [])

  const onLine = useCallback((line: Line) => setProject((p) => (p ? replaceLine(p, line) : p)), [])

  const createProject = async (title: string) => {
    try {
      const p = await api.createProject(title)
      await loadProjects()
      setProject(p)
      setView({ kind: 'project', id: p.id })
      writeLast(p.id)
      return p
    } catch (e) {
      fail(e)
      return null
    }
  }

  const deleteProject = async (p: ProjectSummary) => {
    if (!window.confirm(`"${p.title}" 에피소드를 지울까요?\n만든 음성도 모두 지워집니다. (iCloud 로 내보낸 파일은 남습니다)`)) return
    try {
      await api.deleteProject(p.id)
      const ps = await api.projects()
      setProjects(ps)
      notify(`에피소드 "${p.title}" 삭제됨`)
      if (view.kind === 'project' && view.id === p.id) {
        setProject(null)
        if (ps[0]) openProject(ps[0].id)
        else setView({ kind: 'empty' })
      }
    } catch (e) {
      fail(e)
    }
  }

  const deleteVoice = async (name: string) => {
    if (!window.confirm(`"${name}" 목소리를 지울까요?`)) return
    try {
      await api.deleteVoice(name)
      await loadVoices()
      notify(`목소리 "${name}" 삭제됨`)
      if (view.kind === 'voices' && view.focus === name) setView({ kind: 'voices' })
    } catch (e) {
      fail(e) // 쓰는 에피소드가 있으면 서버가 이유를 알려 준다
    }
  }

  const openVoice = (name?: string) => {
    setView({ kind: 'voices', focus: name })
    loadVoices()
  }

  const busyProject = queue?.current?.[0]

  return (
    <div className="app">
      <Sidebar
        projects={projects}
        voices={voices}
        view={view}
        queue={queue}
        busyProject={busyProject}
        online={online}
        onOpen={openProject}
        onCreate={createProject}
        onDeleteProject={deleteProject}
        onOpenVoice={openVoice}
        onDeleteVoice={deleteVoice}
        inboxOn={inboxOn}
        onOpenInbox={() => setView({ kind: 'inbox' })}
      />
      <main className="main">
        {view.kind === 'project' && project && project.id === view.id && (
          <ProjectView
            key={project.id}
            project={project}
            voices={voices}
            queue={queue}
            exportState={exports[project.id] ?? { state: 'idle' }}
            setProject={(p) => {
              setProject(p)
              loadProjects()
            }}
            onLine={onLine}
            onGoVoices={() => openVoice()}
            notify={notify}
            fail={fail}
          />
        )}
        {view.kind === 'voices' && (
          <VoicesView
            voices={voices}
            focus={view.focus}
            reload={loadVoices}
            onDelete={deleteVoice}
            notify={notify}
            fail={fail}
          />
        )}
        {view.kind === 'inbox' && (
          <InboxView
            onOpenProject={openProject}
            onChanged={loadInbox}
            notify={notify}
            fail={fail}
          />
        )}
        {view.kind === 'empty' && (
          <div className="empty">
            <h1>TTS 작업실</h1>
            <p>왼쪽에서 에피소드를 만들거나 고르세요.</p>
          </div>
        )}
      </main>
      {toast && (
        <div className={`toast ${toast.bad ? 'bad' : ''}`} role="status">
          {toast.msg}
        </div>
      )}
    </div>
  )
}

function replaceLine(p: Project, line: Line): Project {
  return { ...p, lines: p.lines.map((l) => (l.id === line.id ? line : l)) }
}
