"""명단 → 팀 구성까지 한 번에 (봇 명령어에서 부르는 입구)

    entries = parse_roster(text)
    validate_entries(entries)                 # DB 조회 전에 인원·중복부터 확인
    names = [e.name for e in entries]
    records = records_from_rows(<DB 함수 find_players(서버 slug, names) 결과>)
    records, warns = await fill_solo_ranks(names, records, RIOT_API_KEY)   # riot.py
    outcome = make_teams(entries, records, extra_warnings=warns)
    await channel.send(outcome.text)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .balance import LEVEL_NAME, MAIN, PLAYER_COUNT, BalanceConfig, BalanceResult, Participant, balance
from .rating import PlayerRecord, RatingConfig, rate
from .roster import RosterEntry, RosterError

_NEW = ("솔랭", "기본값")   # 내전 기록 없이 점수를 매긴 유저


@dataclass(frozen=True)
class Outcome:
    result: BalanceResult
    warnings: tuple[str, ...]

    @property
    def text(self) -> str:
        return format_result(self.result, self.warnings)


def validate_entries(entries: list[RosterEntry]) -> None:
    if len(entries) != PLAYER_COUNT:
        raise RosterError(f"확정 인원이 {len(entries)}명이에요. 팀 짜기는 10명일 때만 할 수 있어요.")
    seen, dup = set(), []
    for e in entries:
        k = e.name.casefold().replace(" ", "")
        if k in seen:
            dup.append(e.name)
        seen.add(k)
    if dup:
        raise RosterError("명단에 같은 이름이 두 번 있어요: " + ", ".join(dup))


def records_from_rows(rows) -> dict[str, PlayerRecord]:
    """DB 함수 find_players()의 결과 행들 → make_teams·fill_solo_ranks에 넘길 사전 (닉네임#태그 → PlayerRecord)"""
    return {r["riot_id"]: PlayerRecord(key=r.get("player_key"),
                                       mmr=float(r["mmr"]) if r.get("mmr") is not None else None,
                                       games=int(r.get("games") or 0),
                                       puuid=r.get("puuid"))
            for r in rows}


def make_teams(entries: list[RosterEntry], records: Mapping[str, PlayerRecord | None],
               rating_cfg: RatingConfig | None = None, balance_cfg: BalanceConfig | None = None,
               seed=None, extra_warnings=()) -> Outcome:
    """records: 명단의 닉네임 → 유저 정보. 없는 닉네임(미등록 유저)은 빼거나 None으로 주면 돼요"""
    validate_entries(entries)
    warnings, players = list(extra_warnings), []
    for e in entries:
        rec = records.get(e.name)
        r = rate(rec, rating_cfg)
        if rec is None or rec.key is None:
            how = "솔랭 기준" if r.source == "솔랭" else "기본 점수"
            warnings.append(f"{e.name}: 등록되지 않은 유저라 {how}({r.value:,.0f})으로 넣었어요")
        elif r.source == "기본값":
            warnings.append(f"{e.name}: 내전·솔랭 기록이 없어 기본 점수({r.value:,.0f})로 넣었어요")
        if not e.positions and not e.fill:
            warnings.append(f"{e.name}: 포지션이 없어 아무 포지션이나 가능한 것으로 봤어요")
        players.append(Participant(e.name, r.value, e.positions, e.fill, rec.key if rec else None, r.source))
    return Outcome(balance(players, balance_cfg, seed), tuple(warnings))


def _md(s: str) -> str:
    """디스코드 마크다운 문자 이스케이프 (닉네임의 _ * 등이 서식으로 바뀌지 않게)"""
    return re.sub(r"([\\*_~|`>])", r"\\\1", s)


def format_result(result: BalanceResult, warnings=()) -> str:
    lines = ["**내전 팀 구성** · 10명 · 3판 2선승", ""]
    for t in result.teams:
        lines.append(f"**{t.number}팀** · 평균 {t.average:,.0f}")
        for s in t.slots:
            tags = [] if s.level == MAIN else [LEVEL_NAME[s.level]]
            if s.participant.source in _NEW:
                tags.append("신규")
            lines.append(f"`{s.position}` {_md(s.participant.name)}" + (f" ({', '.join(tags)})" if tags else ""))
        lines.append("")
    summary = f"두 팀 전력 차이 {result.spread:,.0f}"
    if result.sub_count:
        summary += f" · 부 포지션 {result.sub_count}명"
    if result.off_count:
        summary += f" · 포지션 외 {result.off_count}명"
    lines.append(summary)
    if warnings:
        lines += [""] + ["⚠️ " + _md(w) for w in warnings]
    return "\n".join(lines)
