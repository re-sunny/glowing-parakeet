-- 2단계: Vault 토큰 등록 및 수동 호출 성공을 확인한 뒤에만 실행한다.
-- 토큰 자체를 SQL Editor 또는 Git 저장소에 넣지 않는다.
do $$
begin
    if not exists (select 1 from vault.secrets where name = 'kind_collector_github_token') then
        raise exception 'Vault 토큰이 등록되어 있지 않습니다.';
    end if;
    if not exists (select 1 from kind_automation.dispatch_log
                   where scheduled_date = (clock_timestamp() at time zone 'Asia/Seoul')::date
                     and http_status in (200,204)) then
        raise exception '먼저 kind_automation.trigger_kind_collector() 수동 호출을 검증하세요.';
    end if;
    if coalesce(current_setting('cron.timezone', true), 'GMT') not in ('GMT','UTC','Etc/UTC') then
        raise exception 'cron.timezone이 UTC인지 확인하세요.';
    end if;
end;
$$;

select cron.schedule(
    'kind-collector-2015-kst',
    '15 11 * * 1-5',
    'select kind_automation.trigger_kind_collector();'
);
select cron.alter_job(jobid, active := true)
from cron.job where jobname = 'kind-collector-2015-kst';

select jobid, jobname, schedule, active, username
from cron.job where jobname = 'kind-collector-2015-kst';
