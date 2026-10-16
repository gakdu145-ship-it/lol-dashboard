import pytest

from team_balance.balance import OFF, Participant, balance
from team_balance.roster import POSITIONS


def _ten():
    skills = {"탑": (2400, 2000), "정글": (2300, 2100), "미드": (2200, 2200), "원딜": (2500, 1900), "서폿": (2000, 2000)}
    return [Participant(f"{pos}{i}", s, (pos,)) for pos, pair in skills.items() for i, s in enumerate(pair)]


def test_ten_players_find_perfect_split():
    r = balance(_ten(), seed=1)
    assert len(r.teams) == 2
    assert r.spread == 0 and r.sub_count == 0 and r.off_count == 0
    names = {frozenset(s.participant.name for s in t.slots) for t in r.teams}
    assert frozenset({"탑0", "정글0", "미드0", "원딜1", "서폿0"}) in names or \
           frozenset({"탑0", "정글0", "미드1", "원딜1", "서폿0"}) in names or \
           frozenset({"탑0", "정글0", "미드0", "원딜1", "서폿1"}) in names or \
           frozenset({"탑0", "정글0", "미드1", "원딜1", "서폿1"}) in names


def test_every_team_covers_all_positions():
    for t in balance(_ten(), seed=7).teams:
        assert tuple(s.position for s in t.slots) == POSITIONS


def test_same_seed_same_result():
    a, b = balance(_ten(), seed=42), balance(_ten(), seed=42)
    assert [[s.participant.name for s in t.slots] for t in a.teams] == \
           [[s.participant.name for s in t.slots] for t in b.teams]


def test_sub_position_preferred_over_off_position():
    # 원딜 신청자가 없고, 서폿0만 원딜을 부 포지션으로 적었어요 → 원딜 자리는 서폿0이 서야 해요
    players = _ten()
    players = [p for p in players if p.positions != ("원딜",)]
    players += [Participant("서폿2", 2000, ("서폿", "원딜")), Participant("서폿3", 2000, ("서폿",))]
    r = balance(players, seed=0)
    adc = [s for t in r.teams for s in t.slots if s.position == "원딜"]
    assert "서폿2" in {s.participant.name for s in adc}
    assert sum(s.level == OFF for s in adc) == 1


@pytest.mark.parametrize("n", [9, 11, 15, 20])
def test_wrong_headcount(n):
    with pytest.raises(ValueError):
        balance([Participant(str(i), 2000) for i in range(n)])
