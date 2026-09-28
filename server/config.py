"""경로·기본값. 전부 이 폴더(SSD) 안에 둔다."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / ".hf"))

PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS_DIR", ROOT / "projects"))
VOICES_DIR = Path(os.environ.get("STUDIO_VOICES_DIR", ROOT / "voices"))
WEB_DIST = ROOT / "web" / "dist"

# 아이패드(루마퓨전)로 넘기는 곳. iCloud Drive 가 없으면 프로젝트 폴더 안 export/ 에만 쓴다.
ICLOUD_DIR = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
EXPORT_ROOT = Path(os.environ.get("STUDIO_EXPORT_DIR", ICLOUD_DIR / "TTS"))

TTS_MODEL = os.environ.get("STUDIO_TTS_MODEL", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16")
ASR_MODEL = os.environ.get("STUDIO_ASR_MODEL", "mlx-community/Qwen3-ASR-1.7B-8bit")
SR = 24000
OUT_SR = 48000

MAX_AUTO_ATTEMPTS = 3  # 발음 검사에서 틀리면 이만큼까지 자동으로 다시 뽑는다
MAX_VOICE_SECONDS = 30
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
FONT_INDEX_BOLD = 6

DEFAULT_SETTINGS = {
    "voice": "myvoice",
    "temperature": 0.7,
    "sentence_gap": 0.3,
    "para_gap": 0.8,
    "lufs": -14.0,
    "subtitle": {
        "width": 1920,
        "height": 1080,
        "font_size": 64,
        "position": "bottom",  # bottom | middle | top
        "margin": 90,
        "color": "#FFFFFF",
        "outline": 6,
        "outline_color": "#000000",
        "background": "#00FF00",
    },
}
