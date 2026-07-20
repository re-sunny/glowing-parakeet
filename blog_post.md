# 📊 로컬 PC를 켜두지 않고, 무료로 매일 크롤링 자동화하기 (GitHub Actions + Supabase)

파이썬으로 웹 크롤러(Scraper)를 개발한 뒤 항상 마주하는 고민이 있습니다.

> "내가 지정한 시간(예: 매일 저녁 8시 5분)에 이 크롤러가 자동으로 돌게 하려면 어떻게 해야 할까?"

로컬 컴퓨터의 작업 스케줄러나 crontab에 등록해 둘 수도 있지만, 그러려면 컴퓨터가 24시간 내내 켜져 있어야 합니다. 그렇다고 작은 개인 프로젝트나 장난감 크롤러 하나 때문에 AWS EC2 같은 유료 호스팅 서버를 상시 결제해서 켜놓는 것도 지갑 사정에 부담스럽습니다.

이 문제를 우아하게 해결하기 위한 구원투수가 바로 **GitHub Actions**와 **Supabase**의 조합입니다.

---

## 💡 GitHub Actions란? (게다가 무료!)

GitHub Actions는 원래 소프트웨어 배포(CI/CD) 자동화를 위한 개발 도구입니다. 하지만 본질은 **특정 이벤트나 스케줄(Cron)에 맞춰 일시적으로 클라우드 가상 컴퓨터를 대여해서 우리가 짠 코드를 실행해주는 서비스**에 가깝습니다.

### 💰 진짜 100% 무료일까요?
개인 사용자 입장에서는 비대면 크롤링 용도로는 완벽히 무료로 쓸 수 있습니다.
* **공개(Public) 저장소**: 사용 제한이 없는 **전면 무제한 무료**.
* **비공개(Private) 저장소**: 매달 **2,000분의 무료 빌드 시간** 제공.
* *팁: 하루에 딱 1회 기동하여 1~2분 정도 엑셀을 받고 종료되는 크롤러라면 한 달에 60분도 사용하지 않기 때문에 요금이 전혀 청구되지 않습니다.*

---

## 🛠️ 실전 아키텍처: 수집과 조회의 깔끔한 디커플링

이번 프로젝트의 최종 정돈된 데이터 수집 흐름도입니다.

```
[GitHub Actions 가상 머신 시작] ➡️ 매일 20:05 정각 기동 (UTC 11:05)
                        │
                        ▼
[오늘의공시.xls 크롤링] ➡️ Selenium 패키지로 한국거래소 KIND 페이지 접속 및 엑셀 다운로드
                        │
                        ▼
[엑셀 파싱 및 DB 적재] ➡️ Pandas로 적합도 필터링 후 Supabase Cloud DB로 즉각 적재 (Upsert)
                        │
                        ▼
[가상 컴퓨터 자동 폭파] ➡️ 수집 가상 컴퓨터가 리포지토리 파일 변경 없이 증발 (Git 이력 청정 유지!)
```

사용자는 자신의 컴퓨터를 켜둘 필요가 없고, 매일 쌓이는 수많은 백업 엑셀 파일이나 마크다운 임시 보고서가 소스코드 레포지토리 기록을 뒤덮어 더럽히는 비효율을 방지할 수 있습니다.

---

## 🛠️ GitHub Actions 간단 적용 방법

의외로 GitHub Actions를 세팅하여 내 크롤러를 스케줄러로 돌리는 방법은 매우 심플합니다.

### 1단계: `.github/workflows/` 폴더에 설정 파일 넣기
프로젝트 루트 폴더에 `.github` 폴더를 만들고 그 안에 `workflows` 폴더를 개설합니다. 그리고 자동화할 시간과 작동 명령을 담은 yaml 설정 파일을 생성합니다 (예: `kind_collector.yml`).

```yaml
name: KIND Disclosure Daily Collector

on:
  schedule:
    - cron: '5 11 * * *'  # 매일 한국 시간 20:05 실행 (UTC 11:05)
  workflow_dispatch:      # 깃허브 웹에서 수동으로도 실행 가능하게 만들어주는 옵션

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - name: 저장소 체크아웃
        uses: actions/checkout@v3

      - name: 파이썬 설정
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: 의존성 라이브러리 설치
        run: |
          pip install -r requirements.txt

      - name: 크롤러 및 적재 스크립트 실행
        run: |
          python scraper_krx.py
          python read_excel_auto.py --auto --file 오늘의공시.xls
```

