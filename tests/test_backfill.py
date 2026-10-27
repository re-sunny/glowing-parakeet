import datetime as dt
import json
import asyncio

import pytest

import backfill_disclosures as backfill
import read_excel_auto as pipeline


def page(rows, next_page=False):
    return ('<div id="main-contents"><table><tbody>' + ''.join(rows) + '</tbody></table>'
            + ('<a onclick="fnPageGo2(2)">다음 페이지</a>' if next_page else '') + '</div>')


def row(timestamp, company="테스트", submitter="시장감시위원회", title="투자경고종목지정"):
    name = f"<a onclick=\"companysummary_open('00593');return false;\">{company}</a>" if company else ''
    return f'<tr><td>1</td><td>{timestamp}</td><td>{name}</td><td>{title}</td><td>{submitter}</td></tr>'


def test_history_uses_twenty_hour_cutoff_and_source_date():
    html = page([row('2025-06-02 20:15'), row('2025-06-02 20:00'), row('2025-06-02 19:59')], True)
    items, done = backfill.parse_history_page(html, dt.date(2025, 6, 2))
    assert [item['time'] for item in items] == ['20:15', '20:00']
    assert items[0]['code'] == '005930'
    assert done is True


def test_history_continues_pagination_when_every_row_is_after_twenty():
    items, done = backfill.parse_history_page(page([row('2025-06-02 20:00')], True), dt.date(2025, 6, 2))
    assert len(items) == 1
    assert done is False


def test_history_preserves_market_submitter_and_xls_market_code():
    items, done = backfill.parse_history_page(page([row('2025-06-02 20:03', '', '코스닥시장본부', '대량매매내역')]), dt.date(2025, 6, 2))
    assert items[0]['company'] == '코스닥시장본부'
    assert items[0]['code'] == '999980'


def test_no_late_disclosures_and_empty_result_are_successful_empty_days():
    assert backfill.parse_history_page(page([row('2025-01-02 18:30')], True), dt.date(2025, 1, 2)) == ([], True)
    assert backfill.parse_history_page(page(['<tr><td colspan="6">결과값이 없습니다.</td></tr>']), dt.date(2025, 1, 1)) == ([], True)
    assert backfill.parse_history_page(page(['<tr><td colspan="6">조회된 결과값이 없습니다.</td></tr>']), dt.date(2025, 1, 1)) == ([], True)


def test_wrong_date_and_wrong_sort_fail_instead_of_saving():
    with pytest.raises(ValueError, match='날짜 불일치'):
        backfill.parse_history_page(page([row('2026-10-27 20:00')]), dt.date(2025, 6, 2))
    with pytest.raises(ValueError, match='내림차순'):
        backfill.parse_history_page(page([row('2025-06-02 20:00'), row('2025-06-02 20:01')]), dt.date(2025, 6, 2))


def test_historical_upload_uses_explicit_date_not_download_time(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.invalid')
    monkeypatch.setenv('SUPABASE_KEY', 'test-key')
    seen = []

    def post(*args, **kwargs):
        seen.extend(kwargs['json'])
        return type('Response', (), {'status_code': 201})()

    monkeypatch.setattr(pipeline.requests, 'post', post)
    items, _ = backfill.parse_history_page(page([row('2025-06-02 20:00')]), dt.date(2025, 6, 2))
    pipeline.upload_classified_rows_to_supabase(items, disclosure_date='2025-06-02')
    assert seen[0]['disclosure_date'] == '2025-06-02'


def test_checkpoint_marks_only_successful_days_and_dry_run_is_separate(monkeypatch, tmp_path):
    class Collector:
        def collect(self, day):
            return [dict(time='20:00', title='투자경고')]

        def close(self):
            pass

    monkeypatch.setattr(backfill, 'HistoricalCollector', Collector)
    monkeypatch.setattr(backfill.time, 'sleep', lambda _: None)
    checkpoint = tmp_path / 'progress.json'
    day = dt.date(2025, 1, 2)
    backfill.run_backfill(day, day, checkpoint, dry_run=True)
    assert json.loads(checkpoint.read_text())['dates'] == {}
    monkeypatch.setattr(backfill, 'upload_classified_rows_to_supabase', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('DB failure')))
    with pytest.raises(RuntimeError, match='DB failure'):
        backfill.run_backfill(day, day, checkpoint)
    assert json.loads(checkpoint.read_text())['dates'] == {}


def test_date_archive_includes_records_beyond_ten_thousand(monkeypatch):
    import run_server

    def get(url, *, headers, timeout):
        page = int(headers['Range'].split('-')[0]) // 1000
        date = (dt.date(2025, 1, 12) - dt.timedelta(days=page)).isoformat()
        data = [{'disclosure_date': date, 'title': '투자경고', 'time': '20:00'}] * (1000 if page < 11 else 1)
        return type('Response', (), {'status_code': 200, 'json': lambda self: data})()

    monkeypatch.setattr(run_server.requests, 'get', get)
    assert '2025-01-01' in asyncio.run(run_server.get_dates())


def test_date_archive_accepts_out_of_range_after_full_last_page(monkeypatch):
    import run_server

    def get(url, *, headers, timeout):
        first = headers['Range'] == '0-999'
        data = ([{'disclosure_date': '2025-01-06', 'title': 'ETF 신규상장', 'time': '20:00'}] * 1000
                if first else {'code': 'PGRST103'})
        return type('Response', (), {'status_code': 200 if first else 416, 'json': lambda self: data})()

    monkeypatch.setattr(run_server.requests, 'get', get)
    assert asyncio.run(run_server.get_dates()) == ['2025-01-06']
