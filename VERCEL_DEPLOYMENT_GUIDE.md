# 🚀 Vercel을 활용한 KIND 공시 대시보드 100% 무료 배포 가이드

본 가이드는 **KIND 기업 공시 자동화 파이프라인 및 대시보드**를 **Vercel** 서비스에 100% 무료로 배포하여 내 웹사이트 주소(`https://xxxx.vercel.app`)를 생성하는 방법을 초보자의 눈높이에 맞춰 상세히 안내합니다.

---

## 🏗️ 1. 전체 배포 구조 이해하기

배포가 완료되면 다음과 같은 구조로 시스템이 동작합니다:

```
[ 매일 20:05 ] ➡️ GitHub Actions (자동 크롤링) ➡️ Supabase Cloud DB (영구 보존)
                                                       │
                                                       ▼
[ 사용자의 브라우저 ] ⬅️ Vercel (FastAPI 무제한 무료 웹 호스팅) ⬅️ DB 데이터 조회
```

* **데이터 수집 & DB**: 이미 GitHub Actions 및 Supabase가 연동되어 있으므로 별도 설정이 필요 없습니다.
* **웹 대시보드**: Vercel이 파이썬 백엔드(`run_server.py`) 및 프론트엔드(`dashboard.html`)를 무료로 호스팅해 줍니다.

---

## 🛠️ 2. 배포 준비 단계 (코드 커밋)

프로젝트 내에 Vercel 전용 설정 파일인 `vercel.json`과 서버 경로 보정 작업이 이미 완벽히 세팅되어 있습니다.

터미널에서 아래 명령어로 수정된 사항을 Git에 저장(Commit) 및 Push합니다:

```bash
# 1. 변경된 파일 전체 등록
git add .

# 2. 커밋 메시지 작성
git commit -m "feat: Prepare Vercel serverless deployment config"

# 3. GitHub 원격 저장소에 업로드
git push origin master
```

---

## 🌐 3. Vercel 웹 사이트에서 클릭 몇 번으로 배포하기 (가장 추천하는 방법)

### **Step 1. Vercel 로그인**
1. 웹 브라우저를 열고 **[https://vercel.com](https://vercel.com)** 에 접속합니다.
2. 오른쪽 상단 **[Sign Up]** (또는 Log In) 버튼을 클릭합니다.
3. **`Continue with GitHub`**를 클릭하여 본인의 깃허브 계정으로 로그인합니다.

---

### **Step 2. 프로젝트 가져오기 (Import)**
1. Vercel 대시보드 메인 화면에서 오른쪽 상단의 **[Add New...]** 버튼 ➔ **[Project]**를 선택합니다.
2. `Import Git Repository` 목록에서 본인의 **`excel_read`** (또는 해당 저장소명) 프로젝트를 탐색합니다.
3. 해당 프로젝트 오른쪽의 **[Import]** 버튼을 클릭합니다.

---

### **Step 3. 배포 실행 (Deploy)**
1. `Configure Project` 설정 화면이 나타납니다.
   * **Framework Preset**: `Other` (자동 인식됨)
   * **Root Directory**: `./` (기본값 그대로 유지)
   * **Environment Variables**: 입력할 내용 없음 (서버 측에 이미 설정되어 있음)
2. 하단의 **[Deploy]** 버튼을 누릅니다.
3. 약 30초~1분간 폭죽 애니메이션과 함께 빌드가 진행됩니다.

---

### **Step 4. 배포 완료 및 접속 테스트**
1. 빌드가 완료되면 **`Congratulations!`** 화면이 뜬다.
2. 화면 중앙의 대시보드 미리보기 이미지 또는 **[Visit]** 버튼을 클릭합니다.
3. 부여받은 무료 주소 (예: `https://excel-read-xxxx.vercel.app`)로 대시보드가 정상 구동되는지 확인합니다.

---

## 💻 4. 터미널(CLI) 명령어로 배포하는 대안 방법

웹 사이트 방문 없이 명령어로 즉시 배포하고 싶으신 경우:

```bash
# Vercel CLI 배포 명령 실행
npx vercel
```

1. 명령어를 입력하면 `Set up and deploy?` 메시지가 뜹니다. `y`를 입력하고 Enter를 누릅니다.
2. 브라우저 창이 열리면 **[Log In]** 및 **[Verify]**를 클릭하여 인증을 마칩니다.
3. 터미널의 모든 질문(Scope, Project Name 등)에서 **Enter** 키만 눌러 기본값을 선택합니다.
4. 배포 완료 후 출력되는 `Production: https://...` URL을 클릭하여 접속합니다.

---

## 🔄 5. 향후 업데이트 방법

추후 코드를 수정하거나 기능을 추가한 후에는 **GitHub에 Push만 하면 Vercel이 이를 감지하여 자동으로 새 버전으로 재배포**됩니다:

```bash
git add .
git commit -m "Update dashboard features"
git push origin master
```
(Push 완료 후 1분 이내에 웹 사이트에 자동 반영됩니다.)

---

🎉 **축하합니다! 이제 누구나 24시간 언제 어디서나 접속할 수 있는 나만의 기업 공시 리스크 모니터링 포털이 완성되었습니다.**
