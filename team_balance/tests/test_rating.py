import pytest

from team_balance.rating import PlayerRecord, RatingConfig, rate, solo_ladder


def test_solo_ladder():
    assert solo_ladder("EMERALD", "IV", 0) == 2000
    assert solo_ladder("DIAMOND", 1, 50) == 2750
    assert solo_ladder("다이아몬드", "1", 50) == 2750
    assert solo_ladder("MASTER", None, 120) == 2920
    assert solo_ladder("UNRANKED") is None
    assert solo_ladder(None) is None


def test_no_data_uses_start_mmr():
    assert rate(None).value == 2000
    assert rate(PlayerRecord("k")).source == "기본값"


def test_new_player_uses_solo():
    r = rate(PlayerRecord("k", solo_tier="DIAMOND", solo_division="IV"))   # 2400 → 2000 + 400×0.5
    assert (r.value, r.source) == (2200, "솔랭")


def test_blend_moves_toward_inhouse_mmr():
    cfg = RatingConfig(blend_games=5)
    solo = dict(solo_tier="DIAMOND", solo_division="IV")   # 2200
    half = rate(PlayerRecord("k", mmr=2400, games=5, **solo), cfg)
    assert half.value == pytest.approx(2300) and half.source == "혼합"
    more = rate(PlayerRecord("k", mmr=2400, games=15, **solo), cfg)
    assert more.value == pytest.approx(2350)          # 15/20 × 2400 + 5/20 × 2200
    enough = rate(PlayerRecord("k", mmr=2400, games=20, **solo), cfg)
    assert (enough.value, enough.source) == (2400, "내전")   # solo_until_games부터는 솔랭을 안 봐요


def test_inhouse_only():
    assert rate(PlayerRecord("k", mmr=2150, games=3)).value == 2150
