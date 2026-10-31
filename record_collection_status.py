"""Actions의 실제 수집 결과를 공개 가능한 최소 상태로 기록한다."""
import argparse
import datetime as dt
import os
import requests


def record(state):
    base = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    run = os.getenv('GITHUB_RUN_ID', '')
    attempt = os.getenv('GITHUB_RUN_ATTEMPT', '1')
    if not base or not key or not run.isdigit() or not attempt.isdigit():
        print('::warning::수집 상태 기록을 사용할 수 없습니다. 기존 수집 결과는 유지합니다.')
        return False
    now = dt.datetime.now(dt.timezone.utc)
    target = now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    identity = f'{run}:{attempt}'
    url = f'{base}/rest/v1/kind_collection_runs'
    try:
        if state == 'running':
            response = requests.post(url, headers={**headers, 'Prefer': 'resolution=merge-duplicates,return=minimal'},
                                     params={'on_conflict': 'run_id'},
                                     json={'run_id': identity, 'target_date': target, 'state': state,
                                           'started_at': now.isoformat(), 'completed_at': None,
                                           'stored_count': None, 'origin': 'collector'}, timeout=15)
        else:
            count = None
            if state == 'succeeded':
                result = requests.get(f'{base}/rest/v1/disclosures',
                                      headers={**headers, 'Prefer': 'count=exact'},
                                      params={'select': 'id', 'disclosure_date': f'eq.{target}', 'limit': '1'}, timeout=15)
                result.raise_for_status()
                count = int(result.headers['content-range'].split('/')[-1])
            response = requests.patch(url, params={'run_id': f'eq.{identity}'},
                                      headers={**headers, 'Prefer': 'return=representation'},
                                      json={'state': state, 'completed_at': now.isoformat(), 'stored_count': count}, timeout=15)
            if response.status_code == 200 and not response.json():
                raise ValueError('missing running record')
        if response.status_code not in (200, 201, 204):
            raise ValueError('status write rejected')
        print(f'수집 상태 기록: {state}')
        return True
    except Exception:
        # 요청 URL·headers·인증정보·내부 오류는 공개 로그나 테이블에 쓰지 않는다.
        print('::warning::수집 상태를 확인하지 못했습니다. 홈페이지에는 확인 불가로 표시합니다.')
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('state', choices=['running', 'succeeded', 'failed'])
    record(parser.parse_args().state)
