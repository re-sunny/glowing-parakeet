# -*- coding: utf-8 -*-
import os
import sys
import datetime
import argparse
import pandas as pd
from langchain_ollama import OllamaLLM
from langchain_community.llms import Ollama

# Windows CP949 console encoding fix
if sys.platform.startswith('win'):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

# excel_utils.py 및 template.py 모듈로부터 도우미 함수 및 HTML 레이아웃 임포트
from excel_utils import (
    get_latest_excel_in_current_dir,
    try_read_excel,
    md_to_html,
    get_html2canvas_script,
    extract_hour_from_time_value
)
from template import (
    HTML_HEADER,
    HTML_CARD_START,
    HTML_EMPTY_STATE,
    HTML_TABLE_START,
    HTML_TABLE_ROW,
    HTML_TABLE_END,
    HTML_CARD_END,
    HTML_FOOTER
)


def generate_report_from_agent_md(file_path, search_keywords, agent_md_path="agents_auto.md", bypass_time_filter=False, no_ai=False):
    if not os.path.exists(agent_md_path):
        if os.path.exists("agents.md"):
            print("⚠️ 'agents_auto.md'가 없어 'agents.md'를 사용합니다.")
            agent_md_path = "agents.md"
        else:
            print(f"❌ '{agent_md_path}' 파일을 찾을 수 없습니다.")
            return None
        
    with open(agent_md_path, "r", encoding="utf-8") as f:
        agent_prompt_template = f.read()

    # 안전하게 엑셀 파싱 헤더 정렬 통일
    try:
        df = try_read_excel(file_path)
    except Exception as e:
        print(f"❌ 파일을 파싱하는 중 오류가 발생했습니다: {e}")
        return None

    if df is None or df.empty:
        print("❌ 엑셀 파일에 데이터가 존재하지 않습니다.")
        return None

    # 대표적인 칼럼 위치 인덱스 자동 추정
    time_col, com_col, code_col, title_col, submitter_col = None, None, None, None, None
    cols = df.columns.tolist()
    
    # 1. 컬럼명을 이용한 정확한 매핑
    if "시간" in cols: time_col = cols.index("시간")
    if "회사명" in cols: com_col = cols.index("회사명")
    if "종목코드" in cols: code_col = cols.index("종목코드")
    if "공시제목" in cols: title_col = cols.index("공시제목")
    if "제출인" in cols: submitter_col = cols.index("제출인")
    
    # 2. 컬럼명 매핑 실패 시, 데이터 분석 폴백
    if None in [time_col, com_col, code_col, title_col]:
        sample_row = [str(x).strip() for x in df.iloc[0].tolist()]
        for idx, val in enumerate(sample_row):
            if ":" in val:
                time_col = idx
            elif val.isdigit() and len(val) >= 4:
                code_col = idx
            elif len(val) > 15:
                title_col = idx
        
        if time_col is None: time_col = 1
        if com_col is None: com_col = 2
        if code_col is None: code_col = 3
        if title_col is None: title_col = 4
        
    if submitter_col is None:
        submitter_col = 5 if 5 < len(cols) else (len(cols) - 1)

    matched_rows = []
    for idx, row in df.iterrows():
        # 1. 시간 조건 검사 (20:00시부터 포함, bypass_time_filter가 True이면 건너뜀)
        if not bypass_time_filter and time_col is not None and time_col < len(row):
            time_val = row.iloc[time_col]
            hour = extract_hour_from_time_value(time_val)
            if hour is not None:
                if hour < 20:
                    continue

        # 2. 키워드 조건 검사 (지정된 키워드가 있을 경우에 필터링 적용)
        title_val = str(row.iloc[title_col]) if title_col < len(row) else ""
        if search_keywords:
            if not any(k in title_val for k in search_keywords):
                continue
                
        matched_rows.append(row)

    if not matched_rows:
        print("💡 조건에 일치하는 공시 데이터가 없습니다.")
        return {
            "empty": True,
            "msg": "✓ 조건에 일치하는 신규 우려/주의성 유의 공시 내역이 조회되지 않았습니다. 당일 시장은 안정세입니다."
        }

    # 카테고리 정의 (5개 탭 분리)
    categories = {
        "warning_risk_trading": {
            "title": "투자경고 & 투자위험 & 매매거래정지",
            "icon": "🚨",
            "color": "trading",
            "items": []
        },
        "overheating": {
            "title": "단기과열지정 관련",
            "icon": "🔥",
            "color": "overheating",
            "items": []
        },
        "caution": {
            "title": "투자주의 & 환기종목",
            "icon": "⚠️",
            "color": "caution",
            "items": []
        },
        "short_selling": {
            "title": "공매도 과열종목",
            "icon": "📉",
            "color": "short",
            "items": []
        },
        "others": {
            "title": "기타 유의사항",
            "icon": "📝",
            "color": "other",
            "items": []
        }
    }

    # 데이터 분류 및 정렬
    data_lines = []
    for row in matched_rows:
        time_val = str(row.iloc[time_col]).strip() if time_col < len(row) else "-"
        com_val = str(row.iloc[com_col]).strip() if com_col < len(row) else "-"
        code_val = str(row.iloc[code_col]).split(".")[0].strip() if code_col < len(row) else "-"
        # 종목코드 자릿수 포맷
        if len(code_val) < 6 and code_val.isdigit():
            code_val = code_val.zfill(6)
            
        title_val = str(row.iloc[title_col]).strip() if title_col < len(row) else "-"
        submitter_val = str(row.iloc[submitter_col]).strip() if submitter_col < len(row) else "-"

        item = {
            "time": time_val,
            "company": com_val,
            "code": code_val,
            "title": title_val,
            "submitter": submitter_val
        }

        # 분류를 위한 정규화
        title_clean = title_val.replace(" ", "")

        # 1. 경고/위험/거래 (거래정지, 투자경고, 투자위험 포함시 최우선 권장 배정)
        if any(kw in title_clean for kw in ["거래정지", "투자경고", "투자위험", "투자주의경고", "매매거래"]):
            categories["warning_risk_trading"]["items"].append(item)
            data_lines.append(f"- [경고/위험/거래] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 2. 단기과열
        elif "단기과열" in title_clean:
            categories["overheating"]["items"].append(item)
            data_lines.append(f"- [단기과열] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 3. 투자주의 (주의, 환기종목 포함)
        elif any(kw in title_clean for kw in ["투자주의", "환기종목"]):
            categories["caution"]["items"].append(item)
            data_lines.append(f"- [투자주의] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 4. 공매도 (공매도, 공매도과열 포함)
        elif any(kw in title_clean for kw in ["공매도", "공매도과열"]):
            categories["short_selling"]["items"].append(item)
            data_lines.append(f"- [공매도] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 5. 기타
        else:
            categories["others"]["items"].append(item)
            data_lines.append(f"- [기타] [{time_val}] {com_val}({code_val}) | {title_val}")

    excel_context = "\n".join(data_lines)
    keywords_summary = ", ".join(search_keywords) if search_keywords else "전체 필터링"

    final_prompt = agent_prompt_template.replace("{search_keywords}", keywords_summary)
    final_prompt = final_prompt.replace("{excel_context}", excel_context)
    
    print("\n--- [키워드 매칭 분석 및 요약 생성 중] ---")
    
    ai_brief = ""
    if no_ai:
        print("⚡ [Bypass AI] AI 분석을 생략하고 Python 정량 요약만 활용합니다.")
        ai_brief = ""
    else:
        try:
            try:
                llm = OllamaLLM(model="gemma4")
            except ImportError:
                llm = Ollama(model="gemma4")
                
            print(f"🤖 데이터 매칭 완료! [{keywords_summary}] 관련 종합 AI 평론을 작성하고 있습니다...\n")
            ai_brief = llm.invoke(final_prompt)
        except Exception as e:
            print(f"⚠️ Ollama 연동 실패 혹은 모델 부재로 요약 브리핑을 대체합니다: {e}")
            ai_brief = "당일 공매도 과열종목 지정 및 규제 관련 공매도/경고성 리스크 내역이 수집되었습니다. 투자 지표 검토 시 하단의 세부 공시 내역 표를 면밀히 참조하시기 바랍니다."

    # 마크다운 표준 리포트 작성
    ai_brief_indented = ai_brief.replace('\n', '\n>')
    md_content = f"# 📊 주요 기업 공시 현황 리포트 (조회 키워드: {keywords_summary})\n\n"
    md_content += f"## ✍️ AI 종합 시장 브리핑\n>{ai_brief_indented}\n\n"
    
    for cat_key, cat_val in categories.items():
        md_content += f"### {cat_val['icon']} {cat_val['title']} ({len(cat_val['items'])}건)\n"
        if not cat_val["items"]:
            md_content += "- 등록된 특이사항 공시가 없습니다.\n\n"
        else:
            md_content += "| 시간 | 회사명 (종목코드) | 📢 주요 공시 내용 | 제출인 |\n"
            md_content += "| :---: | :--- | :--- | :--- |\n"
            for item in cat_val["items"]:
                md_content += f"| {item['time']} | **{item['company']}** ({item['code']}) | {item['title']} | {item['submitter']} |\n"
            md_content += "\n"

    # HTML/CSS 대시보드 리포트 생성 - Python 정량 분석 테이블과 AI 한줄 평론의 하이브리드 블록 구성
    stats_html = f"""
    <div class="market-stats" style="margin-bottom: 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 14px;">
        <p style="margin: 0 0 10px 0; font-size: 14px; font-weight: 700; color: #f1f5f9;">📊 시장 리스크 속보 (정량 분석)</p>
        <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px;">
            <span style="background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.3); color: #f59e0b; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;">⚠️ 투자주의: {len(categories['caution']['items'])}건</span>
            <span style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;">🔥 단기과열: {len(categories['overheating']['items'])}건</span>
            <span style="background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); color: #a78bfa; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;">🚨 경고·위험: {len(categories['warning_risk_trading']['items'])}건</span>
            <span style="background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: #60a5fa; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700;">📉 공매도과열: {len(categories['short_selling']['items'])}건</span>
        </div>
    """
    
    critical_companies = []
    for item in categories['warning_risk_trading']['items']:
        critical_companies.append(f"<strong style='color: #ef4444;'>{item['company']}</strong>(신규/예고)")
    for item in categories['overheating']['items']:
        critical_companies.append(f"<strong style='color: #f59e0b;'>{item['company']}</strong>(단기과열)")
        
    critical_companies = list(dict.fromkeys(critical_companies))
    
    if critical_companies:
        stats_html += f"""
        <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">
            🔍 <strong>핵심 모니터링 기업:</strong> {', '.join(critical_companies[:6])}{' 외' if len(critical_companies) > 6 else ''}
        </p>
        </div>
        """
    else:
        stats_html += """
        <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5;">
            🔍 <strong>핵심 모니터링 기업:</strong> 당일 특이사항 리스크 기업이 없습니다. (안전)
        </p>
        </div>
        """

    if not ai_brief or ai_brief.strip() == "":
        ai_commentary_html = """
        <div class="ai-commentary-box" style="border-left-color: #64748b; margin-top: 10px;">
            <p>
                <span style="background: #64748b; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-right: 8px; vertical-align: middle;">INFO</span>
                당일 수집된 시장 조치 및 경보 내역이 카테고리별로 정비되었습니다. 자세한 공시 사항은 하단의 각 탭 뷰를 확인하세요.
            </p>
        </div>
        """
    else:
        import re
        temp_brief = ai_brief.strip()
        
        # 불필요한 마크다운 기획 문자 제거 (*, **, `, - , * )
        temp_brief = re.sub(r'\*\*|\*|`', '', temp_brief)
        temp_brief = re.sub(r'^\s*[-*]\s+', '', temp_brief, flags=re.MULTILINE)
        
        # Ollama 머리말 서두 문구 제거 (예: "요약:", "AI 분석:")
        temp_brief = re.sub(r'^(요약|분석|AI 요약|AI 분석|시장 리스크 요약|요약하자면)\s*:\s*', '', temp_brief, flags=re.IGNORECASE)
        
        last_dot_idx = max(temp_brief.rfind('.'), temp_brief.rfind('?'), temp_brief.rfind('!'))
        if last_dot_idx != -1 and last_dot_idx < len(temp_brief) - 1:
            temp_brief = temp_brief[:last_dot_idx + 1]
            
        temp_brief = temp_brief.strip()
        
        ai_commentary_html = f"""
        <div class="ai-commentary-box">
            <p>
                <span style="background: #2563eb; color: #ffffff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-right: 8px; vertical-align: middle; letter-spacing: 0.5px;">AI BRIEF</span>
                {temp_brief}
            </p>
        </div>
        """

    html_brief = stats_html + ai_commentary_html
    today_date = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    
    # html2canvas 라이브러리의 오프라인 로컬 인라인 시도
    html2canvas_js = get_html2canvas_script()
    if html2canvas_js:
        html2canvas_script_tag = f"<script>{html2canvas_js}</script>"
    else:
        html2canvas_script_tag = '<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>'
        
    # HTML 헤더 렌더링
    html_content = HTML_HEADER.format(
        html2canvas_script_tag=html2canvas_script_tag,
        today_date=today_date,
        html_brief=html_brief
    )
    
    # 카드리스트 루프 렌더링
    for cat_key, cat_val in categories.items():
        badge_class = cat_val["color"]
        length = len(cat_val["items"])
        html_content += HTML_CARD_START.format(
            cat_key=cat_key,
            badge_class=badge_class,
            icon=cat_val['icon'],
            title=cat_val['title'],
            length=length
        )
        
        if not cat_val["items"]:
            html_content += HTML_EMPTY_STATE
        else:
            html_content += HTML_TABLE_START
            for item in cat_val["items"]:
                html_content += HTML_TABLE_ROW.format(
                    time=item['time'],
                    company=item['company'],
                    code=item['code'],
                    title=item['title'],
                    submitter=item['submitter']
                )
            html_content += HTML_TABLE_END
            
        html_content += HTML_CARD_END

    # HTML 푸터 렌더링
    html_content += HTML_FOOTER

    return {
        "html": html_content,
        "md": md_content,
        "ai_brief": ai_brief
    }


def select_keywords_interactive():
    """
    사용자가 원하는 공시 필터 키워드를 체크 리스트(메뉴) 형태로 편리하게 선택할 수 있게 합니다.
    """
    presets = {
        "1": ("투자경고 / 투자위험 / 투자주의", ["투자경고", "투자위험", "투자주의"]),
        "2": ("공매도 과열종목 지정", ["공매도", "공매도 과열"]),
        "3": ("단기과열지정 / 불성실공시", ["단기과열", "불성실공시"]),
        "4": ("상장폐지 / 관리종목 지정", ["상장폐지", "관리종목"]),
        "5": ("투자주의환기종목", ["환기종목", "투자주의환기"]),
        "6": ("직접 입력 (검색할 키워드를 타이핑)", None)
    }
    
    print("\n==================================================")
    print("📢 리포트를 만들고자 하는 공시 유형을 선택하세요 (여러 번호 입력 가능: 예: 1, 2)")
    print("==================================================")
    for key, (label, _) in presets.items():
        print(f"[{key}] {label}")
    print("==================================================")
    
    user_choice = input("💡 선택할 번호(쉼표 구분)를 입력하세요: ").strip()
    selected_keywords = []
    
    choices = [c.strip() for c in user_choice.split(",") if c.strip()]
    
    for c in choices:
        if c in presets:
            label, kws = presets[c]
            if kws:
                selected_keywords.extend(kws)
            elif c == "6":
                custom = input("✍️ 직접 검색할 키워드를 입력하세요 (여러 개는 쉼표 구분): ").strip()
                custom_kws = [ck.strip() for ck in custom.split(",") if ck.strip()]
                selected_keywords.extend(custom_kws)
                
    # 중복 제거
    selected_keywords = list(set([k for k in selected_keywords if k]))
    return selected_keywords


def save_report(report_data, keywords):
    """
    생성된 리포트를 'reports/' 폴더 아래 HTML 및 Markdown 두 가지 확장자로 모두 보조 저장합니다.
    """
    if not report_data:
        return
    
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    short_kws = f"_{'_'.join(keywords[:2])}" if keywords else ""
    
    # 1. 공시 미존재 시 (단순 문자열 수신 시 처리용 폴백)
    if isinstance(report_data, str):
        filename_md = f"reports/report_{today_str}{short_kws}.md"
        with open(filename_md, "w", encoding="utf-8") as f:
            f.write(report_data)
        print(f"💾 생성된 공시 리포트가 임시로 마크다운 저장되었습니다. -> [ {filename_md} ]")
        return filename_md

    # 2. 정상 분석 데이터 수신 시 HTML 및 MD 동시 적재
    if "msg" in report_data and report_data.get("empty"):
        msg = report_data["msg"]
        filename_md = f"reports/report_{today_str}{short_kws}.md"
        with open(filename_md, "w", encoding="utf-8") as f:
            f.write(msg)
        print(f"💾 조건에 검색된 데이터 없음 (안내 파일 저장됨) -> [ {filename_md} ]")
        return filename_md

    # HTML 저장
    filename_html = f"reports/report_{today_str}{short_kws}.html"
    with open(filename_html, "w", encoding="utf-8") as f:
        f.write(report_data["html"])
        
    # MD 저장
    filename_md = f"reports/report_{today_str}{short_kws}.md"
    with open(filename_md, "w", encoding="utf-8") as f:
        f.write(report_data["md"])
        
    print(f"💾 생성된 공시 대시보드 리포트가 성공적으로 저장되었습니다:")
    print(f"   ▶ 브라우저용 HTML : [ {filename_html} ]")
    print(f"   ▶ 일반텍스트 뷰 MD : [ {filename_md} ]")
    return filename_html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="기업 공시 필터링 및 리포트 자동 생성 툴")
    parser.add_argument("--auto", action="store_true", help="스케줄러 등을 통한 자동 배치 처리 모드")
    parser.add_argument("--file", type=str, help="분석에 사용할 특정 엑셀 파일 경로")
    parser.add_argument("--keywords", type=str, help="자동 모드 시 필터링할 키워드 목록 (쉼표 구분)")
    parser.add_argument("--bypass-time-filter", action="store_true", help="시간 필터(20:00 이후 조건)를 무시하고 전체 시간 공시 파싱")
    parser.add_argument("--no-ai", action="store_true", help="Ollama LLM 연동을 생략하고 Python 기반의 통계 정보로 요약 브리핑 대체")
    
    args = parser.parse_args()
    
    if args.auto:
        # 자동 스케줄러 실행 모드
        if not args.file:
            print("❌ 자동 모드 실행 시 --file 인수가 필수적입니다.")
            sys.exit(1)
            
        file_path = args.file
        keywords_to_search = []
        if args.keywords:
            keywords_to_search = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        
        print(f"🤖 [자동 배치 모드] 대상 파일: {os.path.basename(file_path)}")
        if keywords_to_search:
            print(f"🤖 [자동 배치 모드] 검색 키워드: {keywords_to_search}")
        else:
            print(f"🤖 [자동 배치 모드] 전체 공시 모드 (20:00 이후 모든 공시)")
        
        report_content = generate_report_from_agent_md(file_path, keywords_to_search, bypass_time_filter=args.bypass_time_filter, no_ai=args.no_ai)
        if report_content:
            save_report(report_content, keywords_to_search)
            
    else:
        # 대화형 일반 모드 -> 최신 엑셀 파일의 전체 공시 리포트 생성
        excel_file = get_latest_excel_in_current_dir()
        if excel_file:
            print(f"✨ [일반 모드] 대상 파일: {os.path.basename(excel_file)}")
            print(f"✨ 키워드 선택을 생략하고 20:00 이후 전체 공시 데이터를 리포팅합니다.")
            report_content = generate_report_from_agent_md(excel_file, [], bypass_time_filter=args.bypass_time_filter, no_ai=args.no_ai)
            if report_content:
                save_report(report_content, [])