-- 공개된 KIND 목록에 대한 검색/이력. 기존 SELECT RLS를 그대로 적용한다.
create or replace function public.disclosure_search_page(
    search_text text default '', security_code text default null,
    date_from date default null, date_to date default null,
    category_filter text default null, exclude_text boolean default false,
    selected_codes text[] default null, page_number integer default 1,
    page_size integer default 50
) returns jsonb language sql stable security invoker set search_path = '' as $$
with args as (
    select replace(replace(replace(left(coalesce(search_text,''),120), E'\\', E'\\\\'), '%', E'\\%'), '_', E'\\_') as q,
           greatest(1,least(coalesce(page_number,1),100000)) as p,
           greatest(1,least(coalesce(page_size,50),100)) as n
), source as (
    select d.*, regexp_replace(coalesce(d.title,''), '[[:space:]]+', '', 'g') as compact_title
    from public.disclosures d
    where (security_code is null or d.code = security_code)
      and (selected_codes is null or d.code = any(selected_codes))
      and (date_from is null or d.disclosure_date >= date_from)
      and (date_to is null or d.disclosure_date <= date_to)
      and regexp_replace(coalesce(d.title,''), '[[:space:].!。！]+','','g') not in
          ('결과값이없습니다','조회결과가없습니다','검색결과가없습니다','조회된데이터가없습니다','검색된데이터가없습니다','조회된결과값이없습니다')
      and regexp_replace(coalesce(d.time,''), '[[:space:].!。！]+','','g') not in
          ('결과값이없습니다','조회결과가없습니다','검색결과가없습니다','조회된데이터가없습니다','검색된데이터가없습니다','조회된결과값이없습니다')
), classified as (
    select s.*, case
        when compact_title like '%상장폐지%' then 'others'
        when compact_title ~ '(거래정지|정지해제|매매정지|투자경고|투자위험|투자주의경고|매매거래)' then 'warning_risk_trading'
        when compact_title like '%단기과열%' then 'overheating'
        when compact_title ~ '(투자주의|환기종목)' then 'caution'
        when compact_title like '%공매도%' then 'short_selling'
        else 'others' end as display_category
    from source s
), matched as materialized (
    select c.* from classified c cross join args a
    where (category_filter is null or c.display_category = category_filter)
      and (a.q = '' or (
          (coalesce(c.company,'') ilike '%'||a.q||'%' escape E'\\'
           or coalesce(c.code,'') ilike '%'||a.q||'%' escape E'\\'
           or coalesce(c.title,'') ilike '%'||a.q||'%' escape E'\\'
           or coalesce(c.submitter,'') ilike '%'||a.q||'%' escape E'\\') <> exclude_text))
), paged as (
    select id,disclosure_date,time,company,code,title,submitter,source_url,display_category as category
    from matched order by disclosure_date desc,time desc,id desc
    limit (select n from args) offset (select (p-1)*n from args)
)
select jsonb_build_object(
    'items',coalesce((select jsonb_agg(to_jsonb(p) order by p.disclosure_date desc,p.time desc,p.id desc) from paged p),'[]'::jsonb),
    'total',(select count(*) from matched),
    'page',(select p from args),'page_size',(select n from args),
    'category_counts',(select coalesce(jsonb_object_agg(category,cnt),'{}'::jsonb) from
        (select display_category as category,count(*) as cnt from matched group by display_category) counts)
);
$$;
revoke all on function public.disclosure_search_page(text,text,date,date,text,boolean,text[],integer,integer) from public;
grant execute on function public.disclosure_search_page(text,text,date,date,text,boolean,text[],integer,integer) to anon,authenticated,service_role;

-- 공개 가능한 실행 상태만 보관. 오류 메시지·토큰·내부 파일 경로는 저장하지 않는다.
create table if not exists public.kind_collection_runs (
    run_id text primary key,
    target_date date not null,
    state text not null check (state in ('running','succeeded','failed')),
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    stored_count integer check (stored_count >= 0),
    origin text not null default 'collector' check (origin in ('collector','verified_history'))
);
alter table public.kind_collection_runs enable row level security;
revoke all on public.kind_collection_runs from public,anon,authenticated;
grant select on public.kind_collection_runs to anon,authenticated;
grant select,insert,update on public.kind_collection_runs to service_role;
drop policy if exists kind_collection_runs_public_read on public.kind_collection_runs;
create policy kind_collection_runs_public_read on public.kind_collection_runs for select to anon,authenticated using (true);
create index if not exists kind_collection_runs_date on public.kind_collection_runs(target_date desc,started_at desc);
