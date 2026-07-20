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

app = FastAPI(title="KIND Disclosure Dashboard Server")

# CORS 허용 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 캐시 방지를 위한 미들웨어 설정 (실시간 데이터 조회 무결성 보장)
class DisableCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

app.add_middleware(DisableCacheMiddleware)

# Supabase 접속 정보 설정 (서버 측 안전 보존)
SUPABASE_URL = "https://uyqmlrivrrjjzcuxbttj.supabase.co"
SUPABASE_KEY = "sb_publishable_KkQB5rDmsV7R5ZkPsMt3pw_bgr29KcM"

supabase_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ----------------- FastAPI API Routes -----------------

@app.get("/api/dates")
async def get_dates():
    try:
        url = f"{SUPABASE_URL}/rest/v1/disclosures?select=disclosure_date"
        response = requests.get(url, headers=supabase_headers, timeout=5)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Supabase fetch failed")
        
        data = response.json()
        dates = sorted(list(set(row["disclosure_date"] for row in data if row.get("disclosure_date"))), reverse=True)
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
        
        if query:
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
                params["limit"] = "150"
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
        else:
            # 3) 검색어가 없을 때 (단순 날짜별 목록 조회)
            if date:
                params["disclosure_date"] = f"eq.{date}"
            params["order"] = "time.desc"

        response = requests.get(url, headers=supabase_headers, params=params, timeout=5)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Supabase data query failed")
            
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- Static File Routing -----------------

# 루트 경로 진입 시 dashboard.html 반환
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return FileResponse("dashboard.html")

# 명시적인 dashboard.html 경로 지원
@app.get("/dashboard.html", response_class=HTMLResponse)
async def get_dashboard_html():
    return FileResponse("dashboard.html")

# reports 폴더가 존재할 경우 정적 파일 라우팅 추가
if os.path.exists("reports"):
    app.mount("/reports", StaticFiles(directory="reports"), name="reports")

def open_browser():
    time.sleep(1.0)
    url = "http://localhost:8000/dashboard.html"
    webbrowser.open(url)
    print(f"\n🚀 [FastAPI 백엔드 프록시] 대시보드 웹 서비스가 성공적으로 연동되었습니다: {url}")

if __name__ == "__main__":
    # 브라우저 오픈 작업 백그라운드 구동
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("📡 FastAPI & Uvicorn 프록시 웹 서버를 구동합니다...")
    uvicorn.run("run_server:app", host="127.0.0.1", port=8000, reload=True)
