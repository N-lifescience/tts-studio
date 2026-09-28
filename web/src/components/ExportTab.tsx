import { useEffect, useState } from 'react'
import { api, urls } from '../api'
import type { ProjectProps } from './ProjectView'

export function ExportTab({ project, exportState, fail, goLines }: ProjectProps & { goLines: () => void }) {
  const [info, setInfo] = useState<{ exists: boolean; folder: string; local?: string; icloud?: string | null; files?: string[] } | null>(null)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    api.exportInfo(project.id).then(setInfo).catch(fail)
  }, [project.id, fail, exportState.state])

  const missing = project.lines.filter((l) => !l.chosen).length
  const bad = project.lines.filter((l) => l.check === 'bad').length
  const running = exportState.state === 'running' || starting

  const start = async () => {
    setStarting(true)
    try {
      await api.export(project.id)
    } catch (e) {
      fail(e)
    } finally {
      setStarting(false)
    }
  }

  const files = info?.files ?? []
  const lineFiles = files.filter((f) => f.startsWith('lines/'))
  const mainFiles = files.filter((f) => !f.startsWith('lines/'))
  const icloud = exportState.state === 'done' ? exportState.result.icloud : info?.icloud

  return (
    <div className="export-tab">
      <section className="card">
        <h2>iCloud Drive 로 내보내기</h2>
        <p className="muted">
          아이패드 <b>파일 앱 → iCloud Drive → TTS → {info?.folder ?? project.title}</b> 에 자동으로 나타납니다. 루마퓨전에서 바로 불러오세요.
        </p>
        {missing > 0 ? (
          <p className="warn-text">
            아직 안 만든 줄이 {missing}개 있습니다.{' '}
            <button className="link" onClick={goLines}>
              줄 목록으로
            </button>
          </p>
        ) : bad > 0 ? (
          <p className="warn-text">발음 확인이 필요한 줄이 {bad}개 있습니다. 그대로 내보낼 수는 있습니다.</p>
        ) : null}
        <div className="toolbar">
          <button className="btn primary" disabled={missing > 0 || running} onClick={start}>
            {running ? '내보내는 중…' : '내보내기'}
          </button>
          {exportState.state === 'running' && <span className="muted">{exportState.message}</span>}
          {exportState.state === 'error' && <span className="bad-text">{exportState.message}</span>}
          {exportState.state === 'done' && <span className="ok-text">완료 · {exportState.result.duration.toFixed(1)}초</span>}
        </div>
      </section>

      {info?.exists && (
        <section className="card">
          <h2>내보낸 파일</h2>
          <div className="toolbar">
            {icloud && (
              <button className="btn sm" onClick={() => api.reveal(project.id, 'icloud').catch(fail)}>
                iCloud 폴더 열기
              </button>
            )}
            <button className="btn sm ghost" onClick={() => api.reveal(project.id, 'local').catch(fail)}>
              SSD 사본 열기
            </button>
          </div>
          <ul className="files">
            {mainFiles.map((f) => (
              <li key={f}>
                <a href={urls.exportFile(project.id, f)} download>
                  {f}
                </a>
                <span className="muted small">{DESC[f] ?? ''}</span>
              </li>
            ))}
            {lineFiles.length > 0 && (
              <li>
                <details>
                  <summary>
                    lines/ <span className="muted small">줄별 조각 {lineFiles.length}개 · 파일 이름 = 시작 시각</span>
                  </summary>
                  <ul className="files inner">
                    {lineFiles.map((f) => (
                      <li key={f}>
                        <a href={urls.exportFile(project.id, f)} download>
                          {f.slice(6)}
                        </a>
                      </li>
                    ))}
                  </ul>
                </details>
              </li>
            )}
          </ul>
        </section>
      )}

      <section className="card how">
        <h2>루마퓨전에서 쓰는 법</h2>
        <ol>
          <li>
            <b>narration.wav</b> 를 타임라인 맨 앞(0초)에 오디오로 놓습니다.
          </li>
          <li>
            <b>subtitles_green.mp4</b> 를 영상 위 트랙 0초에 놓고, 클립 편집 → 효과 → <b>크로마 키</b>(초록)를 겁니다. 소리는 없습니다.
          </li>
          <li>
            줄마다 위치를 옮기고 싶으면 <b>lines/</b> 조각을 쓰세요. 파일 이름 앞의 <code>00m07.4s</code> 가 원래 시작 시각입니다.
          </li>
          <li>
            유튜브에 올릴 때 <b>narration.srt</b> 를 자막(CC)으로 올리면 됩니다. 영상에 자막을 박았다면 생략.
          </li>
        </ol>
        <p className="muted small">루마퓨전은 타임라인 파일(XML)·SRT 불러오기를 지원하지 않아 이렇게 파일로 넘깁니다.</p>
      </section>
    </div>
  )
}

const DESC: Record<string, string> = {
  'narration.wav': '전체 나레이션 · 48kHz · 유튜브 음량',
  'narration.srt': '유튜브 자막(CC)',
  'subtitles_green.mp4': '초록 배경 자막 영상 · 크로마키용',
}
