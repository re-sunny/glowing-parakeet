-- 날짜 목록 조회가 전체 공시를 내려받지 않도록 DB에서 DISTINCT 처리한다.
-- 호출자의 기존 SELECT/RLS 권한으로만 실행한다.
create or replace function public.disclosure_archive_dates()
returns table(disclosure_date date)
language sql
stable
security invoker
set search_path = ''
as $$
    select distinct d.disclosure_date
    from public.disclosures as d
    where d.disclosure_date is not null
      and regexp_replace(coalesce(d.title, ''), '[[:space:].!。！]+', '', 'g')
          not in ('결과값이없습니다', '조회결과가없습니다', '검색결과가없습니다',
                  '조회된데이터가없습니다', '검색된데이터가없습니다', '조회된결과값이없습니다')
      and regexp_replace(coalesce(d.time, ''), '[[:space:].!。！]+', '', 'g')
          not in ('결과값이없습니다', '조회결과가없습니다', '검색결과가없습니다',
                  '조회된데이터가없습니다', '검색된데이터가없습니다', '조회된결과값이없습니다')
    order by d.disclosure_date desc;
$$;

revoke all on function public.disclosure_archive_dates() from public;
grant execute on function public.disclosure_archive_dates() to anon, authenticated, service_role;

-- 확인: 현재 권한으로 조회 가능한 공시 날짜 수
select count(*) as archive_dates from public.disclosure_archive_dates();
