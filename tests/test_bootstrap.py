import pytest
from fastapi import HTTPException

import run_server


def response(data, status=200):
    return type('Response', (), {'status_code': status, 'json': lambda self: data})()


def test_bootstrap_uses_one_db_call_and_keeps_existing_normalization(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return response({'dates': ['2026-10-26', '2025-01-06'], 'date': '2026-10-26', 'disclosures': [
            {'title': '결과값이 없습니다.'},
            {'title': '상장폐지에 따른 매매거래정지', 'company': 'nan', 'submitter': '코스닥시장본부', 'code': '999980'},
        ]})

    monkeypatch.setattr(run_server, 'database_get', get)
    data = run_server.get_bootstrap()
    assert len(calls) == 1
    assert calls[0].endswith('/rpc/disclosure_dashboard_bootstrap')
    assert data['dates'] == ['2026-10-26', '2025-01-06']
    assert len(data['disclosures']) == 1
    assert data['disclosures'][0]['company'] == '코스닥시장본부'
    assert data['disclosures'][0]['category'] == 'others'


@pytest.mark.parametrize('data,status', [({}, 200), ([], 200), ({}, 500)])
def test_bootstrap_rejects_invalid_or_failed_database_response(monkeypatch, data, status):
    monkeypatch.setattr(run_server, 'database_get', lambda *args, **kwargs: response(data, status))
    with pytest.raises(HTTPException):
        run_server.get_bootstrap()


def test_empty_database_bootstrap_is_valid(monkeypatch):
    payload = {'dates': [], 'date': None, 'disclosures': []}
    monkeypatch.setattr(run_server, 'database_get', lambda *args, **kwargs: response(payload))
    assert run_server.get_bootstrap() == payload
