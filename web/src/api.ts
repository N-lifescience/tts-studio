import type { Line, Project, ProjectSummary, QueueState, Settings, Voice } from './types'

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method }
  if (body instanceof FormData) init.body = body
  else if (body !== undefined) {
    init.body = JSON.stringify(body)
    init.headers = { 'Content-Type': 'application/json' }
  }
  const r = await fetch(url, init)
  if (!r.ok) {
    let msg = `${r.status}`
    try {
      const j = await r.json()
      msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
    } catch {
      /* 본문 없음 */
    }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

const P = (id: string) => `/api/projects/${encodeURIComponent(id)}`

export interface LinePatch {
  text?: string
  voice?: string
  reset_voice?: boolean
  speed?: number
  gap?: number
  reset_gap?: boolean
  chosen?: string
  ignore_check?: boolean
}

export const api = {
  status: () => req<QueueState & { export_root: string; icloud: boolean; peak_memory_gb: number | null }>('GET', '/api/status'),
  projects: () => req<ProjectSummary[]>('GET', '/api/projects'),
  createProject: (title: string, script = '') => req<Project>('POST', '/api/projects', { title, script }),
  project: (id: string) => req<Project>('GET', P(id)),
  patchProject: (id: string, body: { title?: string; settings?: Partial<Settings> }) => req<Project>('PATCH', P(id), body),
  deleteProject: (id: string) => req<{ ok: boolean }>('DELETE', P(id)),
  putScript: (id: string, script: string) => req<Project>('PUT', `${P(id)}/script`, { script }),
  patchLine: (id: string, lid: string, body: LinePatch) => req<Line>('PATCH', `${P(id)}/lines/${lid}`, body),
  generateLine: (id: string, lid: string, manual = true) =>
    req<QueueState>('POST', `${P(id)}/lines/${lid}/generate?manual=${manual}`),
  generateAll: (id: string, redo = false) =>
    req<QueueState & { added: number }>('POST', `${P(id)}/generate${redo ? '?redo=true' : ''}`),
  cancel: (id: string) => req<{ cancelled: number }>('POST', `${P(id)}/cancel`),
  preview: (id: string) =>
    req<{ duration: number; missing: number[]; cues: [number, number, string][]; url: string }>('POST', `${P(id)}/preview`),
  export: (id: string) => req<{ started: boolean }>('POST', `${P(id)}/export`),
  exportInfo: (id: string) =>
    req<{ exists: boolean; folder: string; local?: string; icloud?: string | null; files?: string[] }>('GET', `${P(id)}/export`),
  reveal: (id: string, where: 'icloud' | 'local') => req<{ ok: boolean }>('POST', `${P(id)}/reveal?where=${where}`),
  voices: () => req<Voice[]>('GET', '/api/voices'),
  addVoice: (name: string, file: Blob, filename: string, overwrite = false) => {
    const fd = new FormData()
    fd.append('name', name)
    fd.append('overwrite', String(overwrite))
    fd.append('file', file, filename)
    return req<{ name: string; text: string; duration: number }>('POST', '/api/voices', fd)
  },
  patchVoice: (name: string, text: string) => req<{ name: string; text: string }>('PATCH', `/api/voices/${encodeURIComponent(name)}`, { text }),
  deleteVoice: (name: string) => req<{ ok: boolean }>('DELETE', `/api/voices/${encodeURIComponent(name)}`),
}

export const urls = {
  take: (pid: string, tid: string) => `${P(pid)}/takes/${tid}`,
  voice: (name: string, v = '') => `/api/voices/${encodeURIComponent(name)}/audio?v=${encodeURIComponent(v)}`,
  exportFile: (pid: string, path: string) => `${P(pid)}/export/file?path=${encodeURIComponent(path)}`,
  subtitlePreview: (pid: string, text: string, v: string) =>
    `${P(pid)}/subtitle-preview.png?text=${encodeURIComponent(text)}&v=${encodeURIComponent(v)}`,
}
