"""KIND 상세검색에서 날짜별 20시 이후 공시를 보충 수집한다."""
import argparse
import datetime as dt
import json
import re
import tempfile
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from disclosure_rules import clean_cell, classify_title, is_no_result, storage_company
from read_excel_auto import upload_classified_rows_to_supabase
from scraper_krx import create_chrome_driver, is_access_denied

DETAILS_URL = "https://kind.krx.co.kr/disclosure/details.do?method=searchDetailsMain"
KST = dt.timezone(dt.timedelta(hours=9))


def parse_history_page(html, target_date):
    """내림차순 공시 표를 검증한다. 20시 전 행이 나오면 더 이전 페이지는 불필요하다."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#main-contents table")
    if table is None:
        raise ValueError("KIND 공시 결과 표가 없습니다.")
    if any(is_no_result(cell.get_text(strip=True)) for cell in table.select("td")):
        return [], True
    rows = table.select("tbody tr")
    if not rows:
        raise ValueError("빈 표에 조회 결과 없음 안내도 없습니다.")
    items, previous = [], None
    reached_cutoff = False
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            raise ValueError(f"공시 표의 칼럼 구성이 변경됐습니다: {[cell.get_text(strip=True) for cell in cells]}")
        timestamp = dt.datetime.strptime(cells[1].get_text(strip=True), "%Y-%m-%d %H:%M")
        if timestamp.date() != target_date:
            raise ValueError(f"조회 날짜 불일치: 요청 {target_date}, 응답 {timestamp.date()}")
        if previous is not None and timestamp > previous:
            raise ValueError("공시 목록이 시간 내림차순이 아닙니다.")
        previous = timestamp
        if timestamp.hour < 20:
            reached_cutoff = True
            continue
        company_link = cells[2].find("a")
        company = company_link.get_text(strip=True) if company_link else "nan"
        submitter = clean_cell(cells[4].get_text(strip=True))
        title = cells[3].get_text(strip=True)
        if not title or is_no_result(title):
            continue
        # KIND 회사 요약 링크의 5자리 회사 코드는 보통주 종목코드의 앞 5자리다.
        # 링크가 없는 시장 전체 자료는 기존 XLS와 동일한 시장 코드를 사용한다.
        match = re.search(r"companysummary_open\('([A-Za-z0-9]+)'", company_link.get("onclick", "")) if company_link else None
        if match and len(match[1]) == 5:
            code = match[1] + "0"
        elif match and len(match[1]) == 6:
            code = match[1]
        elif company_link:
            raise ValueError(f"종목코드를 확인할 수 없습니다: {company}")
        else:
            code = {"유가증권시장본부": "999990", "코스닥시장본부": "999980", "파생상품시장본부": "999970"}.get(submitter, "nan")
        item = dict(time=timestamp.strftime("%H:%M"), company=storage_company(company, submitter),
                    code=code, title=title, submitter=submitter, category=classify_title(title))
        source_link = cells[3].find('a')
        receipt = re.search(r"openDisclsViewer\(['\"]([0-9]{14})['\"]", source_link.get('onclick', '')) if source_link else None
        if receipt:
            from disclosure_links import VIEWER_URL
            item['source_url'] = VIEWER_URL + receipt[1]
        items.append(item)
    next_page = next((a for a in soup.select("#main-contents a") if a.get_text(strip=True) == "다음 페이지"), None)
    return items, reached_cutoff or next_page is None


class HistoricalCollector:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kind-history-")
        self.driver = None

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        finally:
            self.driver = None
            self.temp.cleanup()

    def reset(self):
        if self.driver:
            self.driver.quit()
        self.driver = create_chrome_driver(self.temp.name)
        self.driver.get(DETAILS_URL)
        WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#main-contents table")))
        if is_access_denied(self.driver):
            raise RuntimeError("KIND 접근 제한")

    def collect(self, target_date):
        if self.driver is None:
            self.reset()
        driver = self.driver
        for field_id in ("fromDate", "toDate"):
            field = driver.find_element(By.ID, field_id)
            driver.execute_script("arguments[0].value = arguments[1];", field, target_date.isoformat())
        old_table = driver.find_element(By.CSS_SELECTOR, "#main-contents table")
        driver.find_element(By.CSS_SELECTOR, "a.search-btn").click()
        WebDriverWait(driver, 30).until(EC.staleness_of(old_table))
        items = []
        for _ in range(100):
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#main-contents table tbody tr")))
            page_items, done = parse_history_page(driver.page_source, target_date)
            items.extend(page_items)
            if done:
                return items
            old_table = driver.find_element(By.CSS_SELECTOR, "#main-contents table")
            driver.find_element(By.XPATH, "//*[@id='main-contents']//a[normalize-space(.)='다음 페이지']").click()
            WebDriverWait(driver, 30).until(EC.staleness_of(old_table))
            time.sleep(1)
        raise RuntimeError("하루 검색 페이지가 안전 한도(100페이지)를 초과했습니다.")


def run_backfill(start, end, checkpoint, dry_run=False, delay=1.5):
    if end < start:
        raise ValueError("종료일이 시작일보다 이릅니다.")
    if end >= dt.datetime.now(KST).date():
        raise ValueError("미완료된 오늘 자료를 피하도록 종료일은 어제 이전으로 지정하세요.")
    checkpoint = Path(checkpoint)
    state = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else {"dates": {}}
    # dry-run 결과로 실제 적재가 완료됐다고 간주하지 않는다.
    state_key = "preview_dates" if dry_run else "dates"
    completed = state.setdefault(state_key, {})
    collector = HistoricalCollector()
    try:
        day = start
        while day <= end:
            key = day.isoformat()
            if key not in completed:
                for attempt in range(3):
                    try:
                        if attempt:
                            collector.reset()
                        items = collector.collect(day)
                        break
                    except Exception as error:
                        print(f"{key}: 시도 {attempt + 1}/3 실패: {error}", flush=True)
                        if attempt == 2:
                            raise RuntimeError(f"{key} 수집 실패. 완료 기록을 유지하고 중단합니다.") from error
                        else:
                            time.sleep(5 * (attempt + 1))
                if items and not dry_run:
                    upload_classified_rows_to_supabase(items, disclosure_date=key)
                completed[key] = {"matched": len(items)}
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                temporary = checkpoint.with_suffix(".tmp")
                temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(checkpoint)
                print(f"{key}: 20시 이후 {len(items)}건, {'미리보기' if dry_run else '완료'}", flush=True)
                time.sleep(delay)
            day += dt.timedelta(days=1)
    finally:
        collector.close()
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2025, 1, 1))
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.datetime.now(KST).date() - dt.timedelta(days=1))
    parser.add_argument("--checkpoint", default="reports/backfill_checkpoint.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_backfill(args.start, args.end, args.checkpoint, args.dry_run)


if __name__ == "__main__":
    main()
