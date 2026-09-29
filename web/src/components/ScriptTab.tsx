import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ProjectProps } from './ProjectView'

export function ScriptTab({ project, setProject, fail, notify, goLines }: ProjectProps & { goLines: () => void }) {
  const [text, setText] = useState(project.script)
  const [saving, setSaving] = useState(false)

  // 줄 목록에서 글자를 고쳤을 수 있으니 열 때 최신 대본을 받아 온다
  useEffect(() => {
    api.project(project.id).then((p) => setText(p.script)).catch(fail)
  }, [project.id, fail])

  const dirty = text.trim() !== project.script.trim()

  const apply = async (andGenerate: boolean) => {
    setSaving(true)
    try {
      const p = await api.putScript(project.id, text)
      setProject(p)
      setText(p.script)
      if (andGenerate) {
        const r = await api.generateAll(project.id)
        notify(r.added ? `${r.added}줄 생성 시작 (바뀌지 않은 줄은 그대로 둡니다)` : '바뀐 줄이 없습니다')
      }
      goLines()
    } catch (e) {
      fail(e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="script-tab">
      <div className="hint">
        <b>줄바꿈</b>과 <b>문장 끝(. ? !)</b>마다 따로 만들고 짧게 쉽니다. <b>빈 줄</b>은 문단 구분이라 길게 쉽니다.
        숫자·영어는 소리 나는 대로 한글로 쓰는 게 가장 정확합니다 (LoL → 롤).
      </div>
      <div className="toolbar">
        <label className="btn file-btn">
          파일에서 불러오기
          <input
            type="file"
            accept=".docx,.pdf,.txt,.md"
            onChange={async (e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (!f) return
              if (text.trim() && !window.confirm('지금 대본 칸을 파일 내용으로 바꿀까요? (적용하기 전까지는 저장되지 않습니다)')) return
              try {
                const r = await api.parseFile(f)
                setText(r.text)
                notify(`"${f.name}" 에서 ${r.lines}줄을 불러왔습니다. 확인하고 적용하세요.`)
              } catch (err) {
                fail(err)
              }
            }}
          />
        </label>
        <span className="muted small">Word(.docx) · PDF · 텍스트. 빈 줄은 문단 구분으로 들어옵니다.</span>
      </div>
      <textarea
        className="script"
        value={text}
        spellCheck={false}
        maxLength={100000}
        placeholder="여기에 대본을 붙여 넣으세요."
        onChange={(e) => setText(e.target.value)}
      />
      <div className="toolbar">
        <button className="btn primary" disabled={saving || !text.trim()} onClick={() => apply(true)}>
          {saving ? '적용 중…' : dirty ? '적용하고 생성' : '생성'}
        </button>
        <button className="btn" disabled={saving || !dirty} onClick={() => apply(false)}>
          적용만
        </button>
        <span className="muted small">글자가 같은 줄은 만든 음성·설정을 그대로 이어받습니다.</span>
      </div>
    </div>
  )
}
