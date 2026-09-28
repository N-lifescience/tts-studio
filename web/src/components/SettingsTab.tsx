import { useState } from 'react'
import { api, urls } from '../api'
import type { Settings, SubtitleSettings } from '../types'
import type { ProjectProps } from './ProjectView'

export function SettingsTab({ project, voices, setProject, onGoVoices, fail, notify }: ProjectProps) {
  const [s, setS] = useState<Settings>(project.settings)
  const [saving, setSaving] = useState(false)
  const [previewKey, setPreviewKey] = useState(project.updated)
  const dirty = JSON.stringify(s) !== JSON.stringify(project.settings)
  const sample = project.lines[0]?.text ?? '자막 미리보기입니다'

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS((x) => ({ ...x, [k]: v }))
  const sub = <K extends keyof SubtitleSettings>(k: K, v: SubtitleSettings[K]) =>
    setS((x) => ({ ...x, subtitle: { ...x.subtitle, [k]: v } }))

  const save = async () => {
    setSaving(true)
    try {
      const p = await api.patchProject(project.id, { settings: s })
      setProject(p)
      setS(p.settings)
      setPreviewKey(p.updated + Math.random())
      notify('저장했습니다')
    } catch (e) {
      fail(e)
    } finally {
      setSaving(false)
    }
  }

  const voiceChanged = s.voice !== project.settings.voice

  return (
    <div className="settings-tab">
      <section className="card">
        <h2>목소리</h2>
        <div className="grid">
          <label>
            기본 목소리
            <span className="row gap-s">
              <select value={s.voice} onChange={(e) => set('voice', e.target.value)}>
                {voices.map((v) => (
                  <option key={v.name} value={v.name}>
                    {v.name}
                  </option>
                ))}
              </select>
              <button className="btn ghost sm" type="button" onClick={onGoVoices}>
                목소리 관리
              </button>
            </span>
            {voiceChanged && <small className="warn-text">바꾸면 목소리를 따로 정하지 않은 줄은 모두 새로 만들어야 합니다.</small>}
          </label>
          <label>
            표현 다양성 <b>{s.temperature.toFixed(2)}</b>
            <input type="range" min={0.3} max={1.1} step={0.05} value={s.temperature} onChange={(e) => set('temperature', Number(e.target.value))} />
            <small>낮으면 차분하고 안정적, 높으면 억양이 다양하지만 가끔 무너집니다. (새로 만드는 줄부터 적용)</small>
          </label>
          <label>
            문장 사이 쉼 (초)
            <input type="number" min={0} max={5} step={0.1} value={s.sentence_gap} onChange={(e) => set('sentence_gap', Number(e.target.value))} />
          </label>
          <label>
            문단 사이 쉼 (초)
            <input type="number" min={0} max={5} step={0.1} value={s.para_gap} onChange={(e) => set('para_gap', Number(e.target.value))} />
          </label>
          <label>
            최종 음량 (LUFS)
            <input type="number" min={-30} max={-8} step={0.5} value={s.lufs} onChange={(e) => set('lufs', Number(e.target.value))} />
            <small>유튜브 기준 -14. 배경음악과 섞을 거면 -16 정도.</small>
          </label>
        </div>
      </section>

      <section className="card">
        <h2>자막 영상 (루마퓨전 크로마키용)</h2>
        <div className="sub-grid">
          <div className="grid">
            <label>
              글자 크기
              <input type="number" min={20} max={200} value={s.subtitle.font_size} onChange={(e) => sub('font_size', Number(e.target.value))} />
            </label>
            <label>
              위치
              <select value={s.subtitle.position} onChange={(e) => sub('position', e.target.value as SubtitleSettings['position'])}>
                <option value="bottom">아래</option>
                <option value="middle">가운데</option>
                <option value="top">위</option>
              </select>
            </label>
            <label>
              가장자리 여백 (px)
              <input type="number" min={0} max={500} value={s.subtitle.margin} onChange={(e) => sub('margin', Number(e.target.value))} />
            </label>
            <label>
              테두리 두께
              <input type="number" min={0} max={20} value={s.subtitle.outline} onChange={(e) => sub('outline', Number(e.target.value))} />
            </label>
            <label>
              글자색
              <input type="color" value={s.subtitle.color} onChange={(e) => sub('color', e.target.value)} />
            </label>
            <label>
              테두리색
              <input type="color" value={s.subtitle.outline_color} onChange={(e) => sub('outline_color', e.target.value)} />
            </label>
            <label>
              배경색 (크로마키)
              <input type="color" value={s.subtitle.background} onChange={(e) => sub('background', e.target.value)} />
            </label>
            <label>
              화면 크기
              <select
                value={`${s.subtitle.width}x${s.subtitle.height}`}
                onChange={(e) => {
                  const [w, h] = e.target.value.split('x').map(Number)
                  setS((x) => ({ ...x, subtitle: { ...x.subtitle, width: w, height: h } }))
                }}
              >
                <option value="1920x1080">1920×1080 (가로)</option>
                <option value="3840x2160">3840×2160 (4K)</option>
                <option value="1080x1920">1080×1920 (쇼츠)</option>
              </select>
            </label>
          </div>
          <figure className="sub-preview">
            <img src={urls.subtitlePreview(project.id, sample, String(previewKey))} alt="자막 미리보기" />
            <figcaption>{dirty ? '저장하면 미리보기에 반영됩니다' : '첫 줄로 그린 미리보기'}</figcaption>
          </figure>
        </div>
      </section>

      <div className="toolbar sticky-save">
        <button className="btn primary" disabled={!dirty || saving} onClick={save}>
          {saving ? '저장 중…' : '저장'}
        </button>
        {dirty && (
          <button className="btn ghost" onClick={() => setS(project.settings)}>
            되돌리기
          </button>
        )}
      </div>
    </div>
  )
}
