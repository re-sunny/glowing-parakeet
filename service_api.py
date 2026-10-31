"""KIND 서비스의 공개 검색과 상태 응답. 관리자·DART 데이터는 읽지 않는다."""
from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query

CATEGORIES = {'caution', 'overheating', 'warning_risk_trading', 'short_selling', 'others'}


def create_service_router(database_get, base_url, headers, normalize):
    router = APIRouter()

    @router.get('/api/explore')
    def explore(q: str = Query('', max_length=120), code: str | None = Query(None, pattern=r'^\d{6}$'),
                start: Date | None = None, end: Date | None = None,
                category: str | None = None, exclude: bool = False,
                codes: str | None = Query(None, max_length=699),
                page: int = Query(1, ge=1, le=100000), size: int = Query(50, ge=1, le=100)):
        if start and end and start > end:
            raise HTTPException(422, '시작일은 종료일보다 늦을 수 없습니다.')
        if category and category not in CATEGORIES:
            raise HTTPException(422, '잘못된 공시 유형입니다.')
        selected = None
        if codes is not None:
            import re
            selected = list(dict.fromkeys(codes.split(','))) if codes else []
            if len(selected) > 100 or any(not re.fullmatch(r'\d{6}', value) for value in selected):
                raise HTTPException(422, '잘못된 종목 필터입니다.')
        params = {
            'search_text': q.strip(), 'security_code': code,
            'date_from': start.isoformat() if start else None,
            'date_to': end.isoformat() if end else None,
            'category_filter': category, 'exclude_text': exclude,
            'selected_codes': selected, 'page_number': page, 'page_size': size,
        }
        try:
            response = database_get(f'{base_url}/rest/v1/rpc/disclosure_search_page',
                                    headers=headers, params={k: ('{' + ','.join(v) + '}' if isinstance(v, list) else
                                    str(v).lower() if isinstance(v, bool) else v)
                                    for k, v in params.items() if v is not None}, timeout=15)
            if response.status_code != 200:
                raise ValueError('query failed')
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not isinstance(data.get('total'), int):
                raise ValueError('invalid response')
            data['items'] = normalize(data['items'])
            data['has_more'] = page * size < data['total']
            data['scope'] = '20:00 이후 수집 공시 · 문서 기준'
            return data
        except Exception:
            raise HTTPException(502, '공시 검색을 완료하지 못했습니다. 다시 시도해 주세요.') from None

    @router.get('/api/collection-status')
    def collection_status(day: Date | None = None):
        params = {'select': 'run_id,target_date,state,started_at,completed_at,stored_count,origin',
                  'order': 'started_at.desc', 'limit': '1'}
        if day:
            params['target_date'] = f'eq.{day.isoformat()}'
        try:
            response = database_get(f'{base_url}/rest/v1/kind_collection_runs', headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                raise ValueError('status unavailable')
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError('invalid status')
            return {'run': rows[0] if rows else None, 'schedule': '평일 20:15 KST',
                    'coverage': '20:00 이후 수집분이며 수집 이후 등록 공시는 포함되지 않을 수 있습니다.'}
        except Exception:
            return {'run': None, 'unavailable': True, 'schedule': '평일 20:15 KST'}

    return router
