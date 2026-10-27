import asyncio
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse

from run_server import QueryCacheMiddleware, app


@pytest.mark.parametrize('path,params,status,cacheable', [
    ('/api/dates', {}, 200, True),
    ('/api/bootstrap', {}, 200, True),
    ('/api/bootstrap', {'refresh': '1'}, 200, False),
    ('/api/disclosures', {'date': '2026-10-26'}, 200, True),
    ('/api/dates', {'refresh': '1'}, 200, False),
    ('/api/disclosures', {'date': '2026-10-26', 'refresh': '1'}, 200, False),
    ('/api/dates', {}, 500, False),
    ('/', {}, 200, False),
])
def test_only_successful_ordinary_queries_use_short_cdn_cache(path, params, status, cacheable):
    async def next_response(request):
        return JSONResponse([], status_code=status)

    request = SimpleNamespace(url=SimpleNamespace(path=path), query_params=params)
    response = asyncio.run(QueryCacheMiddleware(app).dispatch(request, next_response))
    policy = response.headers['Cache-Control']
    assert ('s-maxage=60' in policy) is cacheable
    assert ('no-store' in policy) is not cacheable
