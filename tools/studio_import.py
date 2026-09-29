"""켜져 있는 TTS 작업실에 대본을 넣는다 (Claude 가 드라이브 문서를 넣을 때, 또는 명령줄에서).

    .venv/bin/python tools/studio_import.py 대본.docx                 # 에피소드 만들고 음성 생성
    .venv/bin/python tools/studio_import.py 대본.pdf --export          # 다 만들어지면 내보내기까지
    .venv/bin/python tools/studio_import.py --text 대본.txt --title "ep05 개미"
    .venv/bin/python tools/studio_import.py 대본.docx --no-generate    # 대본만 넣기

앱이 꺼져 있으면 알려 주고 끝난다 (Dock/바탕화면의 TTS 작업실을 먼저 켤 것).
--wait 를 주면 생성이 끝날 때까지 기다렸다가 줄마다 결과를 보여 준다.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PORT = int(os.environ.get("STUDIO_PORT", "7870"))
BASE = f"http://127.0.0.1:{PORT}/api"


def call(method, path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)["detail"]
        except Exception:
            pass
        sys.exit(f"실패 ({e.code}): {detail}")
    except urllib.error.URLError:
        sys.exit(f"TTS 작업실이 꺼져 있습니다 ({BASE}). Dock/바탕화면의 TTS 작업실을 먼저 켜세요.")


def multipart(fields, file=None):
    b = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    if file:
        name = Path(file).name
        parts.append(
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n".encode() + Path(file).read_bytes() + b"\r\n"
        )
    parts.append(f"--{b}--\r\n".encode())
    return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={b}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help=".docx · .pdf · .txt")
    ap.add_argument("--text", help="대본이 든 텍스트 파일 (구글 문서를 글자로 받은 경우)")
    ap.add_argument("--title", default="", help="에피소드 제목 (기본: 파일 이름)")
    ap.add_argument("--no-generate", action="store_true", help="대본만 넣고 음성은 만들지 않기")
    ap.add_argument("--export", action="store_true", help="다 만들어지면 내보내기까지")
    ap.add_argument("--wait", action="store_true", help="생성이 끝날 때까지 기다리기")
    a = ap.parse_args()
    if not a.file and not a.text:
        ap.error("파일이나 --text 가 필요합니다")

    fields = {"title": a.title, "generate": str(not a.no_generate).lower(), "export": str(a.export).lower()}
    if a.text:
        fields["text"] = Path(a.text).read_text(encoding="utf-8")
        fields["title"] = a.title or Path(a.text).stem
    body, headers = multipart(fields, a.file)
    d = call("POST", "/projects/import", body, headers)
    print(f"에피소드 '{d['title']}' ({d['id']}) · {len(d['lines'])}줄")

    if a.wait and not a.no_generate:
        time.sleep(2)
        while True:
            st = call("GET", "/status")
            if st["pending"] == 0 and not st["current"]:
                break
            time.sleep(3)
        d = call("GET", f"/projects/{d['id']}")
        for i, l in enumerate(d["lines"], 1):
            print(f"  {i:2}. [{l['check']}] {l['text']}")
        bad = sum(l["check"] == "bad" for l in d["lines"])
        print(f"완료 · 확인 필요 {bad}줄" if bad else "완료 · 모두 통과")


if __name__ == "__main__":
    main()
