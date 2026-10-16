"""참여자 실력 점수

내전 기록이 없으면 솔랭 티어로, 기록이 쌓일수록 내전 MMR 쪽으로 옮겨가요.

    점수 = n/(n+k) × 내전 MMR + k/(n+k) × 솔랭 환산 MMR   (n = 내전 판수)

내전 MMR은 모두 같은 값(2000)에서 시작하니까 1~2판 친 사람의 MMR은 실력보다
시작값에 가까워요. 그래서 판수가 적을 때는 솔랭을 더 믿어요.
"""
from __future__ import annotations

from dataclasses import dataclass

_TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
_APEX = ("MASTER", "GRANDMASTER", "CHALLENGER")   # 디비전 없이 LP로만 구분
_KO = {
    "아이언": "IRON", "브론즈": "BRONZE", "실버": "SILVER", "골드": "GOLD",
    "플래티넘": "PLATINUM", "플레티넘": "PLATINUM", "에메랄드": "EMERALD",
    "다이아몬드": "DIAMOND", "다이아": "DIAMOND", "마스터": "MASTER",
    "그랜드마스터": "GRANDMASTER", "그마": "GRANDMASTER", "챌린저": "CHALLENGER",
}
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


@dataclass(frozen=True)
class PlayerRecord:
    """명단의 닉네임 하나에 대한 유저 정보. 내전 기록은 DB(find_players)에서, 솔랭은 라이엇 API(riot.py)에서 채워요"""
    key: str | None = None              # 유저 식별 키 (players.public_key). 미등록 유저는 None
    mmr: float | None = None            # 내전 MMR (사이트와 같은 값)
    games: int = 0                      # 내전 판수
    puuid: str | None = None            # 라이엇 계정 ID (솔랭 조회용)
    solo_tier: str | None = None        # 'DIAMOND' 또는 '다이아몬드'. 언랭이면 None
    solo_division: str | int | None = None   # 'IV' 또는 4
    solo_lp: int | None = None


@dataclass(frozen=True)
class RatingConfig:
    start_mmr: float = 2000      # 내전 MMR 시작값 (사이트 CONFIG.START_MMR과 같게)
    blend_games: float = 5       # k — 이 판수가 되면 내전 MMR과 솔랭을 반반 믿어요
    solo_until_games: int = 20   # 내전 판수가 이만큼 쌓이면 솔랭은 안 봐요 (라이엇 API 조회도 안 해요)
    # 솔랭 → 내전 MMR 환산: 서버 평균쯤 되는 솔랭 티어를 start_mmr에 맞추고, 차이에 배율을 곱해요.
    # 기본값은 에메랄드 4 0LP = 2000. 솔랭·내전 기록이 둘 다 있는 사람이 쌓이면 두 값을 보정하세요.
    solo_anchor: float = 2000    # solo_ladder('EMERALD', 4, 0)
    solo_scale: float = 0.5      # 솔랭 한 디비전(100) 차이 = 내전 MMR 50 차이


@dataclass(frozen=True)
class Rating:
    value: float
    source: str    # '내전' | '혼합' | '솔랭' | '기본값'


def solo_ladder(tier, division=None, lp=None) -> float | None:
    """솔랭 티어를 한 줄 점수로 (아이언 4 0LP = 0, 디비전마다 +100, 마스터 0LP = 2800)"""
    if not tier:
        return None
    t = str(tier).strip()
    t = _KO.get(t, t.upper())
    lp = float(lp or 0)
    if t in _APEX:
        return len(_TIERS) * 400 + lp
    if t not in _TIERS:
        return None   # 'UNRANKED' 등
    return _TIERS.index(t) * 400 + (4 - _division(division)) * 100 + min(lp, 100)


def _division(v) -> int:
    s = str(v if v is not None else "").strip().upper()
    if s in _ROMAN:
        return _ROMAN[s]
    try:
        d = int(s)
    except ValueError:
        return 4
    return d if 1 <= d <= 4 else 4


def solo_to_mmr(ladder: float, cfg: RatingConfig) -> float:
    return cfg.start_mmr + (ladder - cfg.solo_anchor) * cfg.solo_scale


def rate(record: PlayerRecord | None, cfg: RatingConfig | None = None) -> Rating:
    cfg = cfg or RatingConfig()
    if record is None:
        return Rating(cfg.start_mmr, "기본값")
    n = record.games or 0
    ladder = solo_ladder(record.solo_tier, record.solo_division, record.solo_lp) if n < cfg.solo_until_games else None
    solo = solo_to_mmr(ladder, cfg) if ladder is not None else None
    inner = record.mmr if n > 0 and record.mmr is not None else None
    if inner is None and solo is None:
        return Rating(cfg.start_mmr, "기본값")
    if inner is None:
        return Rating(solo, "솔랭")
    if solo is None:
        return Rating(inner, "내전")
    w = n / (n + cfg.blend_games)
    return Rating(w * inner + (1 - w) * solo, "혼합")
