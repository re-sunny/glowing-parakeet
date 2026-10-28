-- 기존 테이블에 원문 URL만 추가한다. RLS와 권한은 변경하지 않는다.
alter table public.disclosures add column if not exists source_url text;
alter table public.disclosures add constraint disclosures_kind_source_url
    check (source_url is null or source_url ~ '^https://kind[.]krx[.]co[.]kr/common/disclsviewer[.]do[?]method=search&acptno=[0-9]{14}$');
notify pgrst, 'reload schema';
