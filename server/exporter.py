"""나레이션 만들기(미리듣기·내보내기).

내보내기 결과 (projects/<id>/export/ 와 iCloud Drive/TTS/<제목>/ 두 곳):
  narration.wav         전체 (48kHz, 목표 음량)
  narration.srt         유튜브 CC
  subtitles_green.mp4   초록 배경 자막 영상
  lines/03_00m07.4s_몸을빠르게.wav   줄별 조각 (전체 파일에서 잘라내 음량이 같다)
"""

import re
import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from . import audio, config, store, subtitles


class NotReady(Exception):
    pass


def build(d, require_all=True):
    """채택된 테이크를 이어 붙인다. → (24kHz 오디오, cues[(시작, 끝, 텍스트)], 빠진 줄 번호들)"""
    lines = d["lines"]
    missing = [i + 1 for i, l in enumerate(lines) if store.chosen_take(d, l) is None]
    if require_all and missing:
        raise NotReady(f"아직 안 만든 줄: {', '.join(map(str, missing))}")
    items, texts = [], []
    for i, l in enumerate(lines):
        t = store.chosen_take(d, l)
        if t is None:
            continue
        a, _ = sf.read(store.take_path(d, t), dtype="float32")
        a = audio.change_speed(a, float(l["speed"]))
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        items.append((a, audio.default_gap(d["settings"], l, nxt)))
        texts.append(l["text"])
    mixed, spans = audio.mix(items)
    cues = [(a, b, t) for (a, b), t in zip(spans, texts)]
    return mixed, cues, missing


def preview(d, dst: Path):
    """전체 듣기용 (음량 보정 없이 빠르게, 빠진 줄은 건너뜀)."""
    mixed, cues, missing = build(d, require_all=False)
    sf.write(dst, mixed, config.SR)
    return {"duration": len(mixed) / config.SR, "missing": missing, "cues": cues}


def safe_name(text, n=12):
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", text)[:n]
    return s or "line"


def folder_name(d):
    """iCloud 폴더 이름 = 제목 (파일 이름에 못 쓰는 글자만 뺀다)."""
    return re.sub(r"[^0-9A-Za-z가-힣 _-]", "", d["title"]).strip()[:60] or d["id"]


def stamp(sec):
    m, s = divmod(sec, 60)
    return f"{int(m):02}m{s:04.1f}s"


def export(d, progress=lambda msg: None):
    mixed, cues, _ = build(d, require_all=True)
    out = store._dir(d["id"]) / "export"
    tmpdir = Path(tempfile.mkdtemp(dir=store._dir(d["id"])))
    try:
        progress("음량 맞추는 중")
        raw = tmpdir / "raw.wav"
        sf.write(raw, mixed, config.SR)
        audio.loudnorm(raw, tmpdir / "narration.wav", d["settings"]["lufs"])
        raw.unlink()
        (tmpdir / "narration.srt").write_text(subtitles.make_srt(cues), encoding="utf-8")

        progress("줄별 조각 자르는 중")
        final, sr = sf.read(tmpdir / "narration.wav", dtype="float32")
        (tmpdir / "lines").mkdir()
        for i, (a, b, text) in enumerate(cues, 1):
            seg = final[int(a * sr) : int(np.ceil(b * sr))]
            sf.write(tmpdir / "lines" / f"{i:02}_{stamp(a)}_{safe_name(text)}.wav", seg, sr)

        progress("자막 영상 만드는 중")
        total = len(final) / sr
        subtitles.make_video(cues, total, d["settings"]["subtitle"], tmpdir / "subtitles_green.mp4")

        if out.exists():
            shutil.rmtree(out)
        tmpdir.rename(out)
    finally:
        if tmpdir.exists():
            shutil.rmtree(tmpdir)

    result = {"local": str(out), "icloud": None, "duration": round(total, 2), "files": sorted(
        str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())}

    progress("iCloud Drive 로 복사 중" if config.EXPORT_IS_ICLOUD else "내보내기 폴더로 복사 중")
    dst = config.EXPORT_ROOT / folder_name(d)
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(out, dst)
    result["icloud"] = str(dst)
    return result
