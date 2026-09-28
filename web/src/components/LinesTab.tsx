import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { api, urls, type LinePatch } from '../api'
import { player, usePlayer } from '../player'
import type { DiffOp, Line } from '../types'
import type { ProjectProps } from './ProjectView'

const SPEEDS = [0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15, 1.2]
const GAPS = [0, 0.2, 0.3, 0.5, 0.8, 1, 1.5, 2, 3]
const BUSY = new Set(['queued', 'generating', 'checking'])
const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮'

type Props = ProjectProps & { goScript: () => void; goExport: () => void }

export function LinesTab(props: Props) {
  const { project, fail, notify } = props
  const [preview, setPreview] = useState<{ url: string; cues: [number, number, string][]; ids: string[] } | null>(null)
  const [building, setBuilding] = useState(false)
  const ps = usePlayer()

  const missing = project.lines.filter((l) => !l.chosen).length
  const busy = project.lines.filter((l) => BUSY.has(l.status)).length

  const playAll = async () => {
    if (ps.key === 'preview') return player.stop()
    setBuilding(true)
    try {
      const ids = project.lines.filter((l) => l.chosen).map((l) => l.id)
      const r = await api.preview(project.id)
      if (!ids.length) return notify('아직 만든 줄이 없습니다', true)
      setPreview({ url: r.url, cues: r.cues, ids })
      if (r.missing.length) notify(`아직 없는 줄은 빼고 들려줍니다: ${r.missing.join(', ')}번`)
      player.play('preview', r.url)
    } catch (e) {
      fail(e)
    } finally {
      setBuilding(false)
    }
  }

  // 전체 듣기 중이면 지금 나오는 줄
  const nowLine = useMemo(() => {
    if (ps.key !== 'preview' || !preview) return null
    const i = preview.cues.findIndex(([a, b]) => ps.time >= a && ps.time < b + 0.05)
    return i >= 0 ? preview.ids[i] : null
  }, [ps.key, ps.time, preview])

  if (!project.lines.length) {
    return (
      <div className="empty-tab">
        <p>아직 대본이 없습니다.</p>
        <button className="btn primary" onClick={props.goScript}>
          대본 넣기
        </button>
      </div>
    )
  }

  return (
    <div className="lines-tab">
      <div className="toolbar">
        <button
          className="btn primary"
          disabled={missing === 0 && busy === 0}
          onClick={() => api.generateAll(project.id).then((r) => notify(r.added ? `${r.added}줄 생성 시작` : '만들 줄이 없습니다')).catch(fail)}
        >
          {missing ? `전체 생성 (${missing}줄)` : '모두 생성됨'}
        </button>
        {missing < project.lines.length && (
          <button
            className="btn"
            disabled={busy > 0}
            title="모든 줄을 새로 뽑습니다. 예전 테이크는 테이크 번호로 남아 있어 다시 고를 수 있어요."
            onClick={() => {
              if (!window.confirm(`${project.lines.length}줄을 모두 새로 뽑을까요?\n예전 테이크는 지워지지 않고 테이크 번호로 남습니다.`)) return
              api
                .generateAll(project.id, true)
                .then((r) => notify(`${r.added}줄 다시 뽑기 시작`))
                .catch(fail)
            }}
          >
            ↻ 전체 다시 뽑기
          </button>
        )}
        {busy > 0 && (
          <button className="btn" onClick={() => api.cancel(project.id).then((r) => notify(`${r.cancelled}줄 대기 취소`)).catch(fail)}>
            대기 중지
          </button>
        )}
        <button className="btn" onClick={playAll} disabled={building}>
          {ps.key === 'preview' ? '■ 멈춤' : building ? '준비 중…' : '▶ 전체 듣기'}
        </button>
        {ps.key === 'preview' && (
          <span className="time">
            {fmt(ps.time)} / {fmt(ps.duration)}
          </span>
        )}
        <span className="spacer" />
        {missing === 0 && busy === 0 && (
          <button className="btn ghost" onClick={props.goExport}>
            내보내기 →
          </button>
        )}
      </div>

      <ol className="lines">
        {project.lines.map((l, i) => (
          <Fragment key={l.id}>
            {i > 0 && l.para !== project.lines[i - 1].para && <li className="para-break" aria-hidden />}
            <LineRow {...props} n={i + 1} line={l} now={nowLine === l.id} />
          </Fragment>
        ))}
      </ol>
    </div>
  )
}

