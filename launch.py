"""TTS 작업실 켜기 (윈도우 바탕화면 아이콘 → studio.bat → 여기).

이미 켜져 있으면 브라우저만 연다. 아니면 화면이 바뀌었을 때 다시 빌드하고, 서버를 켜고, 준비되면 브라우저를 연다.
이 창을 닫으면 서버도 꺼진다.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("STUDIO_PORT", "7870"))
URL = f"http://127.0.0.1:{PORT}"


def up():
    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=2):
            return True
    except Exception:
        return False


def web_is_stale():
    index = ROOT / "web" / "dist" / "index.html"
    if not index.exists():
        return True
    built = index.stat().st_mtime
    srcs = [ROOT / "web" / "index.html", *(ROOT / "web" / "src").rglob("*")]
    return any(p.is_file() and p.stat().st_mtime > built for p in srcs)


def build_web():
    npm = shutil.which("npm")
    if not npm:
        sys.exit("화면을 빌드하려면 Node.js 가 필요합니다. setup.bat 을 다시 실행하세요.")
    print("화면 빌드 중…")
    web = ROOT / "web"
    if not (web / "node_modules").exists():
        subprocess.run([npm, "ci"], cwd=web, check=True)
    subprocess.run([npm, "run", "build"], cwd=web, check=True, stdout=subprocess.DEVNULL)


def open_when_ready():
    for _ in range(240):  # 처음 켤 때 모델 없이도 서버는 금방 뜬다
        if up():
            if not os.environ.get("STUDIO_NO_OPEN"):
                webbrowser.open(URL)
            return
        time.sleep(0.5)


def main():
    os.chdir(ROOT)
    if up():
        print(f"이미 켜져 있습니다 → {URL}")
        webbrowser.open(URL)
        return
    if not shutil.which("ffmpeg"):
        print("⚠ ffmpeg 를 찾을 수 없습니다. 음성 합치기·내보내기가 안 됩니다. setup.bat 을 다시 실행하세요.")
    if web_is_stale():
        build_web()
    threading.Thread(target=open_when_ready, daemon=True).start()
    print(f"TTS 작업실 → {URL}")
    print("이 창을 닫으면 꺼집니다.")
    sys.path.insert(0, str(ROOT))
    from server.app import main as serve

    serve()


if __name__ == "__main__":
    main()
