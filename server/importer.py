"""대본 파일 불러오기: Word(.docx) · PDF · 텍스트 → 대본 글자, 그리고 '대본 폴더' 자동 불러오기.

대본 폴더는 보통 구글 드라이브 데스크톱 앱이 동기화하는 폴더 안의 한 폴더다.
드라이브에 파일을 올리면 이 컴퓨터로 내려오고, 앱이 그걸 보고 에피소드를 만든다
(원하면 음성 생성·내보내기까지). 구글 계정 연결이나 API 키가 필요 없다.
"""

import json
import re
import sys
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

from . import config, store

EXTS = (".docx", ".pdf", ".txt", ".md")
MAX_BYTES = 30 * 1024 * 1024
SETTINGS_FILE = config.ROOT / "studio-settings.json"  # 이 컴퓨터만의 설정 (저장소에 안 올림)
_lock = threading.RLock()


class ImportError_(Exception):
    pass


def _clean(lines):
    """줄 목록 정리: 앞뒤 공백, 쪽 번호만 있는 줄 제거, 빈 줄 여러 개는 하나로 (= 문단 구분)."""
    out = []
    for ln in lines:
        ln = re.sub(r"[ \t　\xa0]+", " ", ln).strip()
        if re.fullmatch(r"[-–—]?\s*\d{1,4}\s*[-–—]?|\d+\s*/\s*\d+", ln):
            continue
        if not ln and (not out or not out[-1]):
            continue
        out.append(ln)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


# 제작용 대본은 보통 표다 (타임코드 · 장면 · 나레이션 · 화면 · 자막 …). 이런 머리글의 열만 대본으로 쓴다.
NARRATION_HEADERS = ("나레이션", "내레이션", "narration", "대사", "녹음", "voice over", "vo")


def _narration_col(header_cells):
    for i, h in enumerate(header_cells):
        h = re.sub(r"\s+", " ", h).strip().lower()
        if any(k == h or (len(k) > 2 and k in h) for k in NARRATION_HEADERS):
            return i
    return None


def _split_sentences(text):
    """한 칸에 문장이 붙어 있으면 ('있습니다.사마귀입니다.') 문장마다 줄을 나눈다."""
    text = re.sub(r"(?<=[.?!…])(?=[^\s.?!…\"'”’)\]])", "\n", text)
    return [t.strip() for t in text.split("\n") if t.strip()]


def _docx(data):
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(BytesIO(data))
    body = doc.element.body
    blocks = [Table(el, doc) if el.tag.endswith("}tbl") else Paragraph(el, doc)
              for el in body.iterchildren() if el.tag.endswith(("}tbl", "}p"))]

    # 1) 나레이션 열이 있는 표가 있으면 그 열만 (표 하나 = 문단 하나)
    lines = []
    for b in blocks:
        if not isinstance(b, Table) or len(b.rows) < 2:
            continue
        col = _narration_col([c.text for c in b.rows[0].cells])
        if col is None:
            continue
        for row in b.rows[1:]:
            cells = row.cells
            if col < len(cells):
                for para in cells[col].paragraphs:
                    lines.extend(_split_sentences(para.text))
        lines.append("")
    if any(lines):
        return _clean(lines)

    # 2) 아니면 본문 단락 (단락 안 줄바꿈도 줄로, 빈 단락 = 문단 구분)
    for b in blocks:
        if isinstance(b, Paragraph):
            lines.extend(b.text.split("\n") if b.text.strip() else [""])
    return _clean(lines)


def _md_narration(text):
    """마크다운 표(드라이브에서 글자로 받은 제작 대본)에서 나레이션 열만. 없으면 None."""
    lines, rows, found = text.splitlines(), [], []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            col = _narration_col(header)
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                if col is not None:
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if col < len(cells):
                        cell = re.sub(r"\\(.)", r"\1", cells[col])  # 마크다운 이스케이프 풀기
                        rows.extend(_split_sentences(cell.replace("<br>", "\n")))
                i += 1
            if col is not None:
                found = True
                rows.append("")
            continue
        i += 1
    return _clean(rows) if found else None


_END = re.compile(r"[.?!…。」』\"'”’)]$")


def _pdf(data):
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as e:
        raise ImportError_(f"PDF 를 열 수 없습니다: {e}")
    if reader.is_encrypted:
        raise ImportError_("암호가 걸린 PDF 는 읽을 수 없습니다")
    raw = []
    for page in reader.pages:
        raw.extend((page.extract_text() or "").splitlines())
        raw.append("")
    if not any(ln.strip() for ln in raw):
        raise ImportError_("PDF 에 글자가 없습니다 (스캔 이미지 PDF 는 읽을 수 없습니다)")
    # PDF 는 화면 폭에서 줄이 꺾여 있으니, 문장 끝이 아닌 줄은 다음 줄과 이어 붙인다
    lines, buf = [], ""
    for ln in raw:
        ln = ln.strip()
        if not ln:
            if buf:
                lines.append(buf)
                buf = ""
            lines.append("")
            continue
        buf = f"{buf} {ln}".strip() if buf else ln
        if _END.search(buf):
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    return _clean(lines)


def _txt(data):
    for enc in ("utf-8-sig", "cp949", "utf-16"):
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        return _md_narration(text) or _clean(text.splitlines())
    raise ImportError_("글자 인코딩을 알 수 없습니다 (UTF-8 로 저장해 주세요)")


