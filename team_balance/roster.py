"""내전 확정 명단 텍스트 → 참여자 목록

서버마다 명단 양식이 달라서 최대한 느슨하게 읽어요. 한 줄 = 한 명이고,
줄 끝에 붙은 포지션을 앞에서부터 주 포지션, 부 포지션으로 봐요.

    1. Hide on bush#KR1 미드/탑
    - 닉네임#KR1 (정글, 서폿)
    닉네임 주:원딜 부:서폿
    닉네임 올라운더
"""
from __future__ import annotations

import re
from dataclasses import dataclass

POSITIONS = ("탑", "정글", "미드", "원딜", "서폿")
FILL = "*"   # 아무 포지션이나 가능

_ALIASES = {
    "탑": ["탑", "top"],
    "정글": ["정글", "정글러", "jg", "jgl", "jug", "jungle"],
    "미드": ["미드", "mid", "middle"],
    "원딜": ["원딜", "바텀", "원거리딜러", "ad", "adc", "bot", "bottom"],
    "서폿": ["서폿", "서포터", "서포트", "sup", "supp", "support", "utility"],
    FILL: ["올", "올라운더", "올포지션", "상관없음", "아무거나", "무관", "자유", "fill", "all", "any"],
}
POS_ALIAS = {a.lower(): pos for pos, names in _ALIASES.items() for a in names}

# 닉네임과 포지션 사이, 포지션끼리 사이에 올 수 있는 구분 문자
_SEP = r"\s/,|()\[\]{}·:：~>\-"
_ALT = "|".join(re.escape(a) for a in sorted(POS_ALIAS, key=len, reverse=True))
# 줄 끝의 포지션 하나 ('주:원딜', '(서폿)' 같은 꼴 포함)
_TAIL = re.compile(rf"(?:^|[{_SEP}]+)(?:(?:주|부|메인|서브|main|sub)\s*[:：]?\s*)?({_ALT})[{_SEP}]*$", re.I)
# 줄 앞의 번호·글머리표 ('1.', '10)', '-', '•')
_BULLET = re.compile(r"^(?:\d{1,2}\s*[.)\]:]\s*|[-*•·▶▷►]\s*)+")
_TRAIL_SEP = re.compile(rf"[{_SEP}]+$")
_KR1 = re.compile(r"#kr1$", re.I)


def normalize_riot_id(name: str) -> str:
    """라이엇 기본 태그 KR1은 대소문자만 다른 같은 태그라 KR1로 통일해요 (닉#kr1 → 닉#KR1). 다른 태그는 그대로"""
    return _KR1.sub("#KR1", name.strip())


class RosterError(ValueError):
    """명단을 팀으로 나눌 수 없을 때 (인원 수, 중복 등). 메시지는 그대로 사용자에게 보여줘도 돼요"""


@dataclass(frozen=True)
class RosterEntry:
    name: str                      # 명단에 적힌 롤 닉네임 (DB 조회 키)
    positions: tuple[str, ...]     # 앞에서부터 주 포지션, 부 포지션
    fill: bool = False             # '올라운더' 등 — 어느 포지션이든 괜찮음
    line_no: int = 0


def parse_line(line: str, line_no: int = 0) -> RosterEntry | None:
    """한 줄을 읽어요. 사람이 아닌 줄(빈 줄, '확정 명단:' 같은 제목)은 None"""
    text = _BULLET.sub("", line.strip()).strip()
    if not re.search(r"\w", text) or text.endswith((":", "：")):
        return None
    found = []
    while True:
        m = _TAIL.search(text)
        if not m:
            break
        rest = text[:m.start()]
        if not _TRAIL_SEP.sub("", rest).strip():
            break   # 남는 게 없으면 이 단어는 포지션이 아니라 닉네임 ('미드 정글' → 닉네임 '미드')
        found.append(POS_ALIAS[m.group(1).lower()])
        text = rest
    found.reverse()
    positions = tuple(dict.fromkeys(p for p in found if p != FILL))
    return RosterEntry(name=normalize_riot_id(_TRAIL_SEP.sub("", text)), positions=positions, fill=FILL in found, line_no=line_no)


def parse_roster(text: str) -> list[RosterEntry]:
    entries = []
    for i, line in enumerate(text.splitlines(), 1):
        e = parse_line(line, i)
        if e:
            entries.append(e)
    return entries
