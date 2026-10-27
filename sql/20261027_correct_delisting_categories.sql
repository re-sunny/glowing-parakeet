-- Supabase에서 2026-10-27 확인한 과거 오분류 8건.
-- 원래 category는 모두 warning_risk_trading. 공시 본문/중복 키는 변경하지 않는다.
BEGIN;
UPDATE public.disclosures
SET category = 'others'
WHERE id IN (7845, 7846, 7903, 7904, 7960, 7961, 8017, 8910)
  AND regexp_replace(title, '\s+', '', 'g') LIKE '%상장폐지%'
  AND category = 'warning_risk_trading'
RETURNING id, title, category;
COMMIT;

-- 복구가 필요할 때 별도로 실행:
-- UPDATE public.disclosures SET category = 'warning_risk_trading'
-- WHERE id IN (7845, 7846, 7903, 7904, 7960, 7961, 8017, 8910)
--   AND category = 'others';
