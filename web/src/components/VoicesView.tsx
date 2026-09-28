import { useEffect, useState } from 'react'
import { api, urls } from '../api'
import { player, usePlayer, useRecorder } from '../player'
import type { Voice } from '../types'

interface Props {
  voices: Voice[]
  reload: () => Promise<unknown>
  notify: (msg: string, bad?: boolean) => void
  fail: (e: unknown) => void
}

const READ_ME: Record<string, string> = {
  기본: '여기 협곡을 누비는 괴물이 있습니다. 괴물의 이름은 카직스. 오늘은 이 녀석이 어떤 생물인지 하나씩 뜯어보겠습니다. 먼저 몸부터 보죠. 빠르게 움직이는 뒤쪽 다리와, 먹이를 붙잡는 앞다리가 눈에 띕니다.',
  차분: '밤이 깊어지면 숲은 조용해집니다. 바람 소리와 풀벌레 소리만 남고, 모든 생물이 숨을 고릅니다. 이 시간에 움직이는 것은, 오직 기다리는 법을 아는 사냥꾼뿐입니다.',
  긴장감: '바로 그 순간, 풀숲이 흔들립니다. 먹잇감은 아직 눈치채지 못했습니다. 거리는 단 세 걸음. 숨을 참고, 몸을 낮추고, 그리고 지금입니다!',
}

export function VoicesView({ voices, reload, notify, fail }: Props) {
  const [fresh, setFresh] = useState<string | null>(null) // 방금 등록해서 받아쓰기 확인이 필요한 목소리

  return (
    <div className="voices">
      <header className="project-head">
        <h1 className="title">목소리 관리</h1>
      </header>
      <p className="muted lead">
        목소리 샘플 = 10~30초 녹음 + 그 녹음의 <b>정확한 대본</b>. 결과물은 샘플의 말투·속도·감정을 그대로 따라갑니다. 톤별로 따로 녹음해 두고 줄마다 골라
        쓰세요.
      </p>

      <AddVoice
        existing={voices.map((v) => v.name)}
        onAdded={async (name) => {
          await reload()
          setFresh(name)
          notify('등록했습니다. 받아쓰기가 맞는지 꼭 확인하세요.')
        }}
        fail={fail}
      />

      <div className="voice-list">
        {voices.map((v) => (
          <VoiceCard key={v.name + v.updated} voice={v} fresh={fresh === v.name} reload={reload} notify={notify} fail={fail} />
        ))}
        {voices.length === 0 && <p className="muted">아직 목소리가 없습니다. 위에서 녹음하거나 파일을 올리세요.</p>}
      </div>
    </div>
  )
}

function VoiceCard({ voice, fresh, reload, notify, fail }: { voice: Voice; fresh: boolean } & Omit<Props, 'voices'>) {
  const [text, setText] = useState(voice.text)
  const ps = usePlayer()
  const key = `voice:${voice.name}`
  const dirty = text.trim() !== voice.text.trim()

  const save = async () => {
    try {
      await api.patchVoice(voice.name, text)
      await reload()
      notify('대본을 저장했습니다')
    } catch (e) {
      fail(e)
    }
  }

  const del = async () => {
    if (!window.confirm(`목소리 "${voice.name}" 를 지울까요?`)) return
    try {
      await api.deleteVoice(voice.name)
      await reload()
    } catch (e) {
      fail(e)
    }
  }

  return (
    <section className={`card voice ${fresh ? 'fresh' : ''}`}>
      <div className="row">
        <button className="play" onClick={() => player.play(key, urls.voice(voice.name, voice.updated))} aria-label={`${voice.name} 듣기`}>
          {ps.key === key ? '■' : '▶'}
        </button>
        <h2>{voice.name}</h2>
        <span className="muted small">{voice.duration.toFixed(1)}초</span>
        <span className="spacer" />
        <button className="btn ghost sm danger" onClick={del}>
          삭제
        </button>
      </div>
      {fresh && <p className="warn-text small">자동 받아쓰기 결과입니다. 들어보면서 실제로 말한 그대로 고치세요. 틀리면 복제 품질이 떨어집니다.</p>}
      <textarea className="voice-text" value={text} rows={3} maxLength={2000} onChange={(e) => setText(e.target.value)} />
      {dirty && (
        <div className="row gap-s">
          <button className="btn primary sm" onClick={save}>
            대본 저장
          </button>
          <button className="btn ghost sm" onClick={() => setText(voice.text)}>
            되돌리기
          </button>
        </div>
      )}
    </section>
  )
}

