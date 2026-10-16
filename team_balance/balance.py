"""밸런스 팀 구성

10명 → 5:5 두 팀 (3판 2선승). 한 팀은 5명이고 포지션이 하나씩 배정돼요.

팀 전력 = 실력 점수 합 − 포지션 손실 (부 포지션이면 조금, 신청 안 한 포지션이면 크게 빼요)
목표    = |두 팀 전력 차이| + comfort_weight × 전체 포지션 손실

나누는 경우의 수가 126개뿐이라 전부 따져요. 마지막에 최선과 tolerance 이내로 차이 나는
조합 중 하나를 무작위로 골라서 같은 멤버여도 매번 똑같은 팀이 나오지 않게 해요.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

from .roster import POSITIONS

MAIN, SUB, OFF = 0, 1, 2
LEVEL_NAME = {MAIN: "주", SUB: "부", OFF: "포지션 외"}
TEAM_SIZE = 5
PLAYER_COUNT = 10

_PERMS = list(itertools.permutations(range(TEAM_SIZE)))


@dataclass(frozen=True)
class Participant:
    name: str
    skill: float
    positions: tuple[str, ...] = ()   # 앞에서부터 주, 부
    fill: bool = False
    key: str | None = None
    source: str = ""                  # 실력 점수 출처 (rating.Rating.source)

    def level(self, pos: str) -> int:
        if self.fill or not self.positions or pos == self.positions[0]:
            return MAIN
        return SUB if pos in self.positions[1:] else OFF


@dataclass(frozen=True)
class BalanceConfig:
    sub_malus: float = 40         # 부 포지션에 서면 팀 전력에서 빼는 값
    off_malus: float = 150        # 신청하지 않은 포지션에 서면 빼는 값
    comfort_weight: float = 0.5   # 팀 간 차이와 별개로 포지션 손실 자체를 얼마나 줄일지
    tolerance: float = 30         # 최선과 이만큼 이내인 조합 중에서 무작위로 골라요


@dataclass(frozen=True)
class Slot:
    position: str
    participant: Participant
    level: int


@dataclass(frozen=True)
class Team:
    number: int
    slots: tuple[Slot, ...]   # POSITIONS 순서
    strength: float           # 실력 합 − 포지션 손실

    @property
    def average(self) -> float:
        return sum(s.participant.skill for s in self.slots) / len(self.slots)


@dataclass(frozen=True)
class BalanceResult:
    teams: tuple[Team, ...]
    spread: float      # 두 팀의 전력 차이
    sub_count: int     # 부 포지션에 선 인원
    off_count: int     # 신청하지 않은 포지션에 선 인원


def _assign(members: tuple[int, ...], cost) -> tuple[float, tuple[int, ...]]:
    """포지션 손실이 가장 적은 배정 — (손실, 배정). 배정[i]는 members[i]의 포지션 번호"""
    best_loss, best_perm = float("inf"), _PERMS[0]
    for perm in _PERMS:
        loss = sum(cost[m][p] for m, p in zip(members, perm))
        if loss < best_loss:
            best_loss, best_perm = loss, perm
            if loss == 0:
                break
    return best_loss, best_perm


def balance(players: list[Participant], cfg: BalanceConfig | None = None, seed=None) -> BalanceResult:
    cfg = cfg or BalanceConfig()
    if len(players) != PLAYER_COUNT:
        raise ValueError(f"팀 구성은 10명만 가능해요 (지금 {len(players)}명)")
    rng = random.Random(seed)
    malus = {MAIN: 0.0, SUB: cfg.sub_malus, OFF: cfg.off_malus}
    cost = [[malus[p.level(pos)] for pos in POSITIONS] for p in players]

    def team(members):
        loss, perm = _assign(members, cost)
        return sum(players[m].skill for m in members) - loss, loss, perm

    found = []
    for combo in itertools.combinations(range(1, PLAYER_COUNT), TEAM_SIZE - 1):
        a = (0,) + combo   # 0번 선수를 한쪽에 고정해서 같은 분할을 두 번 세지 않아요
        b = tuple(i for i in range(PLAYER_COUNT) if i not in a)
        ta, tb = team(a), team(b)
        score = abs(ta[0] - tb[0]) + cfg.comfort_weight * (ta[1] + tb[1])
        found.append((score, (a, ta), (b, tb)))

    best = min(f[0] for f in found)
    chosen = list(rng.choice([f for f in found if f[0] <= best + cfg.tolerance])[1:])
    rng.shuffle(chosen)   # 1팀·2팀 이름이 실력 순서를 드러내지 않게

    teams, sub_count, off_count = [], 0, 0
    for number, (members, (strength, _, perm)) in enumerate(chosen, 1):
        slots = []
        for m, p in sorted(zip(members, perm), key=lambda x: x[1]):
            player, pos = players[m], POSITIONS[p]
            level = player.level(pos)
            sub_count += level == SUB
            off_count += level == OFF
            slots.append(Slot(pos, player, level))
        teams.append(Team(number, tuple(slots), strength))
    return BalanceResult(tuple(teams), abs(teams[0].strength - teams[1].strength), sub_count, off_count)
