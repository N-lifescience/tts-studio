"""발음 검사: 음성인식 결과를 대본과 자모 단위로 비교한다.

글자 단위로 비교하면 "찢어내는→뛰어내는" 같은 진짜 오류와 "공허→공어"(ㅎ 탈락) 같은
소리 나는 대로의 받아쓰기가 똑같이 한 글자 차이로 잡힌다. 자모로 풀면 전자는 3, 후자는 1이라
구분이 된다.
"""

import difflib
import re

# 허용하는 자모 편집거리. 짧은 줄은 한두 자모가 곧 단어 하나라 더 엄격하게 본다
# ("사마귀→사막이" 는 2 인데 7글자 줄에서는 분명한 오류다).
SHORT_JAMO = 25


def allowed_distance(n_jamo):
    return 1 if n_jamo < SHORT_JAMO else 2

_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"


def normalize(text):
    """공백·문장부호를 없애고 영문은 소문자로. 한글·영문·숫자만 남긴다."""
    return "".join(re.findall(r"[가-힣a-z0-9]", text.lower()))


def to_jamo(text):
    out = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out.append(_CHO[code // 588])
            out.append(_JUNG[(code % 588) // 28])
            if code % 28:
                out.append(_JONG[code % 28])
        else:
            out.append(ch)
    return out


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def score(script_text, heard_text):
    """{'distance': 자모 편집거리, 'ok': bool, 'diff': [[대본 글자, 들린 글자], ...]}"""
    a, b = normalize(script_text), normalize(heard_text)
    ja = to_jamo(a)
    dist = edit_distance(ja, to_jamo(b))
    diff = []  # 화면 표시용: [대본 쪽 글자, 들린 글자] 가 다른 곳만
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            diff.append([a[i1:i2], b[j1:j2]])
    return {"distance": dist, "ok": dist <= allowed_distance(len(ja)), "diff": diff}
