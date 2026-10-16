from team_balance.roster import normalize_riot_id, parse_line, parse_roster


def test_kr1_tag_is_case_insensitive():
    assert parse_line("닉네임#kr1 탑").name == "닉네임#KR1"
    assert normalize_riot_id("닉네임#Kr1") == "닉네임#KR1"
    assert normalize_riot_id("닉네임#abc") == "닉네임#abc"     # 다른 태그는 그대로
    assert normalize_riot_id("닉네임#kr12") == "닉네임#kr12"   # KR1로 끝나는 게 아니라 KR1 자체일 때만


def test_slash():
    e = parse_line("Hide on bush#KR1 미드/탑")
    assert e.name == "Hide on bush#KR1"
    assert e.positions == ("미드", "탑")


def test_bullet_and_parentheses():
    e = parse_line("- 닉네임#KR1 (정글, 서폿)")
    assert (e.name, e.positions) == ("닉네임#KR1", ("정글", "서폿"))


def test_numbered_with_labels():
    e = parse_line("3. 닉네임 주:원딜 부:서폿")
    assert (e.name, e.positions) == ("닉네임", ("원딜", "서폿"))


def test_english_aliases():
    e = parse_line("10) Faker#T1 - MID / Top")
    assert (e.name, e.positions) == ("Faker#T1", ("미드", "탑"))


def test_fill():
    e = parse_line("닉네임 올라운더")
    assert e.name == "닉네임" and e.positions == () and e.fill


def test_nickname_that_is_a_position_word():
    e = parse_line("미드 정글")
    assert (e.name, e.positions) == ("미드", ("정글",))


def test_tag_is_not_a_position():
    e = parse_line("닉네임#탑")
    assert (e.name, e.positions) == ("닉네임#탑", ())


def test_duplicate_positions_collapse():
    assert parse_line("닉네임 탑/탑/정글").positions == ("탑", "정글")


def test_roster_skips_titles_and_blank_lines():
    text = """확정 명단:

    1. 가나다#KR1 탑/정글
    2. 라마바#KR1 서폿
    """
    entries = parse_roster(text)
    assert [e.name for e in entries] == ["가나다#KR1", "라마바#KR1"]
    assert entries[0].line_no == 3
