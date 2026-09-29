"""자막: srt 와 초록 배경 자막 영상(루마퓨전 크로마키용).

설치된 ffmpeg 에 자막 필터(libass)가 없어서 Pillow 로 자막 그림을 그리고
ffmpeg concat 으로 시간에 맞춰 이어 붙인다.
"""

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(cues):
    """cues: [(시작, 끝, 텍스트), ...]"""
    return "\n".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1))


def _font(size):
    if config.FONT_PATH is None:  # 한글 글꼴을 못 찾으면 Pillow 기본 글꼴 (한글은 깨질 수 있다)
        return ImageFont.load_default(size)
    return ImageFont.truetype(config.FONT_PATH, size, index=config.FONT_INDEX_BOLD)


def wrap(text, font, max_w):
    """픽셀 폭에 맞춰 줄바꿈. 띄어쓰기에서 먼저 끊고, 안 되면 글자 단위로."""
    lines, cur = [], ""
    for word in text.split(" "):
        cand = f"{cur} {word}".strip()
        if font.getlength(cand) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        cur = ""
        for ch in word:
            if font.getlength(cur + ch) > max_w and cur:
                lines.append(cur)
                cur = ""
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def balanced_wrap(text, font, max_w):
    """줄 수는 그대로 두고 줄 길이를 고르게 (\"…한 번 / 뜯어보겠습니다\" 처럼 한쪽만 짧지 않게)."""
    lines = wrap(text, font, max_w)
    if len(lines) < 2:
        return lines
    lo, hi = max_w / len(lines) * 0.8, max_w
    for _ in range(12):
        mid = (lo + hi) / 2
        if len(wrap(text, font, mid)) == len(lines):
            hi = mid
        else:
            lo = mid
    return wrap(text, font, hi)


def render(text, st, transparent_bg=False):
    """자막 한 장. st = settings['subtitle']"""
    W, H = int(st["width"]), int(st["height"])
    bg = (0, 0, 0, 0) if transparent_bg else st["background"]
    img = Image.new("RGBA" if transparent_bg else "RGB", (W, H), bg)
    if not text:
        return img
    font = _font(int(st["font_size"]))
    lines = balanced_wrap(text, font, W * 0.86)
    line_h = int(st["font_size"] * 1.3)
    block_h = line_h * len(lines)
    margin = int(st["margin"])
    y = {"top": margin, "middle": (H - block_h) // 2}.get(st["position"], H - margin - block_h)
    d = ImageDraw.Draw(img)
    for ln in lines:
        w = font.getlength(ln)
        d.text(
            ((W - w) / 2, y), ln, font=font, fill=st["color"],
            stroke_width=int(st["outline"]), stroke_fill=st["outline_color"],
        )
        y += line_h
    return img


def make_video(cues, total, st, dst: Path, fps=30):
    """초록 배경 자막 영상 (소리 없음). 길이 = 나레이션 길이."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        render("", st).save(tmp / "blank.png")
        entries, t = [], 0.0
        for i, (a, b, text) in enumerate(cues):
            if a > t:
                entries.append(("blank.png", a - t))
            render(text, st).save(tmp / f"s{i}.png")
            entries.append((f"s{i}.png", b - a))
            t = b
        if total > t:
            entries.append(("blank.png", total - t))
        lst = "".join(f"file '{f}'\nduration {d:.3f}\n" for f, d in entries)
        lst += f"file '{entries[-1][0]}'\n"  # concat 은 마지막 duration 을 쓰려면 한 번 더 적어야 한다
        (tmp / "list.txt").write_text(lst)
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y",
             "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-g", str(fps), "-t", f"{total:.3f}", "-movflags", "+faststart", str(dst)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"자막 영상 실패: {r.stderr[-400:]}")
