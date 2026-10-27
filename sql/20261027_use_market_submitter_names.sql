-- Supabase에서 2026-10-27 확인: 대상 326건, 정규화 후 충돌 0건.
-- 적용 전 원본/복구 SQL은 로컬 reports/company_before_submitter_20261027_164007.* 에 보관.
-- 회사명이 nan이고 제출인이 확인된 두 시장본부일 때만 변경한다.
-- 동일한 키의 정상 행이 이미 있다면 변경을 건너뛴다.
BEGIN;
UPDATE public.disclosures AS d
SET company = d.submitter
WHERE d.company = 'nan'
  AND d.submitter IN ('유가증권시장본부', '코스닥시장본부')
  AND NOT EXISTS (
    SELECT 1 FROM public.disclosures AS t
    WHERE t.id <> d.id
      AND t.disclosure_date IS NOT DISTINCT FROM d.disclosure_date
      AND t.time IS NOT DISTINCT FROM d.time
      AND t.code IS NOT DISTINCT FROM d.code
      AND t.title IS NOT DISTINCT FROM d.title
      AND t.company = d.submitter
  )
RETURNING id, company, submitter;
COMMIT;
