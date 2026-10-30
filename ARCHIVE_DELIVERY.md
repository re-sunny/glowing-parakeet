# 과거 공시의 첫 조회 속도 개선

날짜 조회 실행 계획은 기존 인덱스를 사용하며 2025-01-06 표본의 DB 실행 시간은
0.065ms였다. 서버 최초 기동과 네트워크 왕복으로 같은 날짜의 API 요청은
약 1.8초가 걸려, 과거 공시를 배포 시점에 날짜별 JSON으로 만든다.

## 전달 경로

- `node build_archive.mjs`가 공개 조회 키의 RLS 범위에서 KIND `disclosures`를 읽는다.
- 페이지 전체 건수와 ID 중복을 검사하고, 안내문을 제외한 공개 화면 필드만 내보낸다.
- 한국 시간 당일과 미래 데이터는 정적 파일에서 제외한다.
- `@vercel/static-build`가 `public/dashboard.html` 및 `public/archive/dates/*.json`을 CDN에 배포한다.
- HTML 안의 목록에 있는 과거 날짜는 정적 JSON을 읽는다. 모든 날짜를 브라우저에 미리 다운로드하지 않는다.
- 파일의 날짜·버전·배포 시각을 검증한다. 파일 오류, 미포함 날짜, 강제 갱신은 기존 API로 처리한다.
- 파일은 재배포할 때 다시 생성한다. DB의 과거 데이터 수정은 재배포 후 정적 조회에 반영된다.
- 새로 쌓여 아직 배포 파일에 없는 날짜와 오늘 공시는 계속 실시간 API로 읽는다.
- DB와 매일 20:15 수집 예약은 그대로 유지한다. DART 비공개 스키마는 이 빌드에서 조회하지 않는다.

2026-10-30 최초 생성: 과거 416일, 실제 공시 19,439건. 생성 결과는 `public/`에
있으며 Git에는 포함하지 않는다. Supabase service-role 키나 원본 비공개 필드는
정적 산출물에 넣지 않는다.

## 검증

- `node tests/archive_build.test.mjs`
- `node tests/dashboard_loading.test.cjs`
- `python -m pytest -q`
- 실제 3개 날짜의 정적 JSON을 기존 Python 정규화 결과와 대조

Vercel의 [빌드 산출물 CDN 전달](https://vercel.com/docs/builds) 및
[정적 빌드 설정](https://vercel.com/docs/builds/configure-a-build)을 사용한다.