def extract_text(data, filename):
    ext = Path(filename).suffix.lower()
    if len(data) > MAX_BYTES:
        raise ImportError_("파일이 너무 큽니다 (30MB 이하)")
    if ext == ".docx":
        try:
            text = _docx(data)
        except Exception as e:
            raise ImportError_(f"Word 파일을 열 수 없습니다: {e}")
    elif ext == ".pdf":
        text = _pdf(data)
    elif ext in (".txt", ".md"):
        text = _txt(data)
    elif ext == ".doc":
        raise ImportError_("옛 Word(.doc) 는 못 읽습니다. Word 에서 .docx 로 다시 저장해 주세요")
    elif ext in (".hwp", ".hwpx"):
        raise ImportError_("한글 파일은 아직 못 읽습니다. .docx 나 PDF 로 저장해 주세요")
    else:
        raise ImportError_(f"{ext or '이 형식'} 은 못 읽습니다 (.docx · .pdf · .txt)")
    if not text.strip():
        raise ImportError_("파일에서 대본 글자를 찾지 못했습니다")
    return text


def title_from(filename):
    return re.sub(r"[_]+", " ", Path(filename).stem).strip()[:100] or "새 에피소드"


# ── 대본 폴더 (자동 불러오기) ────────────────────────────

DEFAULT_SETTINGS = {"folder": "", "auto_generate": True, "auto_export": False}
state = {"last_scan": None, "error": None, "recent": []}  # recent: 최근 불러온 것 (화면 표시용)


def load_settings():
    with _lock:
        s = dict(DEFAULT_SETTINGS)
        if SETTINGS_FILE.exists():
            try:
                s.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("inbox", {}))
            except Exception:
                pass
        return s


def save_settings(s):
    with _lock:
        all_ = {}
        if SETTINGS_FILE.exists():
            try:
                all_ = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                all_ = {}
        all_["inbox"] = {k: s[k] for k in DEFAULT_SETTINGS}
        SETTINGS_FILE.write_text(json.dumps(all_, ensure_ascii=False, indent=1), encoding="utf-8")


def drive_folders():
    """이 컴퓨터에서 구글 드라이브 데스크톱 앱 폴더 찾기 (추천용)."""
    found = []
    home = Path.home()
    cands = list((home / "Library" / "CloudStorage").glob("GoogleDrive-*"))  # 맥
    cands += [home / "Google Drive", home / "GoogleDrive"]
    if sys.platform == "win32":
        cands += [Path(f"{d}:/") for d in "GHIJKLMNOPQRSTUVWXYZ"]
    seen = set()
    for c in cands:
        for sub in ("내 드라이브", "My Drive"):
            p = c / sub
            try:
                if p.is_dir() and p.resolve() not in seen:  # 같은 곳을 가리키는 바로가기는 하나만
                    seen.add(p.resolve())
                    found.append(str(p / "TTS 대본"))
            except OSError:
                pass
    return found


def _registry_path():
    return config.PROJECTS_DIR / ".imports.json"


def _registry():
    p = _registry_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_registry(r):
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    _registry_path().write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def import_script(text, title, pid=None):
    """대본을 새 에피소드로. pid 가 살아 있으면 그 에피소드의 대본을 바꾼다 (같은 줄은 그대로 둔다)."""
    with store.LOCK:
        if pid:
            try:
                d = store.load(pid)
                store.set_script(d, text)
                return store.save(d), False
            except store.NotFound:
                pass
        return store.create_project(title, text), True


def scan(on_imported=None):
    """대본 폴더를 한 번 훑는다. 새 파일·바뀐 파일만 불러온다. → 불러온 개수"""
    s = load_settings()
    folder = Path(s["folder"]) if s["folder"] else None
    state["last_scan"] = datetime.now().isoformat(timespec="seconds")
    if not folder:
        state["error"] = None
        return 0
    if not folder.is_dir():
        state["error"] = f"폴더가 없습니다: {folder}"
        return 0
    state["error"] = None
    reg = _registry()
    n = 0
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in EXTS or f.name.startswith(("~$", ".")) or not f.is_file():
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        if time.time() - st.st_mtime < 5:  # 아직 내려받는 중일 수 있다
            continue
        key = str(f)
        prev = reg.get(key)
        if prev and prev.get("mtime") == st.st_mtime:
            continue
        entry = {"mtime": st.st_mtime, "file": f.name, "at": datetime.now().isoformat(timespec="seconds")}
        try:
            text = extract_text(f.read_bytes(), f.name)
            d, created = import_script(text, title_from(f.name), prev.get("pid") if prev else None)
            entry.update(pid=d["id"], title=d["title"], lines=len(d["lines"]), created=created, error=None)
            n += 1
            if on_imported:
                on_imported(d, s)
        except (ImportError_, OSError) as e:
            entry.update(pid=prev.get("pid") if prev else None, error=str(e))
        reg[key] = entry
        recent = {k: entry.get(k) for k in ("pid", "title", "lines", "created", "error", "at")}
        state["recent"] = ([{"file": f.name, **recent}] + [r for r in state["recent"] if r["file"] != f.name])[:20]
    _save_registry(reg)
    return n
