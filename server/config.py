"""경로·기본값. 전부 이 폴더(SSD) 안에 둔다."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / ".hf"))

PROJECTS_DIR = Path(os.environ.get("STUDIO_PROJECTS_DIR", ROOT / "projects"))
VOICES_DIR = Path(os.environ.get("STUDIO_VOICES_DIR", ROOT / "voices"))
WEB_DIST = ROOT / "web" / "dist"

# 아이패드(루마퓨전)로 넘기는 곳: iCloud Drive (맥·윈도우용 iCloud) → 없으면 문서 폴더.
def _export_root():
    if os.environ.get("STUDIO_EXPORT_DIR"):
        return Path(os.environ["STUDIO_EXPORT_DIR"])
    home = Path.home()
    for icloud in (home / "Library" / "Mobile Documents" / "com~apple~CloudDocs", home / "iCloudDrive"):
        if icloud.exists():
            return icloud / "TTS"
    return home / "Documents" / "TTS 작업실 내보내기"


EXPORT_ROOT = _export_root()
EXPORT_IS_ICLOUD = "iCloud" in str(EXPORT_ROOT) or "CloudDocs" in str(EXPORT_ROOT)

SR = 24000
OUT_SR = 48000

MAX_AUTO_ATTEMPTS = 3  # 발음 검사에서 틀리면 이만큼까지 자동으로 다시 뽑는다
MAX_VOICE_SECONDS = 30
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# 자막 글꼴 (굵게): 맥 = Apple SD Gothic Neo, 윈도우 = 맑은 고딕, 리눅스 = Noto Sans CJK
_FONTS = [
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6),
    ("C:/Windows/Fonts/malgunbd.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
]
FONT_PATH, FONT_INDEX_BOLD = next(((f, i) for f, i in _FONTS if Path(f).exists()), (None, 0))

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
