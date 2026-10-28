"""공시와 KIND 접수번호 목록을 연결하는 공통 규칙."""
import re
import hashlib
import json
from disclosure_rules import clean_cell

SEARCH_URL = 'https://kind.krx.co.kr/disclosure/details.do'
VIEWER_URL = 'https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno='


def compact(value):
    return re.sub(r'\s+', '', clean_cell(value))


def disclosure_identity(date, clock, company, code, title, submitter):
    # 해외법인은 KIND 회사 코드(SGP07 등)와 XLS 종목코드가 서로 다르다.
    # 회사명·시각·제목·제출인을 모두 대조하고 중복 후보는 확정하지 않는다.
    fields = [date, clock, compact(company), compact(title), compact(submitter)]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode('utf-8')).hexdigest()


def identity_for_row(row, date):
    return disclosure_identity(date, row['time'], row['company'], row['code'], row['title'], row['submitter'])
