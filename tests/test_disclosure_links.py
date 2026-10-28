import pytest
from fastapi.testclient import TestClient

import disclosure_links as links
import run_server


IDENTITY = ('2026-10-28', '20:22', 'ACE 글로벌빅파마', '497510', 'ETF 분배락 기준가격 안내', '유가증권시장본부')


def row(company='ACE 글로벌빅파마', code='49751', receipt='20261028000801', clock='20:22'):
    return f'''<tr><td>1</td><td>2026-10-28 {clock}</td>
    <td><a onclick="companysummary_open('{code}')">{company}</a></td>
    <td><a onclick="openDisclsViewer('{receipt}','')">ETF 분배락 기준가격 안내</a></td>
    <td>유가증권시장본부</td></tr>'''


def table(rows):
    return '<table><tbody>' + rows + '</tbody></table>'


def test_same_title_does_not_link_another_company_or_time():
    html = table(row() + row('다른 ETF', '00593', '20261028000802') + row(clock='20:21'))
    receipts, count = links.matching_receipts(html, *IDENTITY)
    assert receipts == {'20261028000801'}
    assert count == 3
    assert links.matching_receipts(table(row(code='00593')), *IDENTITY)[0] == set()


def test_invalid_receipt_and_error_page_are_not_links():
    assert links.matching_receipts(table(row(receipt='https://evil.invalid')), *IDENTITY)[0] == set()
    with pytest.raises(links.DisclosureLinkError):
        links.matching_receipts('<html>Access Denied</html>', *IDENTITY)


def test_market_submitter_is_used_when_company_is_missing():
    html = table('''<tr><td>1</td><td>2026-10-28 20:00</td><td></td>
    <td><a onclick="openDisclsViewer('20261028000001','')">대량매매내역</a></td><td>코스닥시장본부</td></tr>''')
    assert links.matching_receipts(html, '2026-10-28', '20:00', '코스닥시장본부', '999980', '대량매매내역', '코스닥시장본부')[0] == {'20261028000001'}


def test_ambiguous_matches_fail_and_success_is_cached(monkeypatch):
    links._cache.clear()
    pages = [table(row() + row(receipt='20261028000802'))]
    class Response:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
    class Session:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return Response('<form id="searchForm"><input name="orderMode" value=""></form>')
        def post(self, *args, **kwargs): return Response(pages.pop(0))
    monkeypatch.setattr(links.requests, 'Session', Session)
    with pytest.raises(links.DisclosureLinkError): links.resolve_disclosure_url(*IDENTITY)
    pages.append(table(row()))
    assert links.resolve_disclosure_url(*IDENTITY) == links.VIEWER_URL + '20261028000801'
    assert links.resolve_disclosure_url(*IDENTITY) == links.VIEWER_URL + '20261028000801'
    assert pages == []
    links._cache.clear()


def test_redirect_and_safe_failure_page(monkeypatch):
    client = TestClient(run_server.app)
    params = dict(zip(('date','time','company','code','title','submitter'), IDENTITY))
    monkeypatch.setattr(run_server, 'resolve_disclosure_url', lambda *args: links.VIEWER_URL + '20261028000801')
    response = client.get('/api/disclosure-link', params=params, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'].endswith('acptno=20261028000801')
    def fail(*args): raise links.DisclosureLinkError('원문 확인 실패')
    monkeypatch.setattr(run_server, 'resolve_disclosure_url', fail)
    params['title'] = '<script>alert(1)</script>'
    response = client.get('/api/disclosure-link', params=params)
    assert response.status_code == 502
    assert '<script>' not in response.text
    assert '&lt;script&gt;' in response.text
    assert response.headers['cache-control'].startswith('no-store')
