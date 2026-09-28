"""오디오 처리: 무음 자르기, 속도, 이어 붙이기, 음량 맞추기, 목소리 샘플 변환."""

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from . import config


def trim_silence(audio, sr=config.SR, thresh=0.01, pad_sec=0.04):
    idx = np.where(np.abs(audio) > thresh)[0]
    if len(idx) == 0:
        return audio
    pad = int(pad_sec * sr)
    return audio[max(0, idx[0] - pad) : min(len(audio), idx[-1] + pad)]


def _ffmpeg(*args, capture=False):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {r.stderr.strip()[-400:]}")
    return r.stderr if capture else None


def change_speed(audio, speed, sr=config.SR):
    """음높이는 그대로 두고 빠르기만 바꾼다 (ffmpeg atempo)."""
    if abs(speed - 1.0) < 1e-3:
        return audio
    speed = min(2.0, max(0.5, speed))
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
         "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "pipe:0",
         "-af", f"atempo={speed}", "-f", "f32le", "pipe:1"],
        input=audio.astype(np.float32).tobytes(), capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode()[-400:])
    return np.frombuffer(r.stdout, dtype=np.float32)


def default_gap(settings, line, next_line):
    if line.get("gap") is not None:
        return float(line["gap"])
    if next_line is None:
        return 0.0
    return settings["para_gap"] if next_line["para"] != line["para"] else settings["sentence_gap"]


def mix(items, sr=config.SR):
    """items: [(audio, gap_after), ...] → (전체 오디오, [(시작, 끝), ...])"""
    parts, spans, t = [], [], 0.0
    for audio, gap in items:
        parts.append(audio)
        spans.append((t, t + len(audio) / sr))
        t += len(audio) / sr
        if gap > 0:
            parts.append(np.zeros(int(round(gap * sr)), dtype=np.float32))
            t += int(round(gap * sr)) / sr
    audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    return audio, spans


def loudnorm(src, dst, lufs, out_sr=config.OUT_SR):
    """2패스 음량 맞추기 (1패스는 짧은 음성에서 목표보다 작게 나온다)."""
    norm = f"loudnorm=I={lufs}:TP=-1.5:LRA=20"
    err = _ffmpeg("-i", src, "-af", norm + ":print_format=json", "-f", "null", "-", capture=True)
    m = json.loads(err[err.rindex("{") : err.rindex("}") + 1])
    if m["input_i"] in ("-inf", "inf"):  # 무음
        _ffmpeg("-y", "-loglevel", "error", "-i", src, "-ar", out_sr, dst)
        return
    norm += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
             f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    _ffmpeg("-y", "-loglevel", "error", "-i", src, "-af", norm, "-ar", out_sr, dst)


def import_voice(src: Path, dst_wav: Path):
    """아무 녹음 파일 → 24kHz 모노 wav, 앞뒤 무음 제거, 최대 30초."""
    tmp = dst_wav.with_suffix(".tmp.wav")
    _ffmpeg("-y", "-loglevel", "error", "-i", src, "-ac", 1, "-ar", config.SR, "-t", config.MAX_VOICE_SECONDS + 5, tmp)
    a, _ = sf.read(tmp, dtype="float32")
    tmp.unlink()
    a = trim_silence(a, thresh=0.02, pad_sec=0.1)[: config.SR * config.MAX_VOICE_SECONDS]
    if len(a) < config.SR * 3:
        raise ValueError("목소리 샘플이 3초보다 짧습니다 (10~30초 권장)")
    peak = float(np.max(np.abs(a)))
    if peak > 0:
        a = a * (0.9 / peak)
    sf.write(dst_wav, a, config.SR)
    return len(a) / config.SR
