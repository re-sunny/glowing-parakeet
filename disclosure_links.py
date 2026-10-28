"""기존 공시 목록을 KIND의 실제 접수번호와 대조한다. 본문은 수집하지 않는다."""
import re
import time
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup

from disclosure_rules import clean_cell, storage_company

SEARCH_URL = "https://kind.krx.co.kr/disclosure/details.do"
VIEWER_URL = "https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno="
_cache = OrderedDict()


class DisclosureLinkError(Exception):
    pass


def compact(value):
    return re.sub(r"\s+", "", clean_cell(value))


def matching_receipts(html, date, clock, company, code, title, submitter):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tbody tr")
    receipts = set()
    valid_rows = 0
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        valid_rows += 1
        if cells[1].get_text(strip=True) != f"{date} {clock}":
            continue
        if compact(cells[3].get_text()) != compact(title):
            continue
        actual_submitter = cells[4].get_text(strip=True)
        if compact(actual_submitter) != compact(submitter):
            continue
        company_link = cells[2].find("a")
        actual_company = storage_company(company_link.get_text(strip=True) if company_link else "", actual_submitter)
        if compact(actual_company) != compact(company):
            continue
        company_code = re.search(r"companysummary_open\('([A-Za-z0-9]+)'", company_link.get("onclick", "")) if company_link else None
        if company_code and str(code)[:5] != company_code[1][:5]:
            continue
        for link in cells[3].find_all("a"):
            receipt = re.search(r"openDisclsViewer\(['\"]([0-9]{14})['\"]", link.get("onclick", ""))
            if receipt:
                receipts.add(receipt[1])
    if not valid_rows and not any(x in soup.get_text() for x in ("결과값이 없습니다", "조회된 결과가 없습니다")):
        raise DisclosureLinkError("KIND 검색 응답을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.")
    return receipts, valid_rows


def resolve_disclosure_url(date, clock, company, code, title, submitter):
    identity = (date, clock, company, code, title, submitter)
    cached = _cache.get(identity)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    deadline = time.monotonic() + 20

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise DisclosureLinkError("KIND 조회가 지연되고 있습니다. 잠시 후 다시 시도해 주세요.")
        return min(5, seconds)

    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": SEARCH_URL + "?method=searchDetailsMain"})
            response = session.get(SEARCH_URL, params={"method": "searchDetailsMain"}, timeout=remaining())
            response.raise_for_status()
            form = BeautifulSoup(response.text, "html.parser").select_one("#searchForm")
            if form is None:
                raise DisclosureLinkError("KIND 검색에 접속할 수 없습니다. 잠시 후 다시 시도해 주세요.")
            # KIND는 빈 검색 필드도 포함한 양식과 세션을 요구한다.
            fields = {x["name"]: x.get("value", "") for x in form.select("input[name]")
                      if x.get("type") != "checkbox" and (x.get("type") != "radio" or x.has_attr("checked"))}
            fields.update(method="searchDetailsSub", forward="details_sub", fromDate=date, toDate=date,
                          currentPageSize="100", reportNm=compact(title))
            receipts = set()
            for page in range(1, 11):
                fields["pageIndex"] = str(page)
                response = session.post(SEARCH_URL, data=fields, timeout=remaining())
                response.raise_for_status()
                matches, count = matching_receipts(response.text, *identity)
                receipts.update(matches)
                if count < 100:
                    break
            else:
                raise DisclosureLinkError("검색 결과가 많아 원문을 확정할 수 없습니다. KIND 상세검색을 이용해 주세요.")
    except requests.RequestException as error:
        raise DisclosureLinkError("KIND 연결이 지연되거나 제한됐습니다. 잠시 후 다시 시도해 주세요.") from error
    if len(receipts) != 1:
        raise DisclosureLinkError("일치하는 원문을 하나로 확인하지 못했습니다. KIND 상세검색에서 확인해 주세요.")
    url = VIEWER_URL + receipts.pop()
    _cache[identity] = (time.monotonic() + 600, url)
    _cache.move_to_end(identity)
    while len(_cache) > 256:
        _cache.popitem(last=False)
    return url
