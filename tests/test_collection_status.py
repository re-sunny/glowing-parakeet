import record_collection_status as recorder


def test_missing_admin_key_does_not_attempt_public_write(monkeypatch):
    monkeypatch.delenv('SUPABASE_SERVICE_ROLE_KEY', raising=False)
    monkeypatch.setenv('SUPABASE_KEY', 'public-placeholder')
    monkeypatch.setattr(recorder.requests, 'post', lambda *a, **k: (_ for _ in ()).throw(AssertionError('public write')))
    assert recorder.record('running') is False


def test_success_requires_actual_stored_count_and_running_record(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.invalid')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'private-placeholder')
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    class Count:
        headers = {'content-range': '0-0/48'}
        def raise_for_status(self): pass
    monkeypatch.setattr(recorder.requests, 'get', lambda *a, **k: Count())
    seen = []
    def patch(url, **kwargs):
        seen.append(kwargs)
        return type('Reply', (), {'status_code': 200, 'json': lambda self: [{'run_id': '123:2'}]})()
    monkeypatch.setattr(recorder.requests, 'patch', patch)
    assert recorder.record('succeeded') is True
    assert seen[0]['json']['stored_count'] == 48
    assert seen[0]['params']['run_id'] == 'eq.123:2'
    assert 'private-placeholder' not in str(seen[0]['json'])


def test_status_write_failure_is_never_reported_as_success(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://example.invalid')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY', 'private-placeholder')
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setattr(recorder.requests, 'patch', lambda *a, **k: type('Reply', (), {'status_code': 403})())
    assert recorder.record('failed') is False
