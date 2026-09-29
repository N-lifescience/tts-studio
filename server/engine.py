"""모델 적재·생성·받아쓰기. GPU 는 하나라 호출은 작업 스레드 하나에서만 한다.

실제 모델 호출은 플랫폼별 엔진이 한다: 맥(애플 실리콘) = engine_mlx, 윈도우·리눅스 = engine_torch.
STUDIO_BACKEND=mlx|torch 로 강제할 수 있다.
"""

import gc
import importlib.util
import os
import platform
import sys
import threading
import time

from . import config  # noqa: F401  HF_HOME 을 SSD 로 먼저 잡는다


def _pick_backend():
    forced = os.environ.get("STUDIO_BACKEND")
    if forced:
        return forced
    if sys.platform == "darwin" and platform.machine() == "arm64" and importlib.util.find_spec("mlx"):
        return "mlx"
    return "torch"


BACKEND = _pick_backend()
if BACKEND == "mlx":
    from . import engine_mlx as _be
else:
    from . import engine_torch as _be


def describe():
    return _be.describe()


def max_attempts():
    """검사에 떨어지면 자동으로 몇 번까지 뽑을지. CPU 는 한 번 뽑는 데 수십 초라 다시 뽑기는 사람에게 맡긴다."""
    if BACKEND == "torch" and _be.device() == "cpu":
        return int(os.environ.get("STUDIO_MAX_ATTEMPTS", "1"))
    return int(os.environ.get("STUDIO_MAX_ATTEMPTS", str(config.MAX_AUTO_ATTEMPTS)))


# 문장 끝이 뚝 끊기는 문제: Qwen3-TTS 는 대본이 끝나는 곳을 "말이 끊기는 곳"으로 받아들여 마지막 음절을
# 다 사그라들기 전에 멈춘다. 모델에 넘길 때만 끝에 "..." 를 붙이면 끝음을 끝까지 읽는다.
# 실측(4문장×3회, 말소리가 -40dB→-60dB 로 사그라드는 시간): 그대로 25ms·12개 중 6개 뚝 끊김 →
# "..." 115ms·1개. "." 만 붙이면 60ms·4개. 말소리 길이·받아쓰기 내용은 그대로.
# (끝 신호를 늦게 받는 방법·반복 억제 끄기·표현 다양성 낮추기는 효과가 없었다)
# PyTorch 엔진 0.6B 에서는 "..." 가 오히려 끝에 군소리를 붙여 역효과였다 (뚝 끊김 8개 중: 그대로 8, "..." 7, "." 4).
# 그래서 엔진마다 TAIL_STYLE 을 따로 둔다.
TAIL_VERSION = "tail2"  # 이 방식이 바뀌면 올린다 (./narrate 캐시가 알아서 다시 만들게)


def tts_text(text, style=None):
    """모델에 넘길 글자. style: "ellipsis" = 끝에 "...", "period" = 끝에 "." (엔진마다 잘 듣는 쪽이 다르다)"""
    style = style or getattr(_be, "TAIL_STYLE", "ellipsis")
    t = text.rstrip()
    if style == "period":
        return t if t.endswith((".", "?", "!", "…")) else t + "."
    if t.endswith(("?", "!")):
        return t + ".."
    return t.rstrip(".…") + "..."


def max_frames(text):
    """생성 길이 상한 (12.5프레임/초). 끝 신호를 놓치면 모델이 최대 길이(수 분)까지 떠드는 일이 있어
    글자 수로 넉넉히 막는다: 한국어는 1초에 6~7글자 → 글자당 0.3초 + 여유 3초."""
    return int(12.5 * (3 + 0.3 * len(text)))


# 이만큼(초) 안 쓰면 모델을 내려놓는다. 앱을 켜 둔 채 다른 일을 해도 메모리를 안 잡아먹게.
IDLE_UNLOAD_SEC = int(os.environ.get("STUDIO_IDLE_UNLOAD", "600"))
_last_used = time.monotonic()

_lock = threading.Lock()
_gpu = threading.Lock()  # 생성·받아쓰기가 동시에 GPU 를 쓰지 않게
_tts = None
_asr = None
status = {"tts": "unloaded", "asr": "unloaded"}


def tts():
    global _tts
    with _lock:
        if _tts is None:
            status["tts"] = "loading"
            _tts = _be.load_tts()
            status["tts"] = "ready"
        return _tts


def asr():
    global _asr
    with _lock:
        if _asr is None:
            status["asr"] = "loading"
            _asr = _be.load_asr()
            status["asr"] = "ready"
        return _asr


def _touch():
    global _last_used
    _last_used = time.monotonic()


def unload_if_idle():
    """쓰지 않은 지 IDLE_UNLOAD_SEC 가 지났으면 모델을 내린다. 다음 생성 때 다시 올린다(10초쯤)."""
    global _tts, _asr
    if time.monotonic() - _last_used < IDLE_UNLOAD_SEC or (_tts is None and _asr is None):
        return False
    with _lock, _gpu:
        _tts = _asr = None
        status["tts"] = status["asr"] = "unloaded"
        gc.collect()
        _be.clear()
    return True


def generate(text, voice_wav, voice_text, temperature, seed):
    _touch()
    model = tts()
    with _gpu:
        audio = _be.generate(model, tts_text(text), voice_wav, voice_text, temperature, seed, max_frames(text))
    _touch()
    return audio


def transcribe(path):
    _touch()
    model = asr()
    with _gpu:
        return _be.transcribe(model, path)


def peak_memory_gb():
    return _be.peak_memory_gb()
