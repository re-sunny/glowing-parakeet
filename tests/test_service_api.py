import requests
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from service_api import create_service_router


def make_client(handler):
    app = FastAPI()
    app.include_router(create_service_router(handler, 'https://example.invalid', {'apikey': 'not-a-real-key'}, lambda rows: rows))
    return TestClient(app)


def reply(data, status=200):
    return type('Reply', (), {'status_code': status, 'json': lambda self: data})()


def test_full_count_and_query_are_not_limited_to_500():
    seen = []
    def get(url, **kwargs):
        seen.append((url, kwargs['params']))
        return reply({'items': [{'code': '005930'}], 'total': 1200, 'page': 11, 'page_size': 50})
    response = make_client(get).get('/api/explore', params={'q': 'A%,"B', 'code': '005930', 'page': 11, 'exclude': True, 'codes': '005930,000660'})
    assert response.status_code == 200
    assert response.json()['total'] == 1200
    assert response.json()['has_more'] is True
    assert seen[0][1]['search_text'] == 'A%,"B'
    assert seen[0][1]['selected_codes'] == '{005930,000660}'
    assert seen[0][1]['exclude_text'] == 'true'
    assert seen[0][0].endswith('/rpc/disclosure_search_page')


@pytest.mark.parametrize('params', [
    {'code': "005930')"}, {'page': 0}, {'size': 101},
    {'category': 'unknown'}, {'start': '2026-10-31', 'end': '2025-01-01'},
    {'codes': '005930,bad'}, {'q': 'a' * 121}
])
def test_invalid_filters_never_reach_database(params):
    client = make_client(lambda *a, **k: pytest.fail('invalid filters must not query DB'))
    assert client.get('/api/explore', params=params).status_code == 422


def test_empty_watchlist_is_an_explicit_empty_filter():
    seen = []
    def get(url, **kwargs):
        seen.append(kwargs['params'])
        return reply({'items': [], 'total': 0, 'page': 1, 'page_size': 50})
    result = make_client(get).get('/api/explore?codes=')
    assert result.status_code == 200
    assert seen[0]['selected_codes'] == '{}'
    assert result.json()['has_more'] is False


def test_upstream_error_does_not_disclose_private_url_or_key():
    def get(*args, **kwargs):
        raise requests.ConnectionError('secret-placeholder-key on private URL')
    result = make_client(get).get('/api/explore')
    assert result.status_code == 502
    assert 'secret-placeholder' not in result.text


def test_collection_status_missing_is_unknown_not_success():
    result = make_client(lambda *a, **k: reply([])).get('/api/collection-status?day=2026-10-30')
    assert result.status_code == 200
    assert result.json()['run'] is None
    assert 'succeeded' not in result.text


def test_collection_status_failure_preserves_main_service():
    result = make_client(lambda *a, **k: reply({}, 503)).get('/api/collection-status')
    assert result.status_code == 200
    assert result.json()['unavailable'] is True
