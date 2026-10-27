"""공시 수집과 조회에서 함께 사용하는 정규화·분류 규칙."""
import re

import pandas as pd


def clean_cell(value, default="-"):
    if pd.isna(value):
        return default
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "n/a", "na", "<na>", "-"}:
        return default
    return text


def clean_code(value):
    text = clean_cell(value)
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text.zfill(6) if text.isdigit() else text


MARKET_SUBMITTERS = {"유가증권시장본부", "코스닥시장본부"}


def storage_company(company, submitter):
    """실제 회사명은 유지하고, 미제공된 회사명은 확인된 시장본부로 보완한다."""
    name = clean_cell(company)
    source = re.sub(r"\s+", "", clean_cell(submitter))
    if name in {"-", "시장 전체", "회사명 미제공"} and source in MARKET_SUBMITTERS:
        return source
    return clean_cell(company, default="nan")


def display_company(company, title, submitter=None):
    company = storage_company(company, submitter)
    company = clean_cell(company)
    if company != "-":
        return company
    return "회사명 미제공"


def is_no_result(value):
    compact = re.sub(r"[\s.!。！]+", "", clean_cell(value))
    return compact in {
        "결과값이없습니다", "조회결과가없습니다", "검색결과가없습니다",
        "조회된데이터가없습니다", "검색된데이터가없습니다",
        "조회된결과값이없습니다",
    }


def is_placeholder_disclosure(row):
    # KIND의 colspan 안내문은 pandas에서 각 칼럼에 같은 문구로 반복된다.
    # 실제 '주주총회 결과' 등 공시 제목은 이 정확 일치 조건에 포함되지 않는다.
    return is_no_result(row.get("title")) or is_no_result(row.get("time"))


def classify_title(title):
    title = re.sub(r"\s+", "", clean_cell(title))
    # 상장폐지에 따른 매매정지를 시장경보(투자위험)로 표시하지 않는다.
    if "상장폐지" in title:
        return "others"
    if any(word in title for word in (
        "거래정지", "정지해제", "매매정지", "투자경고", "투자위험", "투자주의경고", "매매거래"
    )):
        return "warning_risk_trading"
    if "단기과열" in title:
        return "overheating"
    if any(word in title for word in ("투자주의", "환기종목")):
        return "caution"
    if "공매도" in title:
        return "short_selling"
    return "others"
