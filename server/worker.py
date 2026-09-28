"""생성 작업 줄 세우기 + 화면으로 진행 상황 보내기(SSE).

GPU 는 하나라 줄 생성은 작업 스레드 하나가 차례로 처리한다.
내보내기는 GPU 를 안 쓰므로 따로 돈다.
"""

import asyncio
import collections
import secrets
import threading
import traceback

import soundfile as sf

from . import audio, check, config, engine, exporter, store

# ── 이벤트 ────────────────────────────────────────────────

_subs = set()  # (loop, asyncio.Queue)
_subs_lock = threading.Lock()


def subscribe():
    loop = asyncio.get_running_loop()
    q = asyncio.Queue(maxsize=1000)
    with _subs_lock:
        _subs.add((loop, q))
    return (loop, q)


def unsubscribe(sub):
    with _subs_lock:
        _subs.discard(sub)


def publish(event):
    with _subs_lock:
        subs = list(_subs)
    for loop, q in subs:
        def put(q=q):
            if not q.full():
                q.put_nowait(event)
        try:
            loop.call_soon_threadsafe(put)
        except RuntimeError:  # 닫힌 루프
            pass


# ── 줄 생성 큐 ────────────────────────────────────────────

_q = collections.deque()
_cv = threading.Condition()
_current = None


def queue_state():
    with _cv:
        return {"pending": len(_q), "current": _current, "models": dict(engine.status)}


def _publish_queue():
    publish({"type": "queue", **queue_state()})


def _set_status(pid, lid, status, error=None):
    with store.LOCK:
        d = store.load(pid)
        l = store.find_line(d, lid)
        l["status"], l["error"] = status, error
        store.save(d)
        publish({"type": "line", "project": pid, "line": store.line_view(d, l)})


def enqueue(pid, lids, manual=False):
    added = 0
    with _cv:
        queued = {(j[0], j[1]) for j in _q}
        for lid in lids:
            if (pid, lid) in queued or (_current and _current[:2] == [pid, lid]):
                continue
            _q.append((pid, lid, manual))
            added += 1
        _cv.notify()
    for lid in lids:
        try:
            _set_status(pid, lid, "queued")
        except store.NotFound:
            pass
    _publish_queue()
    return added


def cancel(pid=None):
    with _cv:
        drop = [j for j in _q if pid is None or j[0] == pid]
        for j in drop:
            _q.remove(j)
    for p, lid, _ in drop:
        try:
            _set_status(p, lid, "idle")
        except store.NotFound:
            pass
    _publish_queue()
    return len(drop)


def _run_line(pid, lid, manual):
    d = store.load(pid)
    l = store.find_line(d, lid)
    if not manual and store.chosen_take(d, l):
        _set_status(pid, lid, "done")
        return
    text, voice = l["text"], store.line_voice(d, l)
    if not store.voice_exists(voice):
        raise RuntimeError(f"목소리 '{voice}' 가 없습니다")
    vwav, vtxt = store.voice_paths(voice)
    ref_text = vtxt.read_text(encoding="utf-8").strip() if vtxt.exists() else ""
    temperature = float(d["settings"]["temperature"])

    new = []
    for attempt in range(1, config.MAX_AUTO_ATTEMPTS + 1):
        _set_status(pid, lid, "generating")
        a = engine.generate(text, vwav, ref_text, temperature, secrets.randbits(31))
        tid = store.new_id("t")
        rel = f"takes/{lid}_{tid}.wav"
        sf.write(store._dir(pid) / rel, audio.trim_silence(a), config.SR)
        take = {"id": tid, "file": rel, "text": text, "voice": voice, "created": store.now(),
                "duration": round(len(a) / config.SR, 2), "attempt": attempt,
                "heard": None, "distance": None, "ok": None, "diff": None}

        _set_status(pid, lid, "checking")
        try:
            heard = engine.transcribe(store._dir(pid) / rel)
            take.update(heard=heard, **check.score(text, heard))
        except Exception as e:  # 검사 실패는 생성 실패가 아니다
            take["heard"] = f"(검사 실패: {e})"

        with store.LOCK:
            d = store.load(pid)
            l = store.find_line(d, lid)
            if l["text"] != text:  # 도중에 글자가 바뀌었으면 여기서 그만
                l["takes"].append(take)
                l["status"] = "idle"
                store.save(d)
                publish({"type": "line", "project": pid, "line": store.line_view(d, l)})
                return
            l["takes"].append(take)
            new.append(take)
            best = sorted(new, key=lambda t: (not t["ok"], t["distance"] if t["distance"] is not None else 99))[0]
            l["chosen"] = best["id"]
            store.prune_takes(d, l)
            store.save(d)
            publish({"type": "line", "project": pid, "line": store.line_view(d, l)})
        if take["ok"] is not False:  # 통과 또는 검사 불가 → 더 안 뽑는다
            break
    _set_status(pid, lid, "done")


def _loop():
    global _current
    while True:
        with _cv:
            while not _q:
                _cv.wait()
            pid, lid, manual = _q.popleft()
            _current = [pid, lid]
        _publish_queue()
        try:
            _run_line(pid, lid, manual)
        except store.NotFound:
            pass
        except Exception as e:
            traceback.print_exc()
            try:
                _set_status(pid, lid, "error", str(e)[:300])
            except store.NotFound:
                pass
        finally:
            with _cv:
                _current = None
            _publish_queue()


_started = False


def _idle_loop():
    import time

    while True:
        time.sleep(60)
        with _cv:
            busy = bool(_q) or _current is not None
        if not busy and engine.unload_if_idle():
            _publish_queue()


def start():
    global _started
    if not _started:
        _started = True
        threading.Thread(target=_loop, daemon=True, name="tts-worker").start()
        threading.Thread(target=_idle_loop, daemon=True, name="idle-unload").start()


# ── 내보내기 ──────────────────────────────────────────────

_exporting = set()


def start_export(pid):
    if pid in _exporting:
        return False
    d = store.load(pid)
    exporter.build(d)  # 안 만든 줄이 있으면 여기서 NotReady
    _exporting.add(pid)

    def run():
        try:
            res = exporter.export(
                d, progress=lambda m: publish({"type": "export", "project": pid, "state": "running", "message": m}))
            publish({"type": "export", "project": pid, "state": "done", "result": res})
        except Exception as e:
            traceback.print_exc()
            publish({"type": "export", "project": pid, "state": "error", "message": str(e)[:300]})
        finally:
            _exporting.discard(pid)

    threading.Thread(target=run, daemon=True, name=f"export-{pid}").start()
    return True
