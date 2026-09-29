"""대본 → 줄(조각) 나누기."""

import re

MAX_CHARS = 120  # 이보다 긴 문장은 쉼표에서 나눈다 (길면 발음이 무너지기 쉽다)


def split_script(text):
    """빈 줄 = 문단, 줄바꿈·문장부호 = 조각 경계. [(문단번호, 텍스트), ...]"""
    chunks = []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for pi, para in enumerate(paras):
        for line in para.splitlines():
            # "…" 는 문장 안의 쉼이라 끊지 않는다 ("카직스는 보통… 메뚜기라고" 를 한 번에 읽어야 억양이 이어진다)
            for s in re.split(r"(?<=[.?!])\s+", line.strip()):
                s = s.strip()
                while len(s) > MAX_CHARS and "," in s[:MAX_CHARS]:
                    cut = s.rindex(",", 0, MAX_CHARS) + 1
                    chunks.append((pi, s[:cut]))
                    s = s[cut:].strip()
                if s:
                    chunks.append((pi, s))
    return chunks


def join_script(lines):
    """[(문단번호, 텍스트), ...] → 대본 텍스트 (줄마다 한 줄, 문단 사이 빈 줄)."""
    out, prev = [], None
    for para, text in lines:
        if prev is not None and para != prev:
            out.append("")
        out.append(text)
        prev = para
    return "\n".join(out)
