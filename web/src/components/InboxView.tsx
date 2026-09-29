import { useEffect, useState } from 'react'
import { api } from '../api'
import type { InboxSettings, InboxState } from '../types'

interface Props {
  onOpenProject: (id: string) => void
  onChanged: () => void
  notify: (msg: string, bad?: boolean) => void
  fail: (e: unknown) => void
}

/** 대본 폴더: 구글 드라이브(데스크톱 앱) 폴더에 Word·PDF 를 올리면 알아서 에피소드로. */
export function InboxView({ onOpenProject, onChanged, notify, fail }: Props) {
  const [st, setSt] = useState<InboxState | null>(null)
  const [form, setForm] = useState<InboxSettings | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () =>
    api
      .inbox()
      .then((s) => {
        setSt(s)
        setForm((f) => f ?? s.settings)
      })
      .catch(fail)

  useEffect(() => {
    load()
    const t = window.setInterval(load, 10000)
    return () => window.clearInterval(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!st || !form) return null
  const dirty = JSON.stringify(form) !== JSON.stringify(st.settings)
  const on = !!st.settings.folder

  const save = async (next: InboxSettings) => {
    setBusy(true)
    try {
      const s = await api.putInbox(next)
      setSt(s)
      setForm(s.settings)
      onChanged()
      notify(next.folder ? '대본 폴더를 켰습니다' : '대본 폴더를 껐습니다')
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  const scan = async () => {
    setBusy(true)
    try {
      const s = await api.scanInbox()
      setSt(s)
      notify(s.imported ? `${s.imported}개 불러왔습니다` : '새 파일이 없습니다')
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="voices">
      <header className="project-head">
        <h1 className="title">대본 폴더</h1>
        <span className={`pill ${on ? 'ok-pill' : ''}`}>{on ? '켜짐' : '꺼짐'}</span>
      </header>
      <p className="muted lead">
        이 폴더에 <b>Word(.docx) · PDF · 텍스트</b> 대본을 넣으면 20초 안에 알아서 에피소드가 됩니다. 파일 이름이 제목이 되고, 같은 파일을 고치면
        그 에피소드의 바뀐 줄만 다시 만듭니다. <b>구글 드라이브 데스크톱 앱</b>의 폴더로 정하면, 휴대폰이나 학교 컴퓨터에서 드라이브에 올린 대본이 이
        컴퓨터로 내려와 바로 만들어집니다.
      </p>

      <section className="card">
        <h2>설정</h2>
        <label className="field">
          <span>폴더 (비우면 끔)</span>
          <input
            value={form.folder}
            placeholder="예: …/내 드라이브/TTS 대본"
            onChange={(e) => setForm({ ...form, folder: e.target.value })}
          />
        </label>
        {st.suggestions.length > 0 && form.folder !== st.suggestions[0] && (
          <div className="suggest">
            <span className="muted small">이 컴퓨터에서 찾은 구글 드라이브:</span>
            {st.suggestions.map((s) => (
              <button key={s} className="btn sm" onClick={() => setForm({ ...form, folder: s })} title={s}>
                {s.replace(/^.*?(내 드라이브|My Drive)/, '구글 드라이브 › $1')}
              </button>
            ))}
          </div>
        )}
        {st.suggestions.length === 0 && (
          <p className="muted small">
            구글 드라이브 데스크톱 앱을 찾지 못했습니다. 설치하면(drive.google.com/download) 여기서 바로 고를 수 있습니다. 아무 폴더나 써도 됩니다.
          </p>
        )}
        <label className="check">
          <input type="checkbox" checked={form.auto_generate} onChange={(e) => setForm({ ...form, auto_generate: e.target.checked })} />
          불러오면 바로 음성 만들기
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.auto_export}
            disabled={!form.auto_generate}
            onChange={(e) => setForm({ ...form, auto_export: e.target.checked })}
          />
          다 만들어지면 내보내기까지 (iCloud·문서 폴더로)
        </label>
        <div className="toolbar">
          <button className="btn primary" disabled={!dirty || busy} onClick={() => save(form)}>
            저장
          </button>
          {on && (
            <>
              <button className="btn" disabled={busy} onClick={scan}>
                지금 확인
              </button>
              <button className="btn ghost" onClick={() => api.revealInbox().catch(fail)}>
                폴더 열기
              </button>
              <span className="spacer" />
              <button className="btn ghost danger" disabled={busy} onClick={() => save({ ...form, folder: '' })}>
                끄기
              </button>
            </>
          )}
        </div>
        {st.error && <p className="bad-text small">{st.error}</p>}
      </section>

      <section className="card">
        <h2>최근 불러온 파일</h2>
        {st.recent.length === 0 ? (
          <p className="muted small">
            아직 없습니다.{st.last_scan && ` 마지막 확인 ${st.last_scan.slice(11, 19)}`}
          </p>
        ) : (
          <ul className="files">
            {st.recent.map((r) => (
              <li key={r.file}>
                {r.pid && !r.error ? (
                  <button className="link" onClick={() => onOpenProject(r.pid!)}>
                    {r.title}
                  </button>
                ) : (
                  <span>{r.file}</span>
                )}
                <span className={`small ${r.error ? 'bad-text' : 'muted'}`}>
                  {r.error ? r.error : `${r.created ? '새로 만듦' : '대본 바뀜'} · ${r.lines}줄 · ${r.at.slice(11, 16)}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
