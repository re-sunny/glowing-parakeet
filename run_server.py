# -*- coding: utf-8 -*-
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import webbrowser
import threading
import time
import os
import requests
from disclosure_rules import classify_title, clean_cell, clean_code, display_company, is_placeholder_disclosure

app = FastAPI(title="KIND Disclosure Dashboard Server")

# CORS 허용 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 공개 조회는 CDN에서 60초간 재사용한다. 수동 새로고침과 오류는 캐시하지 않는다.
class QueryCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if (response.status_code == 200
                and request.url.path in {"/api/dates", "/api/disclosures"}
                and request.query_params.get("refresh") != "1"):
            response.headers["Cache-Control"] = "public, max-age=0, s-maxage=60"
        else:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

app.add_middleware(QueryCacheMiddleware)

from dotenv import load_dotenv

load_dotenv()

# Supabase 접속 정보 설정 (환경 변수 우선, 미설정 시 기본값 폴백)
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "https://uyqmlrivrrjjzcuxbttj.supabase.co").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "sb_publishable_KkQB5rDmsV7R5ZkPsMt3pw_bgr29KcM"

supabase_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ----------------- FastAPI API Routes -----------------

@app.get("/api/dates")
async def get_dates():
    try:
        # DB에서 중복 제거·안내문 제외를 끝내 날짜만 전송한다.
        # 날짜가 1000개를 넘는 장기 아카이브도 Range로 이어서 읽는다.
        url = f"{SUPABASE_URL}/rest/v1/rpc/disclosure_archive_dates"
        dates_set = set()
        page = 0
        while True:
            headers = dict(supabase_headers)
            headers["Range"] = f"{page * 1000}-{(page + 1) * 1000 - 1}"
            response = requests.get(url, headers=headers, timeout=15)
            # 전체 행 수가 정확히 1000의 배수면 다음 범위는 416으로 끝날 수 있다.
            if page > 0 and response.status_code == 416 and response.json().get("code") == "PGRST103":
                break
            if response.status_code not in [200, 206]:
                raise RuntimeError(f"공시 날짜 조회 실패: HTTP {response.status_code}")
            data = response.json()
            if not isinstance(data, list) or not data:
                break
            for row in data:
                if row.get("disclosure_date"):
                    dates_set.add(row["disclosure_date"])
            if len(data) < 1000:
                break
            page += 1

        dates = sorted(list(dates_set), reverse=True)
        return dates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/disclosures")
async def get_disclosures(
    date: str = Query(None, description="조회할 날짜 (YYYY-MM-DD)"),
    query: str = Query(None, description="실시간 검색 쿼리"),
    ignoreDate: bool = Query(False, description="날짜 조건 여부 무시 여부 (전역 검색)"),
    exclude: bool = Query(False, description="검색 키워드 포함 대상에서 제외 여부")
):
    try:
        url = f"{SUPABASE_URL}/rest/v1/disclosures"
        params = {}
        
        if query and isinstance(query, str):
            q = query.strip()
            # 1) 날짜 무시 전역 검색 시
            if ignoreDate:
                if exclude:
                    params["company"] = f"not.ilike.%{q}%"
                    params["code"] = f"not.ilike.%{q}%"
                    params["title"] = f"not.ilike.%{q}%"
                    params["submitter"] = f"not.ilike.%{q}%"
                else:
                    params["or"] = f"(company.ilike.%{q}%,code.ilike.%{q}%,title.ilike.%{q}%,submitter.ilike.%{q}%)"
                params["order"] = "disclosure_date.desc,time.desc"
                params["limit"] = "500"
            # 2) 날짜 지정 내 검색 시
            else:
                if date:
                    params["disclosure_date"] = f"eq.{date}"
                if exclude:
                    params["company"] = f"not.ilike.%{q}%"
                    params["code"] = f"not.ilike.%{q}%"
                    params["title"] = f"not.ilike.%{q}%"
                    params["submitter"] = f"not.ilike.%{q}%"
                else:
                    params["or"] = f"(company.ilike.%{q}%,code.ilike.%{q}%,title.ilike.%{q}%,submitter.ilike.%{q}%)"
                params["order"] = "time.desc"
                params["limit"] = "1000"
        else:
            # 3) 검색어가 없을 때 (단순 날짜별 목록 조회)
            if date:
                params["disclosure_date"] = f"eq.{date}"
            params["order"] = "time.desc"
            params["limit"] = "1000"

        response = requests.get(url, headers=supabase_headers, params=params, timeout=15)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Supabase data query failed")
            
        rows = [row for row in response.json() if not is_placeholder_disclosure(row)]
        for row in rows:
            # 과거 저장된 nan 및 잘못된 분류도 조회 시 동일한 규칙으로 보정한다.
            row["company"] = display_company(row.get("company"), row.get("title"), row.get("submitter"))
            row["code"] = clean_code(row.get("code"))
            row["title"] = clean_cell(row.get("title"))
            row["submitter"] = clean_cell(row.get("submitter"))
            row["category"] = classify_title(row["title"])
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 루트 경로 진입 시 dashboard.html 반환
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

# 명시적인 dashboard.html 경로 지원
@app.get("/dashboard.html", response_class=HTMLResponse)
async def get_dashboard_html():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

# reports 폴더가 존재할 경우 정적 파일 라우팅 추가
reports_dir = os.path.join(BASE_DIR, "reports")
if os.path.exists(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")

def open_browser():
    time.sleep(1.0)
    url = "http://localhost:5000/dashboard.html"
    webbrowser.open(url)
    print(f"\n🚀 [FastAPI 백엔드 프록시] 대시보드 웹 서비스가 성공적으로 연동되었습니다: {url}")

if __name__ == "__main__":
    # 브라우저 오픈 작업 백그라운드 구동
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("📡 FastAPI & Uvicorn 프록시 웹 서버를 구동합니다...")
    uvicorn.run("run_server:app", host="127.0.0.1", port=5000, reload=True)
