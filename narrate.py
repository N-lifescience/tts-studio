"""대본(.txt) → 내 목소리 나레이션(.wav) + 자막(.srt)

    ./narrate scripts/ep01.txt               # 전체 생성 (이미 만든 문장은 건너뜀)
    ./narrate scripts/ep01.txt --redo 3 7    # 3·7번 문장만 새 테이크로 다시
    ./narrate scripts/ep01.txt --list        # 문장 번호 확인

대본 규칙: 빈 줄 = 문단 구분(길게 쉼). 줄바꿈·문장 끝 = 조각 구분(짧게 쉼). 조각마다 따로 생성한다.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(ROOT / ".hf"))  # 모델은 SSD 에 둔다

from server.textsplit import split_script  # noqa: E402  웹 작업실과 같은 규칙으로 나눈다

DEFAULT_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16"
SR = 24000


def trim_silence(audio, thresh=0.01, pad=int(0.04 * SR)):
    import numpy as np

    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    return audio[max(0, idx[0] - pad) : min(len(audio), idx[-1] + pad)]


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, help="대본 txt")
    ap.add_argument("--voice", default="myvoice", help="voices/<이름>.wav + .txt (기본 myvoice)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--redo", type=int, nargs="*", default=[], help="다시 뽑을 문장 번호")
    ap.add_argument("--list", action="store_true", help="문장 번호만 출력")
    ap.add_argument("--sentence-gap", type=float, default=0.3, help="문장 사이 쉼(초)")
    ap.add_argument("--para-gap", type=float, default=0.8, help="문단 사이 쉼(초)")
    ap.add_argument("--temperature", type=float, default=0.7, help="낮을수록 안정적, 높을수록 억양 다양")
    ap.add_argument("--lufs", type=float, default=-14.0, help="최종 음량 (유튜브 기준 -14)")
    args = ap.parse_args()

    chunks = split_script(args.script.read_text(encoding="utf-8"))
    if args.list:
        for i, (pi, t) in enumerate(chunks, 1):
            print(f"{i:3}  [문단{pi + 1}]  {t}")
        return

    voice_wav = ROOT / "voices" / f"{args.voice}.wav"
    voice_txt = ROOT / "voices" / f"{args.voice}.txt"
    if not voice_wav.exists() or not voice_txt.exists():
        sys.exit(f"목소리 파일 없음: {voice_wav} / {voice_txt}")
    ref_text = voice_txt.read_text(encoding="utf-8").strip()

    out_dir = ROOT / "out" / args.script.stem
    chunk_dir = out_dir / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    takes_file = out_dir / "takes.json"
    takes = json.loads(takes_file.read_text()) if takes_file.exists() else {}

    import mlx.core as mx
    import numpy as np
    import soundfile as sf

    model = None
    pieces = []
    for i, (pi, text) in enumerate(chunks, 1):
        key = hashlib.sha1(f"{args.model}|{args.voice}|{args.temperature}|{text}".encode()).hexdigest()[:10]
        if i in args.redo:
            takes[key] = takes.get(key, 0) + 1
        take = takes.get(key, 0)
        path = chunk_dir / f"{i:03}_{key}_t{take}.wav"

        if not path.exists():
            if model is None:
                from mlx_audio.tts.utils import load_model

                print(f"모델 불러오는 중: {args.model}")
                model = load_model(args.model)
            print(f"[{i}/{len(chunks)}] {text}")
            mx.random.seed(int(key, 16) % (2**31) + take)
            results = model.generate(
                text=text,
                ref_audio=str(voice_wav),
                ref_text=ref_text,
                lang_code="korean",
                temperature=args.temperature,
            )
            audio = np.concatenate([np.array(r.audio, dtype=np.float32) for r in results])
            sf.write(path, trim_silence(audio), SR)
            mx.clear_cache()
        else:
            print(f"[{i}/{len(chunks)}] (재사용) {text[:40]}")

        pieces.append((pi, text, path))

    takes_file.write_text(json.dumps(takes, ensure_ascii=False, indent=1))
    # 대본이 바뀌어 더 이상 안 쓰는 조각은 정리
    used = {p.name for _, _, p in pieces}
    for f in chunk_dir.glob("*.wav"):
        if f.name not in used:
            f.unlink()

    # 이어 붙이기 + 자막 타이밍
    audio_all, srt, t = [], [], 0.0
    for n, (pi, text, path) in enumerate(pieces):
        if n > 0:
            gap = args.para_gap if pi != pieces[n - 1][0] else args.sentence_gap
            audio_all.append(np.zeros(int(gap * SR), dtype=np.float32))
            t += gap
        a, _ = sf.read(path, dtype="float32")
        audio_all.append(a)
        dur = len(a) / SR
        srt.append(f"{n + 1}\n{srt_time(t)} --> {srt_time(t + dur)}\n{text}\n")
        t += dur

    raw = out_dir / "narration_raw.wav"
    sf.write(raw, np.concatenate(audio_all), SR)
    (out_dir / "narration.srt").write_text("\n".join(srt), encoding="utf-8")

    # 음량 맞추기: 1차 측정 → 2차 보정 (한 번에 하면 짧은 음성에서 목표보다 작게 나온다)
    final = out_dir / "narration.wav"
    norm = f"loudnorm=I={args.lufs}:TP=-1.5:LRA=20"
    measured = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(raw), "-af", norm + ":print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    m = json.loads(measured[measured.rindex("{") : measured.rindex("}") + 1])
    norm += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
             f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", norm, "-ar", "48000", str(final)],
        check=True,
    )
    print(f"\n완료 ({t:.1f}초)\n  음성: {final}\n  자막: {out_dir / 'narration.srt'}")


if __name__ == "__main__":
    main()
