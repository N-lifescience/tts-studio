"""에피소드(프로젝트)·목소리 저장. DB 없이 폴더 + JSON.

projects/<id>/project.json   대본·줄·설정
projects/<id>/takes/*.wav    줄별 테이크 (24kHz 원본)
projects/<id>/export/        내보내기 결과 사본
voices/<이름>.wav + .txt     목소리 샘플 + 그 샘플의 대본
"""

import copy
import json
import re
import secrets
import shutil
import threading
from datetime import datetime

from . import check, config
from .textsplit import join_script, split_script

LOCK = threading.RLock()  # project.json 읽고 쓰기는 전부 이 잠금 안에서

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VOICE_RE = re.compile(r"^[0-9A-Za-z가-힣_-]{1,40}$")


def now():
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}{secrets.token_hex(4)}"


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


# ── 프로젝트 ──────────────────────────────────────────────


def _dir(pid):
    if not _ID_RE.match(pid or ""):
        raise NotFound(pid)
    return config.PROJECTS_DIR / pid


def _path(pid):
    return _dir(pid) / "project.json"


def list_projects():
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in config.PROJECTS_DIR.glob("*/project.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        out.append({"id": d["id"], "title": d["title"], "updated": d["updated"], "lines": len(d["lines"])})
    return sorted(out, key=lambda x: x["updated"], reverse=True)


def load(pid):
    with LOCK:
        p = _path(pid)
        if not p.exists():
            raise NotFound(pid)
        d = json.loads(p.read_text(encoding="utf-8"))
        # 설정 키가 나중에 늘어나도 옛 프로젝트가 깨지지 않게
        s = copy.deepcopy(config.DEFAULT_SETTINGS)
        s.update({k: v for k, v in d.get("settings", {}).items() if k != "subtitle"})
        s["subtitle"].update(d.get("settings", {}).get("subtitle", {}))
        d["settings"] = s
        return d


def save(d):
    with LOCK:
        d["updated"] = now()
        p = _path(d["id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        return d


def create_project(title, script=""):
    title = (title or "").strip() or "새 에피소드"
    with LOCK:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:30] or "ep"
        pid = base
        while (config.PROJECTS_DIR / pid).exists():
            pid = f"{base}-{secrets.token_hex(2)}"
        (config.PROJECTS_DIR / pid / "takes").mkdir(parents=True)
        d = {
            "id": pid,
            "title": title,
            "created": now(),
            "updated": now(),
            "settings": copy.deepcopy(config.DEFAULT_SETTINGS),
            "lines": [],
        }
        if not voice_exists(d["settings"]["voice"]):
            vs = list_voices()
            d["settings"]["voice"] = vs[0]["name"] if vs else ""
        set_script(d, script)
        return save(d)


def delete_project(pid):
    with LOCK:
        d = _dir(pid)
        if not (d / "project.json").exists():
            raise NotFound(pid)
        shutil.rmtree(d)


def script_of(d):
    return join_script([(l["para"], l["text"]) for l in d["lines"]])


def new_line(para, text):
    return {
        "id": new_id("l"),
        "para": para,
        "text": text,
        "voice": None,  # None = 에피소드 기본 목소리
        "speed": 1.0,
        "gap": None,  # None = 기본 쉼 (문장/문단)
        "takes": [],
        "chosen": None,
        "ignore_check": False,
        "status": "idle",
        "error": None,
    }


def set_script(d, script):
    """대본을 다시 나눈다. 글자가 같은 줄은 설정·테이크를 그대로 이어받는다."""
    old = list(d["lines"])
    used = set()
    lines = []
    for para, text in split_script(script or ""):
        match = next((l for l in old if l["id"] not in used and l["text"] == text), None)
        if match:
            used.add(match["id"])
            match["para"] = para
            lines.append(match)
        else:
            lines.append(new_line(para, text))
    for l in old:
        if l["id"] not in used:
            _delete_take_files(d, l["takes"])
    d["lines"] = lines
    return d


def _delete_take_files(d, takes):
    for t in takes:
        f = _dir(d["id"]) / t["file"]
        f.unlink(missing_ok=True)


def find_line(d, lid):
    for l in d["lines"]:
        if l["id"] == lid:
            return l
    raise NotFound(lid)


def line_voice(d, line):
    return line["voice"] or d["settings"]["voice"]


def valid_takes(d, line):
    """지금 글자·목소리로 만든 테이크만."""
    v = line_voice(d, line)
    return [t for t in line["takes"] if t["text"] == line["text"] and t["voice"] == v]


def chosen_take(d, line):
    vt = valid_takes(d, line)
    for t in vt:
        if t["id"] == line["chosen"]:
            return t
    return None


def take_path(d, take):
    return _dir(d["id"]) / take["file"]


def _judge(take):
    """판정은 저장된 거리로 매번 다시 한다 (기준을 바꿔도 옛 테이크가 같은 기준으로 보이게)."""
    if take.get("distance") is None or take.get("heard") is None:
        return take
    return {**take, **check.score(take["text"], take["heard"])}


def line_view(d, line):
    """화면에 보낼 모양: 지금 유효한 테이크와 판정 포함."""
    out = dict(line)
    out["takes"] = [_judge(t) for t in valid_takes(d, line)]
    ct = chosen_take(d, line)
    ct = _judge(ct) if ct else None
    out["chosen"] = ct["id"] if ct else None
    out["voice_used"] = line_voice(d, line)
    if ct is None:
        out["check"] = "none"
    elif ct.get("ok") is None:
        out["check"] = "pending"
    elif ct["ok"] or line["ignore_check"]:
        out["check"] = "ok"
    else:
        out["check"] = "bad"
    return out


def project_view(d):
    out = {k: v for k, v in d.items() if k != "lines"}
    out["lines"] = [line_view(d, l) for l in d["lines"]]
    out["script"] = script_of(d)
    return out


def prune_takes(d, line, keep=8):
    """오래된 테이크 정리: 유효 테이크는 최근 keep 개 + 채택본, 무효(옛 글자/목소리) 테이크는 3개까지."""
    vt = valid_takes(d, line)
    stale = [t for t in line["takes"] if t not in vt]
    drop = [t for t in vt[:-keep] if t["id"] != line["chosen"]] + stale[:-3]
    if drop:
        _delete_take_files(d, drop)
        ids = {t["id"] for t in drop}
        line["takes"] = [t for t in line["takes"] if t["id"] not in ids]


# ── 목소리 ────────────────────────────────────────────────


def check_voice_name(name):
    if not _VOICE_RE.match(name or ""):
        raise BadRequest("목소리 이름은 한글·영문·숫자·_- 로 40자 이내")
    return name


def voice_exists(name):
    return bool(name) and _VOICE_RE.match(name) and (config.VOICES_DIR / f"{name}.wav").exists()


def voice_paths(name):
    check_voice_name(name)
    return config.VOICES_DIR / f"{name}.wav", config.VOICES_DIR / f"{name}.txt"


def list_voices():
    config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for w in sorted(config.VOICES_DIR.glob("*.wav")):
        if not _VOICE_RE.match(w.stem):
            continue
        t = w.with_suffix(".txt")
        import soundfile as sf

        out.append({
            "name": w.stem,
            "text": t.read_text(encoding="utf-8").strip() if t.exists() else "",
            "duration": round(sf.info(str(w)).duration, 2),
            "updated": datetime.fromtimestamp(w.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return out


def voice_usage(name):
    used = []
    for p in list_projects():
        d = load(p["id"])
        if d["settings"]["voice"] == name or any(l["voice"] == name for l in d["lines"]):
            used.append(d["title"])
    return used
