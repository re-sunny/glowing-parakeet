-- 1단계: 실행 권한 연결 전에 적용 가능한 준비 작업. GitHub 토큰을 포함하지 않는다.
create extension if not exists pg_cron;
create extension if not exists http with schema extensions;

create schema if not exists kind_automation;
revoke all on schema kind_automation from public, anon, authenticated;

create table if not exists kind_automation.dispatch_log (
    scheduled_date date primary key,
    requested_at timestamptz not null default clock_timestamp(),
    http_status integer not null,
    workflow_run_id bigint,
    run_url text
);
alter table kind_automation.dispatch_log enable row level security;
revoke all on kind_automation.dispatch_log from public, anon, authenticated;

create or replace function kind_automation.trigger_kind_collector()
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    github_token text;
    reply extensions.http_response;
    response_data jsonb;
    target_date date := (clock_timestamp() at time zone 'Asia/Seoul')::date;
begin
    -- 같은 날 재호출해도 이미 접수된 실행 요청은 늘리지 않는다.
    perform pg_advisory_xact_lock(20261027, 2015);
    if exists (select 1 from kind_automation.dispatch_log where scheduled_date = target_date) then
        return jsonb_build_object('already_requested', true, 'date', target_date);
    end if;

    select decrypted_secret into github_token
    from vault.decrypted_secrets where name = 'kind_collector_github_token';
    if github_token is null or length(trim(github_token)) = 0 then
        raise exception 'Vault에 kind_collector_github_token을 먼저 등록하세요.';
    end if;

    -- 동기 HTTP를 사용해 인증 헤더를 pg_net 공유 큐에 저장하지 않는다.
    perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '15000');
    perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS', '5000');
    select * into reply from extensions.http((
        'POST',
        'https://api.github.com/repos/re-sunny/glowing-parakeet/actions/workflows/kind_collector.yml/dispatches',
        array[
            extensions.http_header('Authorization', 'Bearer ' || github_token),
            extensions.http_header('Accept', 'application/vnd.github+json'),
            extensions.http_header('X-GitHub-Api-Version', '2026-03-10'),
            extensions.http_header('User-Agent', 'NightDisclosure-Supabase-Cron')
        ],
        'application/json',
        '{"ref":"master"}'
    )::extensions.http_request);
    github_token := null;

    if reply.status not in (200, 204) then
        raise exception 'GitHub Actions 실행 요청 실패 (HTTP %)', reply.status;
    end if;
    response_data := case when reply.status = 200 then reply.content::jsonb else '{}'::jsonb end;
    insert into kind_automation.dispatch_log(scheduled_date, http_status, workflow_run_id, run_url)
    values(target_date, reply.status, (response_data->>'workflow_run_id')::bigint, response_data->>'html_url');
    return jsonb_build_object('date', target_date, 'http_status', reply.status,
                             'run_url', response_data->>'html_url');
end;
$$;
revoke all on function kind_automation.trigger_kind_collector() from public, anon, authenticated, service_role;

-- 토큰 연결 전에는 비활성 상태로 예약을 준비한다.
select cron.schedule('kind-collector-2015-kst', '15 11 * * 1-5',
                     'select kind_automation.trigger_kind_collector();');
select cron.alter_job(jobid, active := false)
from cron.job where jobname = 'kind-collector-2015-kst';

select extname, extversion from pg_extension where extname in ('pg_cron','http');
