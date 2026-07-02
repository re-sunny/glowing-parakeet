import os
import time
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def download_today_disclosures(download_dir=None):
    """
    Selenium을 이용해 한국거래소 KIND '오늘의 공시' 페이지에 접속하여 엑셀(XLS) 데이터 파일을 다운로드합니다.
    """
    if download_dir is None:
        download_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    
    print(f"📥 다운로드 경로 설정: {download_dir}")
    
    # 다운로드 시작 전 다운로드 폴더 내 기존 '오늘의공시*.xls/xlsx' 패턴의 구버전 잔여 파일 제거
    old_files = glob.glob(os.path.join(download_dir, "오늘의공시*.xls")) + glob.glob(os.path.join(download_dir, "오늘의공시*.xlsx"))
    for file_path in old_files:
        try:
            os.remove(file_path)
            print(f"🗑️ 기존 잔여 공시 파일 삭제 완료: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"⚠️ 기존 잔여 파일 삭제 중 오류 발생 (스킵): {e}")
            
    # 크롬 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # 백그라운드 운용 (Headless 모드)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # 자동 다운로드 경로 지정 관련 Preferences 설정
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # 웹드라이버 시작
    print("🚗 크롬 브라우저를 초기화하고 있습니다...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Headless 모드에서 다운로드가 가능하도록 CDP 연결 활성화
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir
    })

    try:
        url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain&marketType=0"
        print(f"🌐 대상 웹페이지 접속 중: {url}")
        driver.get(url)
        
        # 테이블 로드 대기 (예: 공시 데이터 테이블 클래스 또는 ID 대기)
        print("⏳ 페이지 로드 완료를 대기 중...")
        time.sleep(3) # 추가적인 렌더링 시간 버퍼
        
        # 엑셀 다운로드 버튼 탐색 및 클릭
        # KIND '오늘의 공시' EXCEL 아이콘 혹은 XLS 링크 클릭
        print("📊 'EXCEL' 다운로드 버튼을 탐색하고 있습니다...")
        
        selectors = [
            "//a[contains(@class, 'xls-btn')]",
            "//a[@title='EXCEL']",
            "//a[contains(@class, 'excel')]",
            "//a[contains(@class, 'btn-excel')]",
            "//a[contains(text(), 'EXCEL')]"
        ]
        
        excel_btn = None
        for sel in selectors:
            try:
                excel_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, sel))
                )
                if excel_btn:
                    print(f"✅ 버튼 탐지 성공 (Selector: {sel})")
                    break
            except Exception:
                continue
                
        if not excel_btn:
            raise Exception("❌ EXCEL 다운로드 버튼을 찾을 수 없습니다.")

        # 보일 때까지 대기 후 스크롤 & 클릭
        driver.execute_script("arguments[0].scrollIntoView(true);", excel_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", excel_btn)
        print("🖱️ 다운로드 클릭 명령을 전송했습니다. 파일 다운로드를 대기하는 중...")
        
        # 다운로드 대기 (다운로드 중 임시 파일 `.crdownload` 상태 대기 포함)
        timeout = 30
        start_time = time.time()
        downloaded = False
        
        while time.time() - start_time < timeout:
            # xls나 xlsx 최신 파일 탐색
            files = glob.glob(os.path.join(download_dir, "*.xls")) + glob.glob(os.path.join(download_dir, "*.xlsx"))
            # 임시 파일이 존재하는지 체크
            temp_files = glob.glob(os.path.join(download_dir, "*.crdownload"))
            
            if files and not temp_files:
                # 최근에 파일이 새로 다운로드 되었는지 메타 데이터 검정 가능
                latest_file = max(files, key=os.path.getmtime)
                # 다운받은지 1분 이내의 새 파일 확인
                if time.time() - os.path.getmtime(latest_file) < 60:
                    print(f"🎉 오늘의 공시 다운로드 성공: {os.path.basename(latest_file)}")
                    downloaded = True
                    return latest_file
            time.sleep(1)
            
        if not downloaded:
            print("⚠️ 다운로드 대기 시간이 초과되었습니다.")
            return None

    except Exception as e:
        print(f"❌ 크롤링 중 오류가 발생했습니다: {e}")
        return None
    finally:
        driver.quit()
        print("🔒 크롬 브라우저를 닫았습니다.")

if __name__ == "__main__":
    download_today_disclosures()
