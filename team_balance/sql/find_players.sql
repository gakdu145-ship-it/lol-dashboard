-- 팀 짜기용 유저 조회: 서버(slug)와 명단의 '닉네임#태그' 목록 → 각 유저의 공개 키·puuid·내전 MMR·판수
-- 닉네임·태그 모두 대소문자 상관없이 찾아요 (결과의 riot_id는 명단에 적힌 그대로, 태그 kr1만 KR1로 바꿔서 돌려줘요)
-- 명단에 있어도 DB에 없는 닉네임(미등록 유저)은 결과에 나오지 않아요
--
-- 봇(service_role 키)에서만 부를 수 있게 막아 둬요. 공개 키로 부르면 남의 puuid를 찾아볼 수 있어서예요.
-- 호출 예 (supabase-py): client.rpc("find_players", {"p_slug": "simkong", "p_riot_ids": names}).execute().data

create or replace function public.find_players(p_slug text, p_riot_ids text[])
returns table (riot_id text, player_key text, puuid text, mmr numeric, games bigint)
language sql stable
as $$
  with input as (
    select distinct regexp_replace(btrim(x), '#kr1$', '#KR1', 'i') as riot_id
    from unnest(p_riot_ids) as x
  )
  select i.riot_id, p.public_key::text, ra.puuid::text, s.mmr, s.games
  from input i
  -- 라이엇 ID는 대소문자를 구분하지 않아서 lower()로 비교
  join public.riot_accounts ra on lower(ra.game_name || '#' || ra.tag_line) = lower(i.riot_id)
  join public.players p on p.id = ra.player_id
  join public.guilds g on g.id = p.guild_id and g.slug = p_slug
  cross join lateral (
    -- 사이트(pub_rankings)와 같은 계산: 확정된 경기만, 2000 + MMR 변화량 합계
    select count(m.id) as games, (2000 + coalesce(sum(mp.mmr_delta) filter (where m.id is not null), 0))::numeric as mmr
    from public.match_participants mp
    left join public.matches m on m.id = mp.match_id and m.status = 'confirmed'
    where mp.player_id = p.id
  ) s
$$;

revoke execute on function public.find_players(text, text[]) from public, anon, authenticated;
grant execute on function public.find_players(text, text[]) to service_role;