function AddVoice({ existing, onAdded, fail }: { existing: string[]; onAdded: (name: string) => Promise<void>; fail: (e: unknown) => void }) {
  const [name, setName] = useState('')
  const [tone, setTone] = useState('기본')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const rec = useRecorder(30)
  const ps = usePlayer()

  const audio = file ?? rec.blob
  useEffect(() => {
    if (!audio) return setBlobUrl(null)
    const u = URL.createObjectURL(audio)
    setBlobUrl(u)
    return () => URL.revokeObjectURL(u)
  }, [audio])

  const nameOk = /^[0-9A-Za-z가-힣_-]{1,40}$/.test(name)
  const exists = existing.includes(name)

  const submit = async () => {
    if (!audio || !nameOk) return
    if (exists && !window.confirm(`"${name}" 목소리를 새 녹음으로 바꿀까요?`)) return
    setBusy(true)
    try {
      const ext = file ? file.name.split('.').pop() : audio.type.includes('mp4') ? 'm4a' : 'webm'
      await api.addVoice(name, audio, `voice.${ext}`, exists)
      setFile(null)
      rec.clear()
      setName('')
      await onAdded(name)
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card add-voice">
      <h2>새 목소리</h2>
      <div className="grid">
        <label>
          이름
          <input value={name} placeholder="예: 차분" maxLength={40} onChange={(e) => setName(e.target.value.trim())} />
          {name && !nameOk && <small className="bad-text">한글·영문·숫자·_- 만</small>}
        </label>
        <label>
          읽을 문장 (예시)
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            {Object.keys(READ_ME).map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </label>
      </div>
      <blockquote className="read-me">{READ_ME[tone]}</blockquote>
      <p className="muted small">조용한 방에서, 실제 나레이션과 같은 말투로. 마이크에서 한 뼘 거리. 20~30초가 가장 좋습니다.</p>

      <div className="toolbar">
        {rec.recording ? (
          <button className="btn danger" onClick={rec.stop}>
            ■ 녹음 끝 ({rec.elapsed.toFixed(0)}초 / 30)
          </button>
        ) : (
          <button className="btn" onClick={() => { setFile(null); rec.start() }} disabled={busy}>
            ● 녹음
          </button>
        )}
        <label className="btn file-btn">
          파일 올리기
          <input
            type="file"
            accept="audio/*,.m4a,.wav,.mp3,.webm"
            onChange={(e) => {
              rec.clear()
              setFile(e.target.files?.[0] ?? null)
              e.target.value = ''
            }}
          />
        </label>
        {blobUrl && (
          <button className="btn ghost" onClick={() => player.play('new-voice', blobUrl)}>
            {ps.key === 'new-voice' ? '■ 멈춤' : '▶ 들어보기'}
          </button>
        )}
        {audio && <span className="muted small">{file ? file.name : `녹음 ${rec.elapsed.toFixed(0)}초`}</span>}
        <span className="spacer" />
        <button className="btn primary" disabled={!audio || !nameOk || busy || rec.recording} onClick={submit}>
          {busy ? '등록·받아쓰는 중…' : exists ? '바꿔서 등록' : '등록'}
        </button>
      </div>
      {rec.recording && <div className="rec-bar" style={{ width: `${(rec.elapsed / 30) * 100}%` }} />}
      {rec.error && <p className="bad-text small">마이크를 쓸 수 없습니다: {rec.error}</p>}
    </section>
  )
}
