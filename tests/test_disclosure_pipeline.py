import asyncio
import datetime
import os
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import read_excel_auto as pipeline
from disclosure_rules import classify_title, clean_code, display_company, storage_company


@pytest.fixture
def configured_db(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.invalid")
    monkeypatch.setenv("SUPABASE_KEY", "read-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "write-key")


def item(title="투자경고종목 지정", time="20:01"):
    return dict(time=time, company="테스트", code="000001", title=title,
                submitter="거래소", category="warning_risk_trading")


def test_second_collection_adds_new_rows_and_updates_old_rows(monkeypatch, tmp_path, configured_db):
    snapshot = tmp_path / "오늘의공시.xls"
    snapshot.write_bytes(b"snapshot")
    timestamp = datetime.datetime(2026, 10, 27, 23, 15, tzinfo=datetime.timezone.utc).timestamp()
    os.utime(snapshot, (timestamp, timestamp))
    database = {}

    def post(url, *, headers, json, params, timeout):
        assert headers["Authorization"] == "Bearer write-key"
        assert params["on_conflict"] == "disclosure_date,time,company,code,title"
        for row in json:
            key = tuple(row[k] for k in params["on_conflict"].split(","))
            database[key] = row
        return type("Response", (), {"status_code": 204})()

    monkeypatch.setattr(pipeline.requests, "post", post)
    pipeline.upload_classified_rows_to_supabase([item()], snapshot)
    updated = {**item(), "category": "others"}
    pipeline.upload_classified_rows_to_supabase([updated, updated, item("신규 공시", "20:14")], snapshot)
    assert len(database) == 2
    assert {row["disclosure_date"] for row in database.values()} == {"2026-10-28"}
    assert next(row for row in database.values() if row["time"] == "20:01")["category"] == "others"


def test_upsert_permission_error_is_not_swallowed(monkeypatch, tmp_path, configured_db):
    snapshot = tmp_path / "snapshot.xls"
    snapshot.touch()

    class Response:
        status_code = 403

        def json(self):
            return {"code": "42501"}

    monkeypatch.setattr(pipeline.requests, "post", lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError, match="42501"):
        pipeline.upload_classified_rows_to_supabase([item()], snapshot)


def test_insert_only_key_skips_existing_rows_without_update_permission(monkeypatch, tmp_path, configured_db):
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
    snapshot = tmp_path / "snapshot.xls"
    snapshot.touch()
    database = {("20:01", "투자경고종목 지정"): item()}

    def post(url, *, headers, json, params, timeout):
        assert headers["Authorization"] == "Bearer read-key"
        assert "resolution=ignore-duplicates" in headers["Prefer"]
        for row in json:
            database.setdefault((row["time"], row["title"]), row)
        return type("Response", (), {"status_code": 201})()

    monkeypatch.setattr(pipeline.requests, "post", post)
    pipeline.upload_classified_rows_to_supabase([item(), item("새로운 공시", "20:14")], snapshot)
    assert len(database) == 2


@pytest.mark.parametrize("title", [
    "자기주식매매 신청내역(유가증권시장)", "대량매매내역(코스닥시장)",
    "일일 회전율 상위 20종목-ELW제외(유가증권시장)",
])
def test_market_statistics_use_the_confirmed_submitter(title):
    assert display_company(float("nan"), title, "유가증권시장본부") == "유가증권시장본부"
    assert classify_title(title) == "others"


@pytest.mark.parametrize("title,category", [
    ("상장폐지에 따른 매매거래정지", "others"),
    ("투자위험종목 지정", "warning_risk_trading"),
    ("매매거래정지 및 정지해제(상장폐지)", "others"),
    ("단기과열종목 지정", "overheating"),
    ("공매도 과열종목 지정", "short_selling"),
])
def test_classification(title, category):
    assert classify_title(title) == category


def test_report_keeps_market_statistics_and_filters_unknown_times(monkeypatch, tmp_path):
    frame = pd.DataFrame([
        ["20:01", float("nan"), 999990, "자기주식매매 신청내역", "유가증권시장본부"],
        ["20:02", "기업", 1234.0, "상장폐지에 따른 매매거래정지", None],
        ["19:59", "이전", 1, "투자경고", "거래소"],
        [None, "시간미제공", 2, "투자경고", "거래소"],
    ], columns=["시간", "회사명", "종목코드", "공시제목", "제출인"])
    captured = []
    monkeypatch.setattr(pipeline, "try_read_excel", lambda _: frame)
    monkeypatch.setattr(pipeline, "upload_classified_rows_to_supabase", lambda rows, _: captured.extend(rows))
    monkeypatch.setattr(pipeline, "get_html2canvas_script", lambda: "/* test */")
    report = pipeline.generate_report_from_agent_md(str(tmp_path / "test.xls"), [])
    assert len(captured) == 2
    assert captured[0]["company"] == "유가증권시장본부"
    assert captured[1]["code"] == "001234"
    assert captured[1]["submitter"] == "-"
    assert all(row["category"] == "others" for row in captured)
    assert "유가증권시장본부" in report["html"]
    assert "시장 전체" not in report["html"]


def test_old_database_rows_are_normalized_when_read(monkeypatch):
    import run_server

    class Response:
        status_code = 200

        def json(self):
            return [
                {**item("상장폐지에 따른 매매거래정지")},
                {**item("대량매매내역"), "company": "nan", "code": None, "submitter": "코스닥시장본부"},
                {**item("결과값이 없습니다."), "time": "결과값이 없습니다."},
            ]

    monkeypatch.setattr(run_server.requests, "get", lambda *args, **kwargs: Response())
    rows = asyncio.run(run_server.get_disclosures(date="2026-10-27", query=None, ignoreDate=False, exclude=False))
    assert rows[0]["category"] == "others"
    assert len(rows) == 2
    assert rows[1]["company"] == "코스닥시장본부"
    assert rows[1]["code"] == "-"


def test_auto_downloads_a_fresh_snapshot_each_time(monkeypatch, tmp_path):
    import scraper_krx

    downloads = []
    processed = []

    def download():
        path = tmp_path / f"snapshot-{len(downloads)}.xls"
        path.touch()
        downloads.append(str(path))
        return str(path)

    def process(path, keywords, **kwargs):
        assert kwargs["build_report"] is False
        processed.append(path)
        return {"count": 1}

    monkeypatch.setattr(scraper_krx, "download_today_disclosures", download)
    monkeypatch.setattr(pipeline, "generate_report_from_agent_md", process)
    monkeypatch.setattr(pipeline, "save_report", lambda *args: pytest.fail("배치에서 브라우저를 열면 안 됩니다"))
    pipeline.main(["--auto", "--no-report"])
    pipeline.main(["--auto", "--no-report"])
    assert processed == downloads
    assert len(set(downloads)) == 2


def test_auto_does_not_reuse_old_files_when_download_fails(monkeypatch):
    import scraper_krx

    monkeypatch.setattr(scraper_krx, "download_today_disclosures", lambda: None)
    monkeypatch.setattr(pipeline, "generate_report_from_agent_md", lambda *args, **kwargs: pytest.fail("오래된 파일 처리"))
    with pytest.raises(SystemExit):
        pipeline.main(["--auto", "--no-report"])


@pytest.mark.parametrize("submitter", ["유가증권시장본부", "코스닥시장본부"])
@pytest.mark.parametrize("company", [None, float("nan"), "N/A", "시장 전체"])
def test_missing_company_is_stored_as_confirmed_submitter(company, submitter):
    assert storage_company(company, submitter) == submitter
    assert display_company(company, "대량매매내역", submitter) == submitter
    assert storage_company("정상기업", submitter) == "정상기업"


def test_unknown_submitter_does_not_invent_a_company():
    assert display_company(None, "자기주식매매 신청내역", None) == "회사명 미제공"


@pytest.mark.parametrize("bypass", [False, True])
def test_empty_result_message_never_becomes_a_disclosure(monkeypatch, bypass):
    frame = pd.DataFrame([
        ["결과값이 없습니다."] * 5,
        ["20:01", "정상기업", 1, "임시주주총회 결과", "정상기업"],
        ["20:02", "정상기업", 1, "결과값이 없습니다.", "정상기업"],
    ], columns=["시간", "회사명", "종목코드", "공시제목", "제출인"])
    captured = []
    monkeypatch.setattr(pipeline, "try_read_excel", lambda _: frame)
    monkeypatch.setattr(pipeline, "upload_classified_rows_to_supabase", lambda rows, _: captured.extend(rows))
    result = pipeline.generate_report_from_agent_md("unused.xls", [], bypass_time_filter=bypass, build_report=False)
    assert result["count"] == 1
    assert [row["title"] for row in captured] == ["임시주주총회 결과"]


def test_uploader_rejects_placeholder_even_when_called_directly(monkeypatch):
    monkeypatch.setattr(pipeline.requests, "post", lambda *args, **kwargs: pytest.fail("안내문을 업로드하면 안 됩니다"))
    assert pipeline.upload_classified_rows_to_supabase([item(" 결과값이 없습니다. ")], "does-not-exist.xls") == 0


def test_date_archive_uses_database_aggregation(monkeypatch):
    import run_server

    class Response:
        status_code = 200

        def json(self):
            return [
                {"disclosure_date": "2026-10-26"},
            ]

    def get(url, **kwargs):
        assert url.endswith('/rest/v1/rpc/disclosure_archive_dates')
        return Response()

    monkeypatch.setattr(run_server.requests, "get", get)
    assert asyncio.run(run_server.get_dates()) == ["2026-10-26"]
