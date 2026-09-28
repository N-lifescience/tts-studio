"""모델 적재·생성·받아쓰기. GPU 는 하나라 호출은 작업 스레드 하나에서만 한다."""

import gc
import os
import threading
import time

import numpy as np

from . import config

# 모델이 "끝" 신호(EOS)를 이만큼 늦게 받아들인다. Qwen3-TTS 는 마지막 음절이 다 사그라들기 전에
# 끝내 버려 문장 끝이 잘려 들린다. 2프레임(약 0.16초)만 더 뽑게 하면 끝음이 무음까지 자연스럽게 내려간다
# (실측: 끝 50ms 가 -30~-42dB 로 뚝 끊기던 것이 -55dB 이하로 사그라듦, 받아쓰기 "보자"→"보죠").
EOS_DELAY_FRAMES = int(os.environ.get("STUDIO_EOS_DELAY", "2"))

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
            _delay_eos(_tts)
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


_eos_state = {"left": 0}


def _delay_eos(model):
    """샘플러를 감싸서, 끝 신호가 나오면 EOS_DELAY_FRAMES 번까지는 무시하고 다른 코드를 뽑게 한다."""
    eos = model.config.talker_config.codec_eos_token_id
    orig = model._sample_token

    def sample(logits, **kw):
        tok = orig(logits, **kw)
        # 코드 예측기(나머지 코드북)도 같은 함수를 쓰는데, 그쪽 어휘에는 EOS 가 없다
        if _eos_state["left"] > 0 and logits.shape[-1] > eos and int(tok[0, 0]) == eos:
            _eos_state["left"] -= 1
            kw = dict(kw)
            kw["suppress_tokens"] = list(kw.get("suppress_tokens") or []) + [eos]
            tok = orig(logits, **kw)
        return tok

    model._sample_token = sample


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
        _eos_state["left"] = EOS_DELAY_FRAMES
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
