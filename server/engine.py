"""모델 적재·생성·받아쓰기. GPU 는 하나라 호출은 작업 스레드 하나에서만 한다."""

import gc
import os
import threading
import time

import numpy as np

from . import config

# 이만큼(초) 안 쓰면 모델을 내려놓는다. 앱을 켜 둔 채 다른 일을 해도 메모리를 안 잡아먹게.
IDLE_UNLOAD_SEC = int(os.environ.get("STUDIO_IDLE_UNLOAD", "600"))
_last_used = time.monotonic()

_lock = threading.Lock()
_gpu = threading.Lock()  # 생성·받아쓰기가 동시에 GPU 를 쓰지 않게
_tts = None
_asr = None
status = {"tts": "unloaded", "asr": "unloaded"}


def _mx():
    import mlx.core as mx

    mx.set_cache_limit(1 << 30)  # 16GB 맥이라 캐시를 1GB 로 묶는다
    return mx


def tts():
    global _tts
    with _lock:
        if _tts is None:
            status["tts"] = "loading"
            _mx()
            from mlx_audio.tts.utils import load_model

            _tts = load_model(config.TTS_MODEL)
            status["tts"] = "ready"
        return _tts


def asr():
    global _asr
    with _lock:
        if _asr is None:
            status["asr"] = "loading"
            _mx()
            from mlx_audio.stt import load

            _asr = load(config.ASR_MODEL)
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
        try:
            _mx().clear_cache()
        except Exception:
            pass
    return True


def generate(text, voice_wav, voice_text, temperature, seed):
    _touch()
    mx = _mx()
    model = tts()
    with _gpu:
        mx.random.seed(seed)
        results = model.generate(
            text=text,
            ref_audio=str(voice_wav),
            ref_text=voice_text,
            lang_code="korean",
            temperature=temperature,
        )
        audio = np.concatenate([np.array(r.audio, dtype=np.float32) for r in results])
        mx.clear_cache()
    _touch()
    return audio


def transcribe(path):
    _touch()
    mx = _mx()
    model = asr()
    with _gpu:
        text = model.generate(str(path), language="ko").text.strip()
        mx.clear_cache()
    return text


def peak_memory_gb():
    try:
        return round(_mx().get_peak_memory() / 1e9, 2)
    except Exception:
        return None
