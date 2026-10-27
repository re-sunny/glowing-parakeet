# 평일 한국 시간 20:15 수집 예약

Supabase Cron이 평일 UTC 11:15에 `kind_collector.yml`의 `workflow_dispatch`를 호출한다.
수집·Supabase 적재는 기존 GitHub Actions에서 수행한다. GitHub 자체 `schedule` 전달 지연은
피하지만, GitHub 러너 대기나 서비스 장애까지 없애는 정시 보장은 아니다.

## 연결 순서

1. `sql/20261027_prepare_collector_schedule.sql`을 한 번 적용한다.
   `pg_cron`, `http`, 외부에 노출되지 않는 `kind_automation` 스키마와 함수를 준비한다.
   `kind-collector-2015-kst` 예약은 비활성 상태로 생성된다.
   운영 중 이 준비 파일을 다시 실행하면 예약이 비활성화되므로 재적용하지 않는다.
2. GitHub fine-grained token을 사용자가 생성한다.
   대상은 `re-sunny/glowing-parakeet` 하나, 권한은 `Actions: Read and write`와 필수 Metadata 읽기다.
   만료일을 확인하고, 만료 전에 Vault의 값을 새 토큰으로 교체한다.
3. 사용자가 Supabase Vault UI에 `kind_collector_github_token` 이름으로 직접 저장한다.
   토큰은 SQL Editor, 코드, 채팅 또는 로그에 넣지 않는다.
4. SQL Editor에서 `select kind_automation.trigger_kind_collector();`를 실행한다.
   GitHub의 실행 성공과 Supabase 적재를 확인한다. 같은 한국 날짜의 접수된 호출은 재요청하지 않는다.
5. `sql/20261027_activate_collector_schedule.sql`로 예약을 활성화한다.
   오늘의 연결 검증 기록, Vault 항목 존재, Cron의 UTC 시간대를 검사한 뒤 활성화한다.
6. 활성화가 확인되면 GitHub workflow의 `on.schedule`을 제거해 두 예약의 중복 실행을 막는다.
   `workflow_dispatch`는 수동·Supabase 호출용으로 유지한다.

## 보관과 기록

- 토큰은 Vault에서 읽어 동기 HTTPS로 GitHub에만 전송한다. `pg_net` 요청 큐에 토큰을 저장하지 않는다.
- 호출 함수는 `SECURITY INVOKER`이며 일반 공개·로그인·service-role API에서는 실행할 수 없다.
  Cron은 예약을 만든 관리자 역할로 실행한다.
- `kind_automation.dispatch_log`는 날짜, HTTP 상태, GitHub 실행 ID/URL만 기록한다.
  요청 접수 성공은 수집 완료와 다르므로 최종 GitHub 실행 결과도 확인한다.
- GitHub 인증 오류·네트워크 오류는 Cron 실패로 남으며 성공 기록을 만들지 않는다.
  자동 재시도 예약은 추가하지 않는다. 실패 원인을 수정한 뒤 관리자가 수동 호출할 수 있다.

```sql
select jobid, jobname, schedule, active, username
from cron.job where jobname = 'kind-collector-2015-kst';

select scheduled_date, requested_at at time zone 'Asia/Seoul' as requested_kst,
       http_status, workflow_run_id, run_url
from kind_automation.dispatch_log order by scheduled_date desc limit 10;

select status, return_message, start_time, end_time
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'kind-collector-2015-kst')
order by start_time desc limit 10;
```

## 일시 정지

```sql
select cron.alter_job(jobid, active := false)
from cron.job where jobname = 'kind-collector-2015-kst';
```

다시 활성화하기 전에 유효한 토큰과 수동 실행을 확인한다. GitHub 예약으로 되돌리는 경우
Supabase 예약을 먼저 정지하고 `15 11 * * 1-5`를 workflow에 복원한다.
