import { useEffect, useRef, useState } from 'react'
import { api, urls } from '../api'
import { player, usePlayer, useRecorder } from '../player'
import type { Voice } from '../types'

interface Props {
  voices: Voice[]
  focus?: string
  reload: () => Promise<unknown>
  onDelete: (name: string) => void
  notify: (msg: string, bad?: boolean) => void
  fail: (e: unknown) => void
}

const READ_ME: Record<string, string> = {
  기본: '여기 협곡을 누비는 괴물이 있습니다. 괴물의 이름은 카직스. 오늘은 이 녀석이 어떤 생물인지 하나씩 뜯어보겠습니다. 먼저 몸부터 보죠. 빠르게 움직이는 뒤쪽 다리와, 먹이를 붙잡는 앞다리가 눈에 띕니다.',
  차분: '밤이 깊어지면 숲은 조용해집니다. 바람 소리와 풀벌레 소리만 남고, 모든 생물이 숨을 고릅니다. 이 시간에 움직이는 것은, 오직 기다리는 법을 아는 사냥꾼뿐입니다.',
  긴장감: '바로 그 순간, 풀숲이 흔들립니다. 먹잇감은 아직 눈치채지 못했습니다. 거리는 단 세 걸음. 숨을 참고, 몸을 낮추고, 그리고 지금입니다!',
}

export function VoicesView({ voices, focus, reload, onDelete, notify, fail }: Props) {
  const [fresh, setFresh] = useState<string | null>(null) // 방금 등록해서 받아쓰기 확인이 필요한 목소리

  return (
    <div className="voices">
      <header className="project-head">
        <h1 className="title">목소리 관리</h1>
      </header>
      <p className="muted lead">
        말투 샘플의 억양을 참고합니다. 감정의 강도는 생성할 때마다 달라질 수 있어요.
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
          <VoiceCard
            key={v.name + v.updated}
            voice={v}
            fresh={fresh === v.name}
            focused={focus === v.name}
            reload={reload}
            onDelete={onDelete}
            notify={notify}
            fail={fail}
          />
        ))}
        {voices.length === 0 && <p className="muted">아직 목소리가 없습니다. 위에서 녹음하거나 파일을 올리세요.</p>}
      </div>
    </div>
  )
}

function VoiceCard({
  voice,
  fresh,
  focused,
  reload,
  onDelete,
  notify,
  fail,
}: { voice: Voice; fresh: boolean; focused: boolean } & Omit<Props, 'voices' | 'focus'>) {
  const [text, setText] = useState(voice.text)
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    if (focused) ref.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focused])
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

  return (
    <section ref={ref} className={`card voice ${fresh ? 'fresh' : ''} ${focused ? 'focused' : ''}`}>
      <div className="row">
        <button className="play" onClick={() => player.play(key, urls.voice(voice.name, voice.updated))} aria-label={`${voice.name} 원본 샘플 듣기`}>
          {ps.key === key ? '■' : '▶'}
        </button>
        <h2>{voice.name}</h2>
        <span className="muted small">{voice.duration.toFixed(1)}초</span>
        <span className="spacer" />
        <button className="btn ghost sm danger" onClick={() => onDelete(voice.name)}>
          삭제
        </button>
      </div>
      {voice.provider && <p className="muted voice-source">출처 {voice.provider} · {voice.family} · {voice.style} · 원본 샘플</p>}
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
      <p className="muted small">조용한 곳에서 자연스럽게 읽은 5~15초 샘플을 권장합니다. 대본은 샘플에서 실제로 읽은 말과 같아야 해요.</p>

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
