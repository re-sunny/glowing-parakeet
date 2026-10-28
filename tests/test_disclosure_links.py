import datetime as dt
import pytest
from collect_disclosure_links import parse_links
from disclosure_links import disclosure_identity, VIEWER_URL
from backfill_disclosures import parse_history_page


def row(company='ACE 글로벌빅파마', code='49751', receipt='20261028000801', clock='20:22'):
    return f'''<tr><td>1</td><td>2026-10-28 {clock}</td>
    <td><a onclick="companysummary_open('{code}')">{company}</a></td>
    <td><a onclick="openDisclsViewer('{receipt}','')">ETF 분배락 기준가격 안내</a></td>
    <td>유가증권시장본부</td></tr>'''


def table(rows):
    return '<div id="main-contents"><table><tbody>' + rows + '</tbody></table></div>'


def test_identity_distinguishes_company_time_and_title():
    identity = disclosure_identity('2026-10-28','20:22','ACE 글로벌빅파마','497510','ETF 분배락 기준가격 안내','유가증권시장본부')
    items, done = parse_links(table(row() + row('다른 ETF', '00593', '20261028000802') + row(clock='20:21')), '2026-10-28')
    assert items[0]['identity'] == identity
    assert len({r['identity'] for r in items}) == 3
    assert done


def test_market_missing_company_matches_stored_submitter_name():
    html = table('''<tr><td>1</td><td>2026-10-28 20:00</td><td></td>
    <td><a onclick="openDisclsViewer('20261028000001','')">대량매매내역</a></td><td>코스닥시장본부</td></tr>''')
    rows, _ = parse_links(html, '2026-10-28')
    assert rows[0]['identity'] == disclosure_identity('2026-10-28','20:00','코스닥시장본부','999980','대량매매내역','코스닥시장본부')


def test_error_wrong_date_invalid_receipt_and_time_cutoff():
    with pytest.raises(ValueError): parse_links('<html>Access Denied</html>', '2026-10-28')
    with pytest.raises(ValueError): parse_links(table(row()), '2025-01-01')
    assert parse_links(table(row(receipt='https://evil.invalid')), '2026-10-28')[0] == []
    assert parse_links(table(row(clock='19:59')), '2026-10-28') == ([], True)
    with pytest.raises(ValueError): parse_links(table(row(clock='20:00') + row(clock='20:22')), '2026-10-28')


def test_historical_parser_preserves_official_viewer_url():
    rows, _ = parse_history_page(table(row()), dt.date(2026,10,28))
    assert rows[0]['source_url'] == VIEWER_URL + '20261028000801'


def test_foreign_kind_company_code_can_differ_from_stock_code():
    assert disclosure_identity('2026-10-28','20:00','프레스티지바이오파마','SGP07','투자주의','시장감시위원회') == disclosure_identity('2026-10-28','20:00','프레스티지바이오파마','950210','투자주의','시장감시위원회')
