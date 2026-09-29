"""윈도우·리눅스 엔진: PyTorch 로 돌린다 (공식 qwen-tts 패키지 + faster-whisper).

NVIDIA 그래픽카드(CUDA)가 있으면 GPU 에서 1.7B 모델, 없으면 CPU 에서 0.6B 모델을 쓴다.
인텔 내장 그래픽(UHD 등)은 쓰지 못해 CPU 로 돈다.

실측 (맥 M4 CPU 4스레드로 흉내, 0.6B·32비트): 문장 길이의 3~8배 시간, 메모리 평소 3~3.3GB·
불러오는 순간 최대 6.5GB. 참고 녹음이 짧을수록(10~15초) 빠르고 가볍다.
16비트(bf16)는 CPU 에서 너무 느려서 쓰지 않는다.
"""

import os

import numpy as np

NAME = "torch"
TAIL_STYLE = "period"  # 실측 뚝 끊김: 0.6B 8개 중 그대로 8 · "..." 7 · "." 4 / 1.7B 4개 중 "..." 3 · "." 2
SR = 24000


def _torch():
    import torch

    return torch


def device():
    t = _torch()
    return "cuda" if t.cuda.is_available() else "cpu"


def _defaults():
    if device() == "cuda":
        return "Qwen/Qwen3-TTS-12Hz-1.7B-Base", "large-v3-turbo"
    return "Qwen/Qwen3-TTS-12Hz-0.6B-Base", "small"


def tts_model_name():
    return os.environ.get("STUDIO_TTS_MODEL") or _defaults()[0]


def asr_model_name():
    return os.environ.get("STUDIO_ASR_MODEL") or _defaults()[1]


def describe():
    t = _torch()
    dev = device()
    name = t.cuda.get_device_name(0) if dev == "cuda" else f"CPU {os.cpu_count()}스레드"
    return {"backend": NAME, "device": name, "tts_model": tts_model_name(), "asr_model": asr_model_name()}


class _TTS:
    """모델 + 목소리별 참고 녹음 분석 결과(캐시). 분석은 목소리마다 한 번만 한다."""

    def __init__(self):
        t = _torch()
        from qwen_tts import Qwen3TTSModel

        dev = device()
        self.model = Qwen3TTSModel.from_pretrained(
            tts_model_name(),
            device_map="cuda:0" if dev == "cuda" else "cpu",
            dtype=t.bfloat16 if dev == "cuda" else t.float32,
            low_cpu_mem_usage=True,
        )
        self.prompts = {}

    def prompt(self, voice_wav, voice_text):
        key = (str(voice_wav), os.path.getmtime(voice_wav), voice_text)
        if key not in self.prompts:
            self.prompts.clear()  # 목소리를 바꾸면 예전 것은 버린다 (메모리 아끼기)
            self.prompts[key] = self.model.create_voice_clone_prompt(ref_audio=str(voice_wav), ref_text=voice_text)
        return self.prompts[key]


def load_tts():
    return _TTS()


def load_asr():
    from faster_whisper import WhisperModel

    if device() == "cuda":
        try:
            return WhisperModel(asr_model_name(), device="cuda", compute_type="float16")
        except Exception as e:  # 윈도우는 cuDNN·cuBLAS 가 따로 없으면 여기서 실패한다 → CPU 로
            print(f"받아쓰기를 GPU 로 못 올려 CPU 로 돌립니다: {e}")
            return WhisperModel("small", device="cpu", compute_type="int8")
    return WhisperModel(asr_model_name(), device="cpu", compute_type="int8")


def generate(model, text, voice_wav, voice_text, temperature, seed, max_frames=2048):
    t = _torch()
    t.manual_seed(seed)
    wavs, sr = model.model.generate_voice_clone(
        text=text,
        language="Korean",
        voice_clone_prompt=model.prompt(voice_wav, voice_text),
        temperature=temperature,
        max_new_tokens=max_frames,
    )
    audio = np.asarray(wavs[0], dtype=np.float32)
    if sr != SR:  # 지금 모델은 24kHz 라 여기 올 일은 없다
        import scipy.signal as ss

        audio = ss.resample_poly(audio, SR, sr).astype(np.float32)
    return audio


def transcribe(model, path):
    segments, _ = model.transcribe(str(path), language="ko", beam_size=1 if device() == "cpu" else 5)
    return "".join(s.text for s in segments).strip()


def clear():
    try:
        t = _torch()
        if t.cuda.is_available():
            t.cuda.empty_cache()
    except Exception:
        pass


def peak_memory_gb():
    try:
        t = _torch()
        if t.cuda.is_available():
            return round(t.cuda.max_memory_allocated() / 1e9, 2)
    except Exception:
        pass
    return None
