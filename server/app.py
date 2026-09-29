"""TTS 작업실 서버. 이 맥(127.0.0.1)에서만 열린다.

    .venv/bin/python -m server.app   (보통은 ./studio 로 켠다)
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import audio, config, engine, exporter, importer, store, subtitles, worker

HOST = "127.0.0.1"
PORT = int(os.environ.get("STUDIO_PORT", "7870"))
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

@asynccontextmanager
async def lifespan(app):
    config.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    worker.start()
    yield


app = FastAPI(title="TTS 작업실", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
       "media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; object-src 'none'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


@app.middleware("http")
async def guard(request: Request, call_next):
    # 다른 사이트가 브라우저를 통해 이 서버를 부르는 것(DNS 리바인딩·CSRF)을 막는다
    host = request.headers.get("host", "")
    if host not in ALLOWED_HOSTS and not os.environ.get("STUDIO_TESTING"):
        return JSONResponse({"detail": "허용되지 않은 주소"}, status_code=403)
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD") and origin and origin.split("://", 1)[-1] not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "허용되지 않은 출처"}, status_code=403)
    try:
        resp = await call_next(request)
    except store.NotFound:
        resp = JSONResponse({"detail": "없음"}, status_code=404)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@app.exception_handler(store.NotFound)
async def _nf(request, exc):
    return JSONResponse({"detail": "없음"}, status_code=404)


@app.exception_handler(store.BadRequest)
async def _br(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(importer.ImportError_)
async def _ie(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(exporter.NotReady)
async def _nr(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=409)


# ── 상태·이벤트 ──────────────────────────────────────────


@app.get("/api/status")
def status():
    return {
        **worker.queue_state(),
        "export_root": str(config.EXPORT_ROOT),
        "icloud": config.EXPORT_IS_ICLOUD,
        "engine": engine.describe(),
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "peak_memory_gb": engine.peak_memory_gb() if engine.status["tts"] == "ready" else None,
    }


@app.get("/api/events")
async def events(request: Request):
    sub = worker.subscribe()

    async def stream():
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(sub[1].get(), timeout=15)
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            worker.unsubscribe(sub)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ── 에피소드 ──────────────────────────────────────────────


class NewProject(BaseModel):
    title: str = Field("", max_length=100)
    script: str = Field("", max_length=100_000)


class ProjectPatch(BaseModel):
    title: str | None = Field(None, max_length=100)
    settings: dict | None = None


class ScriptBody(BaseModel):
    script: str = Field(..., max_length=100_000)


class LinePatch(BaseModel):
    text: str | None = Field(None, max_length=1000)
    voice: str | None = None
    speed: float | None = Field(None, ge=0.5, le=2.0)
    gap: float | None = Field(None, ge=0, le=10)
    reset_gap: bool = False
    reset_voice: bool = False
    chosen: str | None = None
    ignore_check: bool | None = None


_SETTING_TYPES = {"voice": str, "temperature": float, "sentence_gap": float, "para_gap": float, "lufs": float}
_SUB_TYPES = {"font_size": int, "position": str, "margin": int, "color": str, "outline": int,
              "outline_color": str, "background": str, "width": int, "height": int}


def _clean_settings(cur, patch):
    for k, v in patch.items():
        if k == "subtitle" and isinstance(v, dict):
            for sk, sv in v.items():
                if sk in _SUB_TYPES:
                    try:
                        cur["subtitle"][sk] = _SUB_TYPES[sk](sv)
                    except (TypeError, ValueError):
                        raise store.BadRequest(f"자막 설정 {sk} 값이 이상합니다")
        elif k in _SETTING_TYPES:
            try:
                cur[k] = _SETTING_TYPES[k](v)
            except (TypeError, ValueError):
                raise store.BadRequest(f"설정 {k} 값이 이상합니다")
    s = cur["subtitle"]
    if s["position"] not in ("top", "middle", "bottom"):
        raise store.BadRequest("자막 위치는 top/middle/bottom")
    for key in ("color", "outline_color", "background"):
        if not (isinstance(s[key], str) and len(s[key]) == 7 and s[key][0] == "#"):
            raise store.BadRequest("색은 #RRGGBB")
    s["font_size"] = max(20, min(200, s["font_size"]))
    s["outline"] = max(0, min(20, s["outline"]))
    cur["temperature"] = max(0.1, min(1.5, cur["temperature"]))
    cur["lufs"] = max(-30.0, min(-8.0, cur["lufs"]))
    if cur["voice"] and not store.voice_exists(cur["voice"]):
        raise store.BadRequest("그런 목소리가 없습니다")
    return cur


@app.get("/api/projects")
def projects():
    return store.list_projects()


@app.post("/api/projects")
def create_project(body: NewProject):
    return store.project_view(store.create_project(body.title, body.script))


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return store.project_view(store.load(pid))


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch):
    with store.LOCK:
        d = store.load(pid)
        if body.title is not None:
            d["title"] = body.title.strip() or d["title"]
        if body.settings:
            d["settings"] = _clean_settings(d["settings"], body.settings)
        store.save(d)
        return store.project_view(d)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    worker.cancel(pid)
    store.delete_project(pid)
    return {"ok": True}


@app.put("/api/projects/{pid}/script")
def put_script(pid: str, body: ScriptBody):
    with store.LOCK:
        d = store.load(pid)
        store.set_script(d, body.script)
        store.save(d)
        return store.project_view(d)


@app.patch("/api/projects/{pid}/lines/{lid}")
def patch_line(pid: str, lid: str, body: LinePatch):
    with store.LOCK:
        d = store.load(pid)
        l = store.find_line(d, lid)
        if body.text is not None:
            t = " ".join(body.text.split())
            if not t:
                raise store.BadRequest("빈 줄은 대본 편집에서 지우세요")
            if t != l["text"]:
                l["text"], l["chosen"], l["ignore_check"] = t, None, False
                # 예전에 같은 글자로 만든 테이크가 남아 있으면 그걸 다시 채택
                vt = store.valid_takes(d, l)
                if vt:
                    l["chosen"] = vt[-1]["id"]
        if body.reset_voice:
            l["voice"] = None
        elif body.voice is not None:
            if not store.voice_exists(body.voice):
                raise store.BadRequest("그런 목소리가 없습니다")
            l["voice"] = None if body.voice == d["settings"]["voice"] else body.voice
        if body.voice is not None or body.reset_voice:
            vt = store.valid_takes(d, l)
            if not any(t["id"] == l["chosen"] for t in vt):
                l["chosen"] = vt[-1]["id"] if vt else None
        if body.speed is not None:
            l["speed"] = round(body.speed, 2)
        if body.reset_gap:
            l["gap"] = None
        elif body.gap is not None:
            l["gap"] = round(body.gap, 2)
        if body.chosen is not None:
            if not any(t["id"] == body.chosen for t in store.valid_takes(d, l)):
                raise store.BadRequest("그 테이크는 지금 줄과 맞지 않습니다")
            l["chosen"] = body.chosen
        if body.ignore_check is not None:
            l["ignore_check"] = body.ignore_check
        store.save(d)
        return store.line_view(d, l)


@app.post("/api/projects/{pid}/lines/{lid}/generate")
def generate_line(pid: str, lid: str, manual: bool = True):
    """manual=True: 이미 있어도 새 테이크. False: 없을 때만."""
    d = store.load(pid)
    store.find_line(d, lid)
    worker.enqueue(pid, [lid], manual=manual)
    return worker.queue_state()


@app.post("/api/projects/{pid}/generate")
def generate_all(pid: str, redo: bool = False):
    """redo=False: 아직 없는 줄만. True: 모든 줄을 새 테이크로 (예전 테이크는 골라 쓸 수 있게 남는다)."""
    d = store.load(pid)
    todo = [l["id"] for l in d["lines"] if redo or store.chosen_take(d, l) is None]
    added = worker.enqueue(pid, todo, manual=redo)
    return {**worker.queue_state(), "added": added}


@app.post("/api/projects/{pid}/cancel")
def cancel(pid: str):
    return {"cancelled": worker.cancel(pid)}


@app.get("/api/projects/{pid}/takes/{tid}")
def take_audio(pid: str, tid: str):
    d = store.load(pid)
    for l in d["lines"]:
        for t in l["takes"]:
            if t["id"] == tid:
                return FileResponse(store.take_path(d, t), media_type="audio/wav")
    raise store.NotFound(tid)


@app.post("/api/projects/{pid}/preview")
def make_preview(pid: str):
    d = store.load(pid)
    dst = store._dir(pid) / "preview.wav"
    info = exporter.preview(d, dst)
    return {**info, "url": f"/api/projects/{pid}/preview.wav?v={int(dst.stat().st_mtime * 1000)}"}


@app.get("/api/projects/{pid}/preview.wav")
def get_preview(pid: str):
    f = store._dir(pid) / "preview.wav"
    if not f.exists():
        raise store.NotFound(pid)
    return FileResponse(f, media_type="audio/wav")


@app.post("/api/projects/{pid}/export")
def export(pid: str):
    started = worker.start_export(pid)
    return {"started": started}


@app.get("/api/projects/{pid}/export")
def export_info(pid: str):
    d = store.load(pid)
    out = store._dir(pid) / "export"
    folder = exporter.folder_name(d)
    if not out.exists():
        return {"exists": False, "folder": folder}
    return {
        "exists": True,
        "folder": folder,
        "local": str(out),
        "icloud": str(config.EXPORT_ROOT / folder) if (config.EXPORT_ROOT / folder).exists() else None,
        "files": sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()),
    }


@app.get("/api/projects/{pid}/export/file")
def export_file(pid: str, path: str):
    out = (store._dir(pid) / "export").resolve()
    f = (out / path).resolve()
    if out not in f.parents or not f.is_file():
        raise store.NotFound(path)
    return FileResponse(f, filename=f.name)


@app.post("/api/projects/{pid}/reveal")
def reveal(pid: str, where: str = "icloud"):
    """내보낸 폴더를 Finder 로 연다."""
    d = store.load(pid)
    target = (config.EXPORT_ROOT / exporter.folder_name(d)) if where == "icloud" else store._dir(pid) / "export"
    if not target.exists():
        raise store.NotFound(str(target))
    _open_folder(target)
    return {"ok": True}


def _open_folder(target: Path):
    if sys.platform == "win32":
        os.startfile(str(target))  # 탐색기
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(target)], check=False)


@app.get("/api/projects/{pid}/subtitle-preview.png")
def subtitle_preview(pid: str, text: str = "자막 미리보기입니다"):
    d = store.load(pid)
    img = subtitles.render(text[:200], d["settings"]["subtitle"])
    img.thumbnail((960, 540))
    buf = BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


# ── 대본 불러오기 ─────────────────────────────────────────


def _read_upload(file: UploadFile):
    data = b""
    while chunk := file.file.read(1 << 20):
        data += chunk
        if len(data) > importer.MAX_BYTES:
            raise store.BadRequest("파일이 너무 큽니다 (30MB 이하)")
    return data


@app.post("/api/import/parse")
def import_parse(file: UploadFile = File(...)):
    """Word·PDF·텍스트 파일 → 대본 글자 (대본 탭 '파일에서 불러오기'). 저장은 하지 않는다."""
    text = importer.extract_text(_read_upload(file), file.filename or "")
    return {"text": text, "title": importer.title_from(file.filename or ""), "lines": len(text.splitlines())}


@app.post("/api/projects/import")
def import_project(
    file: UploadFile | None = File(None),
    text: str = Form(""),
    title: str = Form(""),
    generate: bool = Form(True),
    export: bool = Form(False),
):
    """파일이나 글자로 에피소드를 바로 만든다 (Claude 가 드라이브 문서를 넣을 때 쓰는 창구).
    generate: 음성까지 생성, export: 생성이 끝나면 내보내기까지."""
    if file is not None and file.filename:
        text = importer.extract_text(_read_upload(file), file.filename)
        title = title or importer.title_from(file.filename)
    if not text.strip():
        raise store.BadRequest("대본이 비어 있습니다")
    d, _ = importer.import_script(text[:100_000], (title or "새 에피소드")[:100])
    worker.publish({"type": "projects"})
    if generate or export:
        worker._after_import(d, {"auto_generate": generate, "auto_export": export})
    return store.project_view(store.load(d["id"]))


class InboxSettings(BaseModel):
    folder: str = Field("", max_length=1000)
    auto_generate: bool = True
    auto_export: bool = False


@app.get("/api/inbox")
def inbox():
    return {"settings": importer.load_settings(), "suggestions": importer.drive_folders(), **importer.state}


@app.put("/api/inbox")
def put_inbox(body: InboxSettings):
    folder = body.folder.strip()
    if folder:
        p = Path(folder).expanduser()
        if not p.is_absolute():
            raise store.BadRequest("폴더는 전체 경로로 적어 주세요")
        if not p.exists():
            if not p.parent.is_dir():
                raise store.BadRequest(f"그 위 폴더가 없습니다: {p.parent}")
            p.mkdir()  # 드라이브 안에 'TTS 대본' 폴더를 만들어 준다
        if not p.is_dir():
            raise store.BadRequest("폴더가 아닙니다")
        folder = str(p)
    importer.save_settings({"folder": folder, "auto_generate": body.auto_generate, "auto_export": body.auto_export})
    worker.scan_inbox()
    return inbox()


@app.post("/api/inbox/scan")
def scan_inbox_now():
    n = worker.scan_inbox()
    return {"imported": n, **inbox()}


@app.post("/api/inbox/reveal")
def reveal_inbox():
    folder = importer.load_settings()["folder"]
    if not folder or not Path(folder).is_dir():
        raise store.NotFound(folder)
    _open_folder(Path(folder))
    return {"ok": True}


# ── 목소리 ────────────────────────────────────────────────


class VoicePatch(BaseModel):
    text: str = Field(..., max_length=2000)


@app.get("/api/voices")
def voices():
    return store.list_voices()


@app.get("/api/voices/{name}/audio")
def voice_audio(name: str):
    wav, _ = store.voice_paths(name)
    if not wav.exists():
        raise store.NotFound(name)
    return FileResponse(wav, media_type="audio/wav")


@app.post("/api/voices")
def add_voice(name: str = Form(...), file: UploadFile = File(...), overwrite: bool = Form(False)):
    wav, txt = store.voice_paths(name)
    if wav.exists() and not overwrite:
        raise store.BadRequest("같은 이름의 목소리가 이미 있습니다")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "upload"
        size = 0
        with open(src, "wb") as f:
            while chunk := file.file.read(1 << 20):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise store.BadRequest("파일이 너무 큽니다 (50MB 이하)")
                f.write(chunk)
        new_wav = Path(tmp) / "voice.wav"
        try:
            duration = audio.import_voice(src, new_wav)
        except (RuntimeError, ValueError) as e:
            raise store.BadRequest(f"녹음 파일을 읽지 못했습니다: {e}")
        heard = engine.transcribe(new_wav)
        config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(new_wav), wav)
    txt.write_text(heard + "\n", encoding="utf-8")
    return {"name": name, "text": heard, "duration": round(duration, 2)}


@app.patch("/api/voices/{name}")
def patch_voice(name: str, body: VoicePatch):
    wav, txt = store.voice_paths(name)
    if not wav.exists():
        raise store.NotFound(name)
    txt.write_text(body.text.strip() + "\n", encoding="utf-8")
    return {"name": name, "text": body.text.strip()}


@app.delete("/api/voices/{name}")
def delete_voice(name: str):
    wav, txt = store.voice_paths(name)
    if not wav.exists():
        raise store.NotFound(name)
    used = store.voice_usage(name)
    if used:
        raise store.BadRequest(f"이 목소리를 쓰는 에피소드가 있어 지울 수 없어요: {', '.join(used)} — 그 에피소드의 목소리를 먼저 바꾸세요")
    wav.unlink()
    txt.unlink(missing_ok=True)
    return {"ok": True}


# ── 화면 ─────────────────────────────────────────────────

if config.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    index = config.WEB_DIST / "index.html"
    if path.startswith("api/"):
        raise HTTPException(404)
    if not index.exists():
        return Response("화면이 아직 빌드되지 않았습니다. ./studio 로 켜면 자동으로 빌드합니다.", media_type="text/plain; charset=utf-8")
    f = (config.WEB_DIST / path).resolve()
    if path and config.WEB_DIST.resolve() in f.parents and f.is_file():
        return FileResponse(f)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def main():
    import uvicorn

    # 브라우저가 진행 상황 연결(SSE)을 물고 있어도 Ctrl+C 에 바로 꺼지게
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning", timeout_graceful_shutdown=2)


if __name__ == "__main__":
    main()
