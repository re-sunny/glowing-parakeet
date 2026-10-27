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


def display_company(company, title):
    company = clean_cell(company)
    if company != "-":
        return company
    compact = re.sub(r"\s+", "", clean_cell(title))
    if any(word in compact for word in (
        "자기주식매매", "대량매매내역", "회전율", "일중변동성",
        "거래량증가율", "최근20일중", "기타시장안내"
    )):
        return "시장 전체"
    return "회사명 미제공"


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
