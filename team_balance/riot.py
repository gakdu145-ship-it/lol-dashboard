"""라이엇 API로 솔랭 티어를 실시간 조회 (팀 짤 때마다)

솔랭 정보는 DB에 저장하지 않고 팀을 짤 때 최신 값을 가져와요.
호출을 아끼려고 내전 기록이 적은 유저(RatingConfig.solo_until_games 미만)만 조회해요.
지금은 소규모 개발 키이고, 정식 심사 후 큰 키로 바꿀 때는 넘겨주는 api_key만 바꾸면 돼요.

조회에 실패해도 팀 짜기는 계속돼요. 그 유저는 내전 기록이나 기본 점수로 들어가고 경고가 붙어요.
aiohttp가 필요해요 (discord.py가 이미 쓰고 있어서 보통 따로 설치할 필요 없어요).
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Mapping, Sequence
from urllib.parse import quote

import aiohttp

from .rating import PlayerRecord, RatingConfig

ACCOUNT_URL = "https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
LEAGUE_URL = "https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
MAX_RETRY_WAIT = 3   # 호출 한도(429)에 걸렸을 때 이 초 이내면 한 번 기다렸다 다시 시도


class RiotUnavailable(Exception):
    pass


async def _get(session: aiohttp.ClientSession, url: str, api_key: str):
    """200이면 JSON, 404면 None, 그 밖에는 RiotUnavailable"""
    for attempt in range(2):
        async with session.get(url, headers={"X-Riot-Token": api_key}) as res:
            if res.status == 200:
                return await res.json()
            if res.status == 404:
                return None
            wait = float(res.headers.get("Retry-After", 1))
            if res.status != 429 or attempt or wait > MAX_RETRY_WAIT:
                raise RiotUnavailable(f"HTTP {res.status}")
        await asyncio.sleep(wait)


async def _solo(session, name: str, rec: PlayerRecord | None, api_key: str, region: str, platform: str):
    """(솔랭을 채운 PlayerRecord 또는 None, 경고 또는 None)"""
    puuid = rec.puuid if rec else None
    if not puuid:   # DB에 없는 유저(미등록)는 닉네임#태그로 계정부터 찾아요
        game, _, tag = name.rpartition("#")
        if not game or not tag:
            return rec, f"{name}: 태그(#KR1 등)가 없어서 솔랭을 조회하지 못했어요"
        acc = await _get(session, ACCOUNT_URL.format(region=region, name=quote(game, safe=""), tag=quote(tag, safe="")), api_key)
        if not acc:
            return rec, f"{name}: 라이엇에서 찾을 수 없는 계정이에요"
        puuid = acc["puuid"]
    entries = await _get(session, LEAGUE_URL.format(platform=platform, puuid=puuid), api_key) or []
    solo = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    base = replace(rec or PlayerRecord(), puuid=puuid)
    if not solo:
        return base, None   # 언랭 — 내전 기록이나 기본 점수로 들어가요
    return replace(base, solo_tier=solo["tier"], solo_division=solo.get("rank"), solo_lp=solo.get("leaguePoints")), None


async def fill_solo_ranks(names: Sequence[str], records: Mapping[str, PlayerRecord | None], api_key: str | None,
                          cfg: RatingConfig | None = None, *, region: str = "asia", platform: str = "kr",
                          timeout: float = 5) -> tuple[dict[str, PlayerRecord | None], list[str]]:
    """records에 솔랭 정보를 채운 새 사전과 경고 목록을 돌려줘요"""
    cfg = cfg or RatingConfig()
    out = dict(records)
    targets = [n for n in names if records.get(n) is None or records[n].games < cfg.solo_until_games]
    if not targets:
        return out, []
    if not api_key:
        return out, ["라이엇 API 키가 없어서 솔랭을 조회하지 않았어요"]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        results = await asyncio.gather(*(_solo(session, n, records.get(n), api_key, region, platform) for n in targets),
                                       return_exceptions=True)
    warnings = []
    for n, r in zip(targets, results):
        if isinstance(r, Exception):
            warnings.append(f"{n}: 솔랭 조회에 실패했어요 (라이엇 API 응답 없음)")
            continue
        rec, warn = r
        out[n] = rec
        if warn:
            warnings.append(warn)
    return out, warnings
