import type { Voice } from '../types'

const STYLES = ['기본', '의문형', '빠르게', '느리게', '신나게', '차분하게']

export function VoicePicker({ voices, value, onChange, disabled = false }: {
  voices: Voice[]
  value: string
  onChange: (name: string) => void
  disabled?: boolean
}) {
  const options = voices.some((v) => v.name === value)
    ? voices : [...voices, { name: value, family: value, style: '기본' } as Voice]
  const selected = options.find((v) => v.name === value)
  const family = selected?.family || value
  const families = [...new Set(options.map((v) => v.family || v.name))]
  const variants = options.filter((v) => (v.family || v.name) === family)
    .sort((a, b) => STYLES.indexOf(a.style || '기본') - STYLES.indexOf(b.style || '기본'))

  return <div className="voice-picker">
    <label>
      목소리
      <select value={family} disabled={disabled} onChange={(e) => {
        const group = options.filter((v) => (v.family || v.name) === e.target.value)
        const next = group.find((v) => v.style === selected?.style)
          || group.find((v) => !v.style || v.style === '기본') || group[0]
        if (next) onChange(next.name)
      }}>
        {families.map((name) => <option key={name} value={name}>{name}</option>)}
      </select>
    </label>
    <label>
      말투
      <select value={value} disabled={disabled || variants.length < 2} onChange={(e) => onChange(e.target.value)}>
        {variants.map((v) => <option key={v.name} value={v.name}>{v.style || '기본'}</option>)}
      </select>
    </label>
  </div>
}
