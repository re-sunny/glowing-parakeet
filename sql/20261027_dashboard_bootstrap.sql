-- 기존 날짜 함수와 같은 RLS 권한으로 초기 화면의 두 조회를 통합한다.
create or replace function public.disclosure_dashboard_bootstrap()
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
    with dates as materialized (
        select disclosure_date from public.disclosure_archive_dates()
    ), latest as (
        select max(disclosure_date) as disclosure_date from dates
    )
    select jsonb_build_object(
        'dates', (select coalesce(jsonb_agg(disclosure_date order by disclosure_date desc), '[]'::jsonb) from dates),
        'date', (select disclosure_date from latest),
        'disclosures', (
            select coalesce(jsonb_agg(to_jsonb(d) order by d.time desc, d.id desc), '[]'::jsonb)
            from public.disclosures as d
            where d.disclosure_date = (select disclosure_date from latest)
        )
    );
$$;

revoke all on function public.disclosure_dashboard_bootstrap() from public;
grant execute on function public.disclosure_dashboard_bootstrap() to anon, authenticated, service_role;

select jsonb_array_length(data->'dates') as dates,
       data->>'date' as latest_date,
       jsonb_array_length(data->'disclosures') as disclosures
from (select public.disclosure_dashboard_bootstrap() as data) as result;
