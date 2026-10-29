# 2026-10-29 수집 실패

- Supabase Cron `kind-collector-2015-kst`는 KST 20:15:00.151821에 실행, succeeded.
- GitHub Actions #153은 KST 20:15에 시작했으나 Supabase 적재에서 HTTP 400 / PGRST102로 실패.
- 실행: https://github.com/re-sunny/glowing-parakeet/actions/runs/40863913792
- KIND 원문 접수번호 수집 및 최신 XLS 다운로드는 진행됐으며, 확인 시 DB에는 10월 29일 행이 없었다.

## 원인 및 수정

원문 URL을 찾은 행에만 `source_url` 필드를 넣어 JSON 배열의 행별 키가 달라졌다.
PostgREST의 일괄 요청은 같은 키 집합을 요구하므로 링크가 있는/없는 행이 섞이면 거절된다.
기존 오류 문구는 모든 오류에 RLS 안내를 표시해 원인 파악을 어렵게 했다.

`upload_classified_rows_to_supabase`에서 중복 제거 후 키 집합별로 나누고 각 그룹을 500행씩 전송한다.
누락 링크를 null로 채우면 관리자 merge 모드에서 기존 링크를 지울 수 있어 누락 필드는 유지한다.
PGRST102에 대해서는 JSON 형식 안내를 표시한다. DB 권한·예약·비밀키 변경은 필요하지 않다.

## 검증

- 수정 전 관리자 키/일반 키 모두 혼합 링크 회귀 테스트 실패를 재현.
- 수정 후 기존 링크 보존, 신규 링크/미연결 행 적재와 기존 테스트 포함 Python 67개 통과.
- 요청 분리 도중 일부 요청이 성공하고 이후 실패할 수 있으므로 전체 실행은 실패로 남긴다.
  기존 고유키와 충돌 처리로 재실행 시 이미 적재한 행은 중복 생성하지 않는다.
- 수정 커밋 `ea301f0` 반영 후 복구 실행 #154가 56초에 성공했다.
  https://github.com/re-sunny/glowing-parakeet/actions/runs/40866938311
- DB 직접 조회로 2026-10-29 공시 58행, 원문 링크 58행, 시간 20:00~20:16을 확인했다.
- 이번 장애는 예약 누락이 아니므로 기존 평일 20:15 Supabase Cron을 유지했다.
