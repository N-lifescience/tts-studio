"""맥(애플 실리콘) 엔진: MLX 로 돌린다. 모델은 mlx-community 변환본."""

import os

import numpy as np

NAME = "mlx"
TAIL_STYLE = "ellipsis"  # 실측: 뚝 끊김 12개 중 6 → 1
TTS_MODEL = os.environ.get("STUDIO_TTS_MODEL", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16")
ASR_MODEL = os.environ.get("STUDIO_ASR_MODEL", "mlx-community/Qwen3-ASR-1.7B-8bit")


def _mx():
    import mlx.core as mx

    mx.set_cache_limit(1 << 30)  # 16GB 맥이라 캐시를 1GB 로 묶는다
    return mx


def describe():
    return {"backend": NAME, "device": "Apple GPU (MLX)", "tts_model": TTS_MODEL, "asr_model": ASR_MODEL}


def load_tts():
    _mx()
    from mlx_audio.tts.utils import load_model

    return load_model(TTS_MODEL)


def load_asr():
    _mx()
    from mlx_audio.stt import load

    return load(ASR_MODEL)


def generate(model, text, voice_wav, voice_text, temperature, seed, max_frames=4096):
    mx = _mx()
    mx.random.seed(seed)
    results = model.generate(
        text=text,
        ref_audio=str(voice_wav),
        ref_text=voice_text,
        lang_code="korean",
        temperature=temperature,
        max_tokens=max_frames,
    )
    audio = np.concatenate([np.array(r.audio, dtype=np.float32) for r in results])
    mx.clear_cache()
    return audio


def transcribe(model, path):
    text = model.generate(str(path), language="ko").text.strip()
    _mx().clear_cache()
    return text


def clear():
    try:
        _mx().clear_cache()
    except Exception:
        pass


def peak_memory_gb():
    try:
        return round(_mx().get_peak_memory() / 1e9, 2)
    except Exception:
        return None
