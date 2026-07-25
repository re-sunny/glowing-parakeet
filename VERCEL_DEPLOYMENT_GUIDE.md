# 🚀 [블로그 원고] KIND 기업 공시 자동화 파이프라인 & Vercel 100% 무료 배포 완벽 가이드

> **요약**: 한국거래소(KRX) KIND '오늘의 공시' 데이터를 매일 자동 수집하고, FastAPI 백엔드와 Supabase DB를 연동하여 **Vercel** 무제한 무료 서버리스 플랫폼에 배포하는 전체 과정을 정리한 기술 블로그 원고입니다. Velog, Tistory, Medium 등에 바로 게시하실 수 있습니다.

---

## 📌 1. 들어가는 글 & 프로젝트 소개

주식 시장에서 **투자경고, 단기과열, 공매도 과열, 매매거래정지** 등의 공시는 종목 리스크 관리에 매우 치명적인 요소입니다. 하지만 매일 저녁 거래소 사이트에 직접 접속해 일일이 확인하는 것은 대단히 번거롭습니다.

본 프로젝트는 **한국거래소(KRX) KIND 공시 시스템**을 자동 크롤링하여 주요 규제 리스크 5대 카테고리로 분류한 뒤, **서버 유지비 0원(100% 무료)**으로 클라우드에 영구 적재 및 웹 대시보드로 시각화하는 파이프라인입니다.

### 🏗️ 전체 시스템 아키텍처

```
[ 매일 월~금 20:05 ] ➡️ GitHub Actions (Selenium 크롤링) ➡️ Supabase Cloud DB (영구 저장)
                                                             │
                                                             ▼
[ 사용자 웹 브라우저 ] ⬅️ Vercel Serverless (FastAPI 대시보드) ⬅️ DB 데이터 실시간 조회
```

1. **데이터 수집**: GitHub Actions 가상 머신이 매일 20:05에 실행되어 KIND 공시 엑셀 데이터를 자동으로 다운로드 및 파싱합니다.
2. **데이터 저장**: 추출된 리스크 항목은 Supabase 클라우드 DB에 전송(Upsert)되어 영구 보존됩니다.
3. **웹 호스팅**: Vercel의 Python Serverless 기능으로 FastAPI 백엔드 및 대시보드 UI를 24시간 무료로 서빙합니다.

---

## 🛠️ 2. 기술 스택 (Tech Stack)

* **Backend**: Python 3.11, FastAPI, Uvicorn, Requests
* **Crawler & Parser**: Selenium, Webdriver Manager, Pandas, BeautifulSoup4
* **Database**: Supabase Cloud DB (PostgreSQL REST API)
* **CI/CD**: GitHub Actions (Schedule Cron)
* **Hosting**: Vercel (Serverless Functions)
* **Frontend**: Vanilla HTML5, CSS3, JavaScript, html2canvas

---

## 💻 3. Vercel 배포를 위한 프로젝트 설정 핵심 포인트

### ① Vercel 설정 파일 (`vercel.json`)
Vercel에 Python FastAPI 애플리케이션을 서버리스 형태로 배포하려면 프로젝트 루트에 `vercel.json` 파일이 필요합니다.

```json
{
    "builds": [
        {
            "src": "run_server.py",
            "use": "@vercel/python"
        }
    ],
    "routes": [
        {
            "src": "/(.*)",
            "dest": "run_server.py"
        }
    ]
}
```

### ② 서버리스 경로 참조 보정 (`BASE_DIR` 패턴)
로컬 환경과 달리 Vercel Serverless Function 환경에서는 현재 작업 디렉터리(Cwd) 위치가 달라질 수 있습니다. `dashboard.html`이나 정적 리소스를 반환할 때는 **절대 경로 방식**으로 지정해야 404/500 에러를 방지할 수 있습니다.

```python
# run_server.py
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))
```

---

## 🌐 4. Vercel 웹 UI로 1분 만에 배포하기 (추천)

### **Step 1. GitHub 저장소에 최신 코드 푸시**
```bash
git add .
git commit -m "feat: Ready for Vercel deployment"
git push origin master
```

### **Step 2. Vercel 회원가입 및 저장소 가져오기**
1. [https://vercel.com](https://vercel.com)에 접속합니다.
2. **`Sign Up`** ➔ **`Continue with GitHub`**를 클릭하여 깃허브 계정으로 로그인합니다.
3. Vercel 메인 대시보드에서 **[Add New...]** ➔ **[Project]**를 선택합니다.
4. 내 저장소 목록에서 `glowing-parakeet` (또는 프로젝트 저장소명) 옆의 **[Import]** 버튼을 누릅니다.

### **Step 3. Deploy 실행**
1. `Framework Preset`: `Other` 선택 (기본값)
2. `Root Directory`: `./` 선택 (기본값)
3. 하단의 **[Deploy]** 버튼을 클릭합니다.
4. 약 30초~1분 후 빌드가 완료되면 `https://your-project.vercel.app` 형태의 **전용 보안(HTTPS) 도메인이 무료 발급**됩니다!

---

## ⌨️ 5. 터미널(CLI) 명령어로 배포하기

웹 UI 접속 없이 터미널 명령어로 배포하는 것도 가능합니다.

```bash
# 1. Vercel CLI 인증 및 배포 실행
npx vercel --prod
```

1. 명령어를 실행하면 브라우저 인증 창이 나타납니다. **[Confirm]** 버튼을 누르면 로그인이 완료됩니다.
2. 터미널의 모든 질문에서 Enter 키를 눌러 기본값을 선택하면 자동으로 프로젝트 생성 및 프로덕션 배포가 완성됩니다.

---

## 🔄 6. 자동화 파이프라인 & 유지 관리 (CI/CD)

### **GitHub Push 시 자동 재배포**
Vercel과 GitHub 저장소가 연동되었기 때문에, 추후 대시보드 코드를 수정하고 `git push`를 실행하면 **Vercel이 이를 자동으로 감지하여 1분 이내에 새 버전으로 재배포**합니다.

```bash
# 코드 수정 후 Push만 하면 자동 배포 완료!
git add .
git commit -m "update: Enhance dashboard search filters"
git push origin master
```

### **크롤러 재시도 메커니즘 (Selenium Robustness)**
한국거래소 KIND 사이트는 순간적인 네트워크 지연이나 과부하로 엑셀 다운로드 버튼이 감지되지 않을 수 있습니다. 
이를 위해 `scraper_krx.py`에는 **5가지 XPath 선택자 교체 검색 + 8~11초 무작위 대기 + 브라우저 재가동 방식의 3회 자동 재시도(Retry Loop)**가 구현되어 있어 100% 수집 무결성을 보장합니다.

---

## 🎉 7. 마무리하며

이제 내 컴퓨터를 24시간 켜둘 필요 없이, **GitHub Actions + Supabase + Vercel** 삼각편대를 활용해 100% 무료로 동작하는 기업 공시 리스크 감지 포털이 구축되었습니다.

금융 데이터 수집 자동화나 파이썬 웹 서비스 무료 배포를 고민하시는 분들께 도움이 되기를 바랍니다!
