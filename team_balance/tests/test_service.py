import pytest

from team_balance import PlayerRecord, RosterError, make_teams, parse_roster, records_from_rows, validate_entries

ROSTER = """
1. 가#KR1 탑/정글
2. 나#KR1 탑
3. 다#KR1 정글
4. 라#KR1 정글/미드
5. 마#KR1 미드
6. 바#KR1 미드/원딜
7. 사_사#KR1 원딜
8. 아#KR1 원딜/서폿
9. 자#KR1 서폿
10. 차#KR1
"""


def test_make_teams_end_to_end():
    entries = parse_roster(ROSTER)
    records = {e.name: PlayerRecord(e.name, mmr=2000 + i * 20, games=10) for i, e in enumerate(entries[:8])}
    records["자#KR1"] = PlayerRecord("자", solo_tier="GOLD", solo_division="II")
    out = make_teams(entries, records, seed=5)

    assert len(out.result.teams) == 2
    assert any("차#KR1: 등록되지 않은 유저" in w for w in out.warnings)
    assert any("차#KR1: 포지션이 없어" in w for w in out.warnings)
    text = out.text
    assert "3판 2선승" in text and "**1팀**" in text and "**2팀**" in text
    assert "사\\_사#KR1" in text            # 디스코드 마크다운 이스케이프
    assert "자#KR1 (신규)" in text or "자#KR1 (부, 신규)" in text or "자#KR1 (포지션 외, 신규)" in text


def test_records_from_rows():
    rows = [{"riot_id": "가#KR1", "player_key": "abc", "puuid": "p1", "mmr": 2150.0, "games": 12},
            {"riot_id": "나#KR1", "player_key": "def", "puuid": None, "mmr": None, "games": 0}]
    rec = records_from_rows(rows)
    assert rec["가#KR1"] == PlayerRecord(key="abc", mmr=2150.0, games=12, puuid="p1")
    assert rec["나#KR1"].mmr is None and rec["나#KR1"].games == 0


def test_headcount_error_message():
    with pytest.raises(RosterError, match="12명"):
        validate_entries(parse_roster("\n".join(f"유저{i} 탑" for i in range(12))))


def test_duplicate_names():
    lines = [f"유저{i} 탑" for i in range(9)] + ["유저 0 정글"]
    with pytest.raises(RosterError, match="두 번"):
        validate_entries(parse_roster("\n".join(lines)))