### 2단계: GitHub 원격 저장소로 Push 하기
작성한 파이썬 스크립트(`scraper_krx.py`, `read_excel_auto.py`) 파일들과 새로 개설한 `.github` 폴더 구조를 통째로 깃허브에 업로드(`git push`)합니다.

### 3단계: 확인 및 수동 실행(테스트) 해보기
1. 본인의 GitHub Repository 웹사이트에 접속한 뒤 상단 탭 중 **[Actions]** 메뉴로 들어갑니다.
2. 좌측 워크플로우 탭에서 방금 생성한 이름(`KIND Disclosure Daily Collector`)을 찾아 클릭합니다.
3. 우측에 생성된 톱니바퀴와 함께 보이는 **`Run workflow`** 버튼을 클릭하여 수동 테스트 작동을 트리거합니다.
4. 가상 러너의 작동 진행 상태가 연두색 체크 표시로 마무리되면 성공입니다! 이제 매일 해당 예약 시간(20:05)마다 클라우드 컴퓨터가 스스로 켜져 크롤러를 가동하게 됩니다.

---

## 🚨 트러블슈팅: 리눅스 가상 환경에서 만난 크래시와 해법

로컬 환경(Windows 데스크탑)에서는 화면도 보고 잘 작동하던 크롤러 소스코드가 GitHub Actions의 리눅스(Ubuntu) 헤드리스 브라우저 실행 단계에 진입하자마자 에러를 뱉었습니다.

```
❌ 크롤링 중 오류가 발생했습니다: ❌ EXCEL 다운로드 버튼을 찾을 수 없습니다.
```

### 🔍 원인 규명
개발 단계에서는 화면이 정상 크기로 뜨지만, 모니터가 존재하지 않는 GitHub Actions 가상 러너 상에서는 크롬 브라우저가 극단적으로 작은 모바일 해상도(기본값 800x600 등)로 해석됩니다.

이때 한국거래소 사이트의 **반응형(Responsive) 웹 레이아웃**이 발동하여 화면 상단에 항시 잘 노출되던 `EXCEL 다운로드` 링크 버튼이 햄버거 메뉴나 하단 서브 메뉴 레이어 뒤쪽으로 찌그러져 숨겨지는 바람에 Selenium 드라이버가 클릭 영역을 잃고 헤매는 문제였습니다.

### 💡 해결책 (Chrome Option 튜닝)
해결 방법은 브라우저를 백그라운드로 켤 때, 시뮬레이션할 기본 화면 해상도를 1080p 데스크탑 표준 크기로 고정 선언하는 것이었습니다.

```python
chrome_options = Options()
chrome_options.add_argument("--headless=new")         # 헤드리스 모드 가동
chrome_options.add_argument("--no-sandbox")            # 접근 권한 우회
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")

# 🌟 핵심 해결 키: 뷰포트를 데스크탑 정규 크기로 지정해 반응형 숨김 방지
chrome_options.add_argument("--window-size=1920,1080")
```

이렇게 해상도 튜닝 인수를 넣어주자마자, 깃허브 가상 러너가 눈코 뜰 새 없이 완벽하게 버튼을 정조준하여 다운로드 및 가공 적재 루프를 완수하게 되었습니다.

---

## 🏁 포스팅을 마치며

이번 클라우드 포탈 자동화를 통해 다음 두 가지 이점이 확보되었습니다.

1. **보안성(Security)**: 브라우저가 다이렉트로 데이터베이스 암호를 노출하지 않는 **FastAPI 백엔드 프록시 구조** 확립.
2. **이식성(Serverless)**: 24시간 도는 PC 스케줄러 의존을 탈피하고 **GitHub Actions 무료 스케줄 클라우드화** 완료.

매일 반복해서 돌려야 하는 데이터 연동이나 크롤러 데몬이 있으시다면, 비싼 서버를 비용 들여 구동하지 마시고 깃허브가 제공해주는 강력한 Actions를 적극 도입하여 자동화해 보세요!
