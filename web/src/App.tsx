import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { ProjectView } from './components/ProjectView'
import { Sidebar } from './components/Sidebar'
import { VoicesView } from './components/VoicesView'
import type { ExportState, Line, Project, ProjectSummary, QueueState, ServerEvent, Voice } from './types'

type View = { kind: 'project'; id: string } | { kind: 'voices' } | { kind: 'empty' }

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
        const last = readLast()
        const pick = ps.find((p) => p.id === last) ?? ps[0]
        if (pick) openProject(pick.id)
        else if (vs.length === 0) setView({ kind: 'voices' })
      })
      .catch(fail)
  }, [openProject, fail])

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
      if (ev.type === 'line') {
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

  const onDeleted = async () => {
    setProject(null)
    const ps = await api.projects()
    setProjects(ps)
    if (ps[0]) openProject(ps[0].id)
    else setView({ kind: 'empty' })
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
        onVoices={() => {
          setView({ kind: 'voices' })
          loadVoices()
        }}
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
            onDeleted={onDeleted}
            onGoVoices={() => setView({ kind: 'voices' })}
            notify={notify}
            fail={fail}
          />
        )}
        {view.kind === 'voices' && <VoicesView voices={voices} reload={loadVoices} notify={notify} fail={fail} />}
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
