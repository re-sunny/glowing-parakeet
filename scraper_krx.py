import os
import sys
import time
import glob
import random


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Windows CP949 console encoding fix
if sys.platform.startswith('win'):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')


def create_chrome_driver(download_dir):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": download_dir
    })
    return driver


def is_access_denied(driver):
    title = (driver.title or '').strip().lower()
    url = (driver.current_url or '').strip().lower()
    body_text = ''
    try:
        body_text = (driver.find_element(By.TAG_NAME, "body").text or '').strip().lower()
    except Exception:
        body_text = ''
    return 'access denied' in title or 'access denied' in body_text or 'access denied' in url


def download_today_disclosures(download_dir=None, max_retries=3, retry_delay=8):
    """
    Selenium을 이용해 한국거래소 KIND '오늘의 공시' 페이지에 접속하여 엑셀(XLS) 데이터 파일을 다운로드합니다.
    간헐적인 Access Denied 차단에 대비해 재시도합니다.
    """
    if download_dir is None:
        download_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()

    print(f"📥 다운로드 경로 설정: {download_dir}")

    old_files = glob.glob(os.path.join(download_dir, "오늘의공시*.xls")) + glob.glob(os.path.join(download_dir, "오늘의공시*.xlsx"))
    for file_path in old_files:
        try:
            os.remove(file_path)
            print(f"🗑️ 기존 잔여 공시 파일 삭제 완료: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"⚠️ 기존 잔여 파일 삭제 중 오류 발생 (스킵): {e}")

    url = "https://kind.krx.co.kr/disclosure/todaydisclosure.do?method=searchTodayDisclosureMain&marketType=0"

    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            print(f"🚗 크롬 브라우저를 초기화하고 있습니다... (시도 {attempt}/{max_retries})")
            driver = create_chrome_driver(download_dir)
            print(f"🌐 대상 웹페이지 접속 중: {url}")
            driver.get(url)
            print("⏳ 페이지 로드 완료를 대기 중...")
            time.sleep(3)

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
                if is_access_denied(driver):
                    print("⚠️ Access Denied로 판단되어 재시도합니다.")
                else:
                    print(f"DEBUG: [진단] 현재 페이지 타이틀: '{driver.title}'")
                    print(f"DEBUG: [진단] 현재 페이지 주소(URL): '{driver.current_url}'")
                    try:
                        page_text = driver.find_element(By.TAG_NAME, "body").text
                        print(f"DEBUG: [진단] Body 텍스트 (앞 300자):\n{page_text[:300]}")
                    except Exception:
                        print(f"DEBUG: [진단] 페이지 소스 요약 (앞 300자):\n{driver.page_source[:300]}")
                raise Exception("❌ EXCEL 다운로드 버튼을 찾을 수 없습니다.")

            driver.execute_script("arguments[0].scrollIntoView(true);", excel_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", excel_btn)
            print("🖱️ 다운로드 클릭 명령을 전송했습니다. 파일 다운로드를 대기하는 중...")

            timeout = 30
            start_time = time.time()
            downloaded = False

            while time.time() - start_time < timeout:
                files = glob.glob(os.path.join(download_dir, "*.xls")) + glob.glob(os.path.join(download_dir, "*.xlsx"))
                temp_files = glob.glob(os.path.join(download_dir, "*.crdownload"))

                if files and not temp_files:
                    latest_file = max(files, key=os.path.getmtime)
                    if time.time() - os.path.getmtime(latest_file) < 60:
                        print(f"🎉 오늘의 공시 다운로드 성공: {os.path.basename(latest_file)}")
                        return latest_file
                time.sleep(1)

            print("⚠️ 다운로드 대기 시간이 초과되었습니다.")
            return None

        except Exception as e:
            print(f"❌ 크롤링 중 오류가 발생했습니다: {e}")
            if attempt < max_retries:
                wait_seconds = retry_delay + random.uniform(0, 3)
                print(f"🔁 {wait_seconds:.1f}초 뒤 재시도합니다...")
                time.sleep(wait_seconds)
                continue
            return None
        finally:
            if driver is not None:
                driver.quit()
                print("🔒 크롬 브라우저를 닫았습니다.")

    return None


if __name__ == "__main__":
    download_today_disclosures()
