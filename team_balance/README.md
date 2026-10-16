# team_balance — 내전 밸런스 팀 구성

10명 확정 명단을 붙여 넣으면 실력 점수와 포지션에 맞춰 5:5 두 팀(3판 2선승)으로 나눠요.
20명 내전은 경매로 팀을 꾸리는 경우가 많아서 지원하지 않아요.

Python 3.9 이상이면 돼요. 폴더째 봇 프로젝트에 복사해서 쓰면 돼요.
라이엇 API 조회(`riot.py`)만 aiohttp가 필요하고(discord.py에 이미 포함), 나머지는 표준 라이브러리만 써요.

## 흐름

```
명단 텍스트 ─ parse_roster ─ validate_entries ─ DB find_players ─ fill_solo_ranks ─ make_teams ─ outcome.text
                                                  (내전 MMR·판수)   (솔랭, 라이엇 API)
```

| 파일 | 역할 |
|---|---|
| `roster.py` | 명단 파싱. 한 줄에 한 명이고, 줄 끝의 포지션을 앞에서부터 주·부 포지션으로 읽어요. 태그 `kr1`은 `KR1`로 통일해요 |
| `rating.py` | 실력 점수. 신규 유저는 솔랭, 내전 판수가 쌓일수록 내전 MMR 쪽으로 옮겨가요 |
| `riot.py` | 솔랭 티어를 팀 짤 때마다 라이엇 API로 실시간 조회해요 (DB에 저장하지 않아요) |
| `balance.py` | 팀 나누기와 포지션 배정. 나누는 경우의 수 126개를 전부 비교해요 |
| `service.py` | DB 결과 변환, 팀 구성, 디스코드 메시지 만들기 |
| `sql/find_players.sql` | 팀 짜기용 유저 조회 DB 함수. Supabase SQL Editor에서 한 번 실행해 두면 돼요 |

### 명단 양식
서버마다 양식이 달라서 느슨하게 읽어요.
```
1. Hide on bush#KR1 미드/탑
- 닉네임#KR1 (정글, 서폿)
닉네임 주:원딜 부:서폿
닉네임 올라운더          ← 어느 포지션이든 가능
```
`확정 명단:`처럼 콜론으로 끝나는 제목 줄과 빈 줄은 건너뛰어요.

## 실력 점수와 라이엇 API 호출
- 내전 판수가 `solo_until_games`(기본 20판)보다 적은 유저와 미등록 유저만 라이엇 API로 솔랭을 조회해요. 한 번에 최대 10명이에요.
- 미등록 유저는 puuid가 없어서 계정 조회 1번과 솔랭 조회 1번, 모두 2번 호출해요.
- 호출 한도(429)에 걸리면 3초 이내일 때만 한 번 기다렸다가 다시 시도해요.
- 조회에 실패해도 팀 짜기는 계속돼요. 그 유저는 내전 기록이나 기본 점수로 들어가고 메시지에 경고가 붙어요.
- 라이엇 정식 키로 바꿀 때는 `fill_solo_ranks`에 넘기는 키만 바꾸면 돼요. 환경 변수(`RIOT_API_KEY`)로 관리하세요.

## discord.py 연결 예시

슬래시 명령어 옵션은 한 줄만 받아서, 명단은 모달(여러 줄 입력)로 받아요.

```python
import os
import discord
from team_balance import RosterError, make_teams, parse_roster, records_from_rows, validate_entries
from team_balance.riot import fill_solo_ranks

class RosterModal(discord.ui.Modal, title="내전 팀 짜기"):
    roster = discord.ui.TextInput(label="확정 명단 (한 줄에 한 명, 포지션 포함)",
                                  style=discord.TextStyle.paragraph, max_length=2000)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            entries = parse_roster(self.roster.value)
            validate_entries(entries)
        except RosterError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.defer()
        names = [e.name for e in entries]
        slug = guild_slug(interaction.guild_id)   # 봇팀: 디스코드 서버 → guilds.slug
        rows = supabase.rpc("find_players", {"p_slug": slug, "p_riot_ids": names}).execute().data
        records, warns = await fill_solo_ranks(names, records_from_rows(rows), os.environ.get("RIOT_API_KEY"))
        outcome = make_teams(entries, records, extra_warnings=warns)
        await interaction.followup.send(outcome.text)

@bot.tree.command(name="팀짜기", description="확정 명단으로 밸런스 팀을 짜요")
async def team_cmd(interaction: discord.Interaction):
    await interaction.response.send_modal(RosterModal())
```
`supabase`는 **service_role 키**로 만든 클라이언트여야 해요. `find_players`는 공개 키로는 부를 수 없게 막아 뒀어요.

## 조정값

- `RatingConfig`
  - `blend_games`: 몇 판에서 내전 MMR과 솔랭을 반반 믿을지 정해요.
  - `solo_until_games`: 내전 판수가 이만큼 쌓이면 솔랭을 보지 않고 라이엇 API도 부르지 않아요.
  - `solo_anchor`, `solo_scale`: 솔랭을 내전 MMR로 환산하는 기준과 배율이에요. 기본값(에메랄드 4 = 2000)은 임시값이에요. 솔랭과 내전 기록이 둘 다 있는 유저가 쌓이면 그 데이터로 보정하세요.
- `BalanceConfig`
  - `sub_malus`, `off_malus`: 부 포지션이나 신청하지 않은 포지션에 섰을 때 팀 전력에서 빼는 값이에요.
  - `tolerance`: 최선의 조합과 이만큼 이내로 차이 나는 조합 중에서 무작위로 골라요. 같은 멤버로 해도 매번 똑같은 팀이 나오지 않게 하려는 값이에요.

## 테스트

```
pip install pytest
python -m pytest team_balance
```
`riot.py`(라이엇 API 호출)는 테스트가 없어요. 실제 키로 한 번 확인해 주세요.
