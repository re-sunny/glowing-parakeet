"""KIND 접수번호를 수집해 기존·신규 공시의 원문 연결 정보를 보충한다."""
import argparse
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from disclosure_links import SEARCH_URL, VIEWER_URL, disclosure_identity, identity_for_row
from disclosure_rules import display_company, clean_cell, is_no_result

_session = None
_defaults = None


def parse_links(html, date):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    count = 0
    before_cutoff = False
    previous = None
    for row in soup.select('table tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) < 5:
            continue
        stamp = cells[1].get_text(strip=True)
        timestamp = dt.datetime.strptime(stamp, '%Y-%m-%d %H:%M')
        if timestamp.date().isoformat() != date:
            raise ValueError('KIND 검색 날짜 불일치')
        if previous is not None and timestamp > previous:
            raise ValueError('KIND 목록이 시간 내림차순이 아닙니다')
        previous = timestamp
        count += 1
        if timestamp.hour < 20:
            before_cutoff = True
            continue
        company_link = cells[2].find('a')
        submitter = clean_cell(cells[4].get_text(strip=True))
        title = clean_cell(cells[3].get_text(strip=True))
        company = display_company(company_link.get_text(strip=True) if company_link else '', title, submitter)
        code_match = re.search(r"companysummary_open\('([A-Za-z0-9]+)'", company_link.get('onclick', '')) if company_link else None
        code = code_match[1] if code_match else {'유가증권시장본부': '999990', '코스닥시장본부': '999980', '파생상품시장본부': '999970'}.get(submitter, '-')
        link = cells[3].find('a')
        receipt = re.search(r"openDisclsViewer\(['\"]([0-9]{14})['\"]", link.get('onclick', '')) if link else None
        if receipt:
            identity = disclosure_identity(date, timestamp.strftime('%H:%M'), company, code, title, submitter)
            items.append({'identity': identity, 'receipt_id': receipt[1], 'disclosure_date': date})
    if count == 0 and not any(is_no_result(td.get_text()) for td in soup.select('td')):
        raise ValueError('KIND 원문 목록 응답을 확인할 수 없습니다')
    return items, count < 100 or before_cutoff


def collect_day(session, defaults, date):
    fields = dict(defaults, method='searchDetailsSub', forward='details_sub', fromDate=date, toDate=date, currentPageSize='100', orderMode='1', orderStat='D')
    items = []
    for page in range(1, 101):
        fields['pageIndex'] = str(page)
        response = session.post(SEARCH_URL, data=fields, timeout=20)
        response.raise_for_status()
        found, done = parse_links(response.text, date)
        items.extend(found)
        if done:
            return items
        time.sleep(.15)
    raise ValueError('원문 목록이 페이지 한도를 초과했습니다')


def collect_source_map(date):
    global _session, _defaults
    try:
        if _session is None:
            _session = requests.Session()
            _session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': SEARCH_URL + '?method=searchDetailsMain'})
            response = _session.get(SEARCH_URL, params={'method': 'searchDetailsMain'}, timeout=20)
            response.raise_for_status()
            form = BeautifulSoup(response.text, 'html.parser').select_one('#searchForm')
            if form is None:
                raise ValueError('KIND 검색 양식을 확인할 수 없습니다')
            _defaults = {x['name']: x.get('value', '') for x in form.select('input[name]') if x.get('type') != 'checkbox' and (x.get('type') != 'radio' or x.has_attr('checked'))}
        items = collect_day(_session, _defaults, date)
    except (requests.RequestException, ValueError):
        if _session:
            _session.close()
        _session = None
        # Actions에서 HTTP 요청이 제한되면 기존 수집기와 같은 브라우저 경로를 쓴다.
        from backfill_disclosures import HistoricalCollector
        collector = HistoricalCollector()
        try:
            rows = collector.collect(dt.date.fromisoformat(date))
            items = [{'identity': identity_for_row(row, date), 'receipt_id': row['source_url'].split('acptno=')[1]} for row in rows if row.get('source_url')]
        finally:
            collector.close()
    candidates = {}
    for item in items:
        candidates.setdefault(item['identity'], set()).add(item['receipt_id'])
    return {key: VIEWER_URL + next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat())
    parser.add_argument('--all-stored-dates', action='store_true')
    parser.add_argument('--checkpoint', default='reports/disclosure_links_checkpoint.json')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
    from run_server import SUPABASE_URL, SUPABASE_KEY
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or SUPABASE_KEY
    headers = {'apikey': key, 'Authorization': 'Bearer ' + key}
    dates = [dt.date.fromisoformat(args.date).isoformat()]
    checkpoint = Path(args.checkpoint)
    stored = []
    if args.all_stored_dates:
        for offset in range(0, 100000, 1000):
            response = requests.get(SUPABASE_URL + '/rest/v1/disclosures', headers={**headers, 'Range': f'{offset}-{offset+999}'},
                                    params={'select': 'id,disclosure_date,time,company,code,title,submitter', 'order': 'id.asc'}, timeout=20)
            if response.status_code == 416:
                break
            response.raise_for_status()
            page = response.json()
            stored.extend(page)
            if len(page) < 1000:
                break
        dates = sorted({r['disclosure_date'] for r in stored if not is_no_result(r['title'])}, reverse=True)
    updates = []
    for date in dates:
        output = Path(f'reports/source_links_v2_{date}.json')
        if args.all_stored_dates and output.exists() and json.loads(output.read_text('utf-8')):
            source_map = json.loads(output.read_text('utf-8'))
        else:
            for attempt in range(3):
                try:
                    source_map = collect_source_map(date)
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
            output.parent.mkdir(exist_ok=True, parents=True)
            output.write_text(json.dumps(source_map, ensure_ascii=False), encoding='utf-8')
        day_updates = []
        for row in stored:
            if row['disclosure_date'] != date:
                continue
            source_url = source_map.get(identity_for_row(row, date))
            if source_url:
                day_updates.append({'id': row['id'], 'source_url': source_url})
        updates.extend(day_updates)
        print(f'{date}: 원문 연결 {len(source_map)}건, 기존 공시 일치 {len(day_updates)}건', flush=True)
        if args.all_stored_dates:
            write_update_sql(Path(f'reports/source_links_update_{date}.sql'), day_updates)
        time.sleep(.2)
    if args.all_stored_dates:
        for offset in range(0, len(updates), 3000):
            write_update_sql(Path(f'reports/source_links_update_batch_{offset//3000+1}.sql'), updates[offset:offset+3000])
        checkpoint.write_text(json.dumps({'dates': len(dates), 'matched_rows': len(updates)}), encoding='utf-8')


def write_update_sql(path, updates):
    payload = json.dumps(updates)
    path.write_text("with changed as (update public.disclosures d set source_url=l.source_url from jsonb_to_recordset($kindlinks$" + payload + "$kindlinks$::jsonb) as l(id bigint,source_url text) where d.id=l.id and d.source_url is null returning d.id) select count(*) as updated_rows from changed;", encoding='utf-8')


if __name__ == '__main__':
    main()
