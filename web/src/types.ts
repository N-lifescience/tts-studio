/** [대본 글자, 들린 글자] — 다른 곳만 */
export type DiffOp = [string, string]

export interface Take {
  id: string
  text: string
  voice: string
  created: string
  duration: number
  attempt: number
  heard: string | null
  distance: number | null
  ok: boolean | null
  diff: DiffOp[] | null
  /** 발음 검사 결과 (받아쓰기 못 했으면 null) */
  pron_ok?: boolean | null
  /** 문장 끝이 자연스럽게 사그라들었는지 (옛 테이크엔 없음) */
  tail_ok?: boolean
  tail_ms?: number
}

export type LineStatus = 'idle' | 'queued' | 'generating' | 'checking' | 'done' | 'error'

export interface Line {
  id: string
  para: number
  text: string
  voice: string | null
  voice_used: string
  speed: number
  gap: number | null
  takes: Take[]
  chosen: string | null
  ignore_check: boolean
  status: LineStatus
  error: string | null
  check: 'none' | 'pending' | 'ok' | 'bad'
}

export interface SubtitleSettings {
  width: number
  height: number
  font_size: number
  position: 'top' | 'middle' | 'bottom'
  margin: number
  color: string
  outline: number
  outline_color: string
  background: string
}

export interface Settings {
  voice: string
  temperature: number
  sentence_gap: number
  para_gap: number
  lufs: number
  subtitle: SubtitleSettings
}

export interface Project {
  id: string
  title: string
  created: string
  updated: string
  settings: Settings
  lines: Line[]
  script: string
}

export interface ProjectSummary {
  id: string
  title: string
  updated: string
  lines: number
}

export interface Voice {
  name: string
  text: string
  duration: number
  updated: string
}

export interface QueueState {
  pending: number
  current: [string, string] | null
  models: { tts: string; asr: string }
}

export interface ExportResult {
  local: string
  icloud: string | null
  duration: number
  files: string[]
}

export type ExportState =
  | { state: 'idle' }
  | { state: 'running'; message: string }
  | { state: 'done'; result: ExportResult }
  | { state: 'error'; message: string }

export type ServerEvent =
  | { type: 'line'; project: string; line: Line }
  | ({ type: 'queue' } & QueueState)
  | { type: 'export'; project: string; state: 'running'; message: string }
  | { type: 'export'; project: string; state: 'done'; result: ExportResult }
  | { type: 'export'; project: string; state: 'error'; message: string }