function LineRow({
  n,
  line,
  project,
  voices,
  now,
  onLine,
  fail,
}: { n: number; line: Line; now: boolean } & ProjectProps) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(line.text)
  const ps = usePlayer()
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => {
    if (now) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [now])
  const busy = BUSY.has(line.status)
  const chosen = line.takes.find((t) => t.id === line.chosen)
  const def = project.settings

  const patch = async (body: LinePatch, regenerate = false) => {
    try {
      const l = await api.patchLine(project.id, line.id, body)
      onLine(l)
      if (regenerate && !l.chosen) await api.generateLine(project.id, line.id, false)
    } catch (e) {
      fail(e)
    }
  }

  const saveText = () => {
    setEditing(false)
    const t = text.trim()
    if (t && t !== line.text) patch({ text: t }, true)
    else setText(line.text)
  }

  const play = (tid: string) => player.play(`take:${tid}`, urls.take(project.id, tid), line.speed)

  const defaultGap = line.gap === null
  const gapLabel = (g: number) => `${g}초`

  return (
    <li ref={ref} className={`line ${now ? 'now' : ''} ${line.check === 'bad' ? 'is-bad' : ''}`}>
      <div className="line-main">
        <span className="line-no">{n}</span>
        <button
          className="play"
          disabled={!chosen}
          aria-label={`${n}번 줄 듣기`}
          onClick={() => chosen && play(chosen.id)}
        >
          {chosen && ps.key === `take:${chosen.id}` ? '■' : '▶'}
        </button>
        {editing ? (
          <textarea
            className="line-edit"
            autoFocus
            value={text}
            rows={2}
            maxLength={1000}
            onChange={(e) => setText(e.target.value)}
            onBlur={saveText}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                saveText()
              }
              if (e.key === 'Escape') {
                setText(line.text)
                setEditing(false)
              }
            }}
          />
        ) : (
          <p className="line-text" onClick={() => !busy && setEditing(true)} title="눌러서 고치기 (고치면 다시 만듭니다)">
            {line.text}
          </p>
        )}
        <StatusChip line={line} />
      </div>

      {line.check === 'bad' && chosen && !busy && (
        <div className="heard">
          <span className="heard-label">이렇게 들렸어요</span>
          <Diff diff={chosen.diff} heard={chosen.heard} />
          <button className="btn sm" onClick={() => patch({ ignore_check: true })}>
            이대로 쓰기
          </button>
        </div>
      )}
      {line.status === 'error' && <div className="heard bad-text">{line.error}</div>}

      <div className="line-ctrl">
        <label>
          목소리
          <select
            value={line.voice_used}
            disabled={busy}
            onChange={(e) =>
              patch(e.target.value === def.voice ? { reset_voice: true } : { voice: e.target.value }, true)
            }
          >
            {voices.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name === def.voice ? `${v.name} (기본)` : v.name}
              </option>
            ))}
            {!voices.some((v) => v.name === line.voice_used) && <option value={line.voice_used}>{line.voice_used} (없음)</option>}
          </select>
        </label>
        <label>
          속도
          <select value={line.speed} onChange={(e) => patch({ speed: Number(e.target.value) })}>
            {(SPEEDS.includes(line.speed) ? SPEEDS : [...SPEEDS, line.speed].sort((a, b) => a - b)).map((s) => (
              <option key={s} value={s}>
                {s.toFixed(2)}x
              </option>
            ))}
          </select>
        </label>
        <label>
          뒤 쉼
          <select
            value={defaultGap ? 'default' : String(line.gap)}
            onChange={(e) => patch(e.target.value === 'default' ? { reset_gap: true } : { gap: Number(e.target.value) })}
          >
            <option value="default">기본</option>
            {(defaultGap || GAPS.includes(line.gap!) ? GAPS : [...GAPS, line.gap!].sort((a, b) => a - b)).map((g) => (
              <option key={g} value={String(g)}>
                {gapLabel(g)}
              </option>
            ))}
          </select>
        </label>

        {line.takes.length > 0 && (
          <div className="takes" role="group" aria-label="테이크">
            <span className="takes-label">테이크</span>
            {line.takes.map((t, i) => (
              <button
                key={t.id}
                className={`take ${t.id === line.chosen ? 'on' : ''} ${t.ok === false ? 'bad' : t.ok ? 'ok' : ''} ${ps.key === `take:${t.id}` ? 'playing' : ''}`}
                title={`${i + 1}번 테이크 · ${t.duration}초${t.heard ? ` · 들린 말: ${t.heard}` : ''}\n누르면 듣고 이걸로 씁니다`}
                onClick={() => {
                  play(t.id)
                  if (t.id !== line.chosen) patch({ chosen: t.id })
                }}
              >
                {CIRCLED[i] ?? i + 1}
              </button>
            ))}
          </div>
        )}
        <span className="spacer" />
        <button className="btn sm" disabled={busy} onClick={() => api.generateLine(project.id, line.id, true).catch(fail)}>
          ↻ 다시 뽑기
        </button>
      </div>
    </li>
  )
}

function StatusChip({ line }: { line: Line }) {
  const map: Record<string, [string, string]> = {
    queued: ['대기', 'wait'],
    generating: ['생성 중', 'live'],
    checking: ['발음 검사 중', 'live'],
  }
  if (map[line.status]) {
    const [t, c] = map[line.status]
    return <span className={`chip ${c}`}>{t}</span>
  }
  if (line.status === 'error') return <span className="chip bad">오류</span>
  if (line.check === 'ok') return <span className="chip ok">{line.ignore_check ? '확인함' : '발음 OK'}</span>
  if (line.check === 'bad') return <span className="chip bad">발음 확인</span>
  if (line.check === 'pending') return <span className="chip">검사 안 됨</span>
  return <span className="chip muted">아직 없음</span>
}

function Diff({ diff, heard }: { diff: DiffOp[] | null; heard: string | null }) {
  return (
    <>
      <span className="diff">“{heard}”</span>
      {diff?.map(([want, got], i) => (
        <span key={i} className="diff-pair" title="대본 → 들린 말">
          <span className="d-want">{want || '∅'}</span> → <span className="d-got">{got || '∅'}</span>
        </span>
      ))}
    </>
  )
}

function fmt(s: number) {
  if (!isFinite(s)) return '0:00'
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}
