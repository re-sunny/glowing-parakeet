import os
import sys
import glob
import argparse
import datetime
import pandas as pd
from langchain_ollama import OllamaLLM
from langchain_community.llms import Ollama

def get_latest_excel_in_current_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    excel_files = []
    for ext in ["*.xlsx", "*.xls"]:
        excel_files.extend(glob.glob(os.path.join(current_dir, ext)))
    if not excel_files:
        print(f"❌ 현재 위치에 엑셀 파일(.xlsx, .xls)이 존재하지 않습니다.")
        return None
    latest_file = max(excel_files, key=os.path.getmtime)
    print(f"📂 인식된 엑셀 파일: {os.path.basename(latest_file)}")
    return latest_file


def try_read_excel(file_path):
    """
    엑셀 상단의 공백이나 깨진 헤더를 우회하여 
    실제 표 데이터가 시작하는 지점을 자동으로 찾아 로드합니다.
    """
    df = None
    try:
        if file_path.endswith('.xls'):
            df = pd.read_excel(file_path, engine='xlrd')
        else:
            df = pd.read_excel(file_path)
    except Exception:
        pass

    # 만약 위에서 못 읽었거나 HTML 형식이 의심될 때
    if df is None or df.empty:
        try:
            # HTML 형식으로 저장된 .xls 파일 처리 (한글 깨짐 방지를 위해 encoding='cp949' 추가)
            dfs = pd.read_html(file_path, encoding='cp949')
            if dfs:
                df = dfs[0]
        except Exception:
            try:
                df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
            except Exception:
                try:
                    df = pd.read_csv(file_path, sep='\t', encoding='cp949')
                except Exception as e:
                    raise ValueError(f"파일을 읽을 수 없습니다: {e}")

    # 1. 원본 컬럼 중 '회사명' 이나 '공시제목' 이 들어있는 경우 바로 헤더로 사용
    cols_str = "".join([str(c) for c in df.columns])
    if any(k in cols_str for k in ["회사명", "공시제목", "종목코드"]):
        df.columns = [str(c).replace('\n', '').replace(' ', '').strip() for c in df.columns]
        return df

    # 2. 첫 번째 행부터 돌며 헤더 매칭 탐색 (헤더가 데이터 행 중간에 박힌 경우 대비)
    actual_header_idx = None
    for idx, row in df.iterrows():
        row_str = "".join(row.dropna().astype(str))
        # 단순 '종목'만 매칭하면 위험하므로, 주요 컬럼 중 최소 2개 이상이 매칭되는 행 탐색
        matches = sum(1 for k in ["회사명", "공시제목", "종목코드", "접수일자", "시간"] if k in row_str)
        if matches >= 2:
            actual_header_idx = idx
            break
            
    # 발견한 헤더 위치를 기준으로 데이터프레임 재정의
    if actual_header_idx is not None:
        raw_cols = df.iloc[actual_header_idx].tolist()
        df.columns = [str(c).replace('\n', '').replace(' ', '').strip() for c in raw_cols]
        df = df.iloc[actual_header_idx + 1:].reset_index(drop=True)
    
    return df

def md_to_html(md_text):
    """
    간단한 마크다운을 HTML 태그로 변환합니다. (굵은 글씨, 목록형 목록 지원)
    """
    if not md_text:
        return ""
    import re
    html = str(md_text).strip()
    # 굵은 글씨 **text** -> <strong>text</strong>
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    lines = html.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                new_lines.append('<ul style="margin: 8px 0; padding-left: 20px; color: #d1d5db; line-height: 1.6;">')
                in_list = True
            new_lines.append(f'<li style="margin-bottom: 6px;">{stripped[2:]}</li>')
        elif stripped.startswith('> '):
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(f'<blockquote style="border-left: 4px solid #8b5cf6; padding-left: 12px; margin: 12px 0; color: #9ca3af; font-style: italic;">{stripped[2:]}</blockquote>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            if stripped:
                new_lines.append(f'<p style="margin: 8px 0; line-height: 1.6; color: #e5e7eb;">{stripped}</p>')
            else:
                new_lines.append('<div style="height: 8px;"></div>')
    if in_list:
        new_lines.append('</ul>')
    return "\n".join(new_lines)


def generate_report_from_agent_md(file_path, search_keywords, agent_md_path="agents_auto.md", bypass_time_filter=False):
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
            time_val = str(row.iloc[time_col]).strip()
            if ":" in time_val:
                try:
                    time_hm = time_val[:5] 
                    if time_hm < "20:00":  
                        continue
                except Exception:
                    pass

        # 2. 키워드 조건 검사 (search_keywords가 제공되지 않거나 비어있으면 모든 행 통과)
        if not search_keywords:
            matched_rows.append(row)
        else:
            full_row_text = "".join(row.dropna().astype(str)).replace(" ", "").lower()
            if any(keyword.replace(" ", "").lower() in full_row_text for keyword in search_keywords):
                matched_rows.append(row)
            
    filtered_df = pd.DataFrame(matched_rows)
    
    if filtered_df.empty:
        cond_str = f"키워드 {search_keywords}" if search_keywords else "20:00 이후 데이터"
        msg = f"\n[안내] 조건에 부합하는 {cond_str} 공시 데이터가 존재하지 않습니다."
        print(msg)
        return {"msg": msg, "empty": True}

    # 종류별 분류 데이터 구성 (사용자 요청 커스텀 4대 분야)
    categories = {
        "caution_overheating": {"title": "투자주의 & 단기과열", "icon": "⚠️", "color": "warning", "items": []},
        "warning_risk_trading": {"title": "투자경고 & 투자위험 & 매매거래", "icon": "🚨", "color": "trading", "items": []},
        "short_selling": {"title": "공매도", "icon": "📉", "color": "listing", "items": []},
        "others": {"title": "기타", "icon": "ℹ️", "color": "others", "items": []}
    }

    # LLM 컨텍스트 전송용 간략 데이터 빌드
    data_lines = []
    
    for _, row in filtered_df.iterrows():
        time_val = str(row.iloc[time_col]).strip() if time_col < len(row) else ""
        com_val = str(row.iloc[com_col]).strip() if com_col < len(row) else ""
        code_val = str(row.iloc[code_col]).strip() if code_col < len(row) else ""
        title_val = str(row.iloc[title_col]).strip() if title_col < len(row) else ""
        sub_val = str(row.iloc[submitter_col]).strip() if submitter_col < len(row) else ""
        
        item = {
            "time": time_val,
            "company": com_val,
            "code": code_val,
            "title": title_val,
            "submitter": sub_val
        }
        
        title_clean = title_val.replace(" ", "").lower()
        
        # 분류 작업
        # 1. 투자경고 & 투자위험 & 매매거래 (경고, 위험, 매매거래, 거래정지, 정지해제, 매매정지 포함)
        # 중요: "[투자주의]투자경고종목 지정예고"처럼 투자경고 등 상위 리스크 키워드가 포함되어 있다면 투경 쪽에 먼저 분류합니다.
        if any(kw in title_clean for kw in ["투자경고", "투자위험", "매매거래", "거래정지", "정지해제", "매매정지"]):
            categories["warning_risk_trading"]["items"].append(item)
            data_lines.append(f"- [경고/위험/거래] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 2. 투자주의 & 단기과열 (주의, 단기과열, 환기종목 포함)
        elif any(kw in title_clean for kw in ["투자주의", "단기과열", "환기종목"]):
            categories["caution_overheating"]["items"].append(item)
            data_lines.append(f"- [주의/단기과열] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 3. 공매도 (공매도, 공매도과열 포함)
        elif any(kw in title_clean for kw in ["공매도", "공매도과열"]):
            categories["short_selling"]["items"].append(item)
            data_lines.append(f"- [공매도] [{time_val}] {com_val}({code_val}) | {title_val}")
        # 4. 기타
        else:
            categories["others"]["items"].append(item)
            data_lines.append(f"- [기타] [{time_val}] {com_val}({code_val}) | {title_val}")
            
    excel_context = "\n".join(data_lines)
    keywords_summary = ", ".join(search_keywords)

    final_prompt = agent_prompt_template.replace("{search_keywords}", keywords_summary)
    final_prompt = final_prompt.replace("{excel_context}", excel_context)
    
    print("\n--- [키워드 매칭 분석 및 요약 생성 중] ---")
    
    ai_brief = ""
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

    # HTML/CSS 대시보드 리포트 생성
    html_brief = md_to_html(ai_brief)
    today_date = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KIND 기업 공시 리스크 감시 보드</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #161d30;
            --border-color: #243049;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            
            --warning-color: #ffc107;
            --warning-bg: rgba(255, 193, 7, 0.1);
            --warning-border: rgba(255, 193, 7, 0.3);
            
            --trading-color: #f43f5e;
            --trading-bg: rgba(244, 63, 94, 0.1);
            --trading-border: rgba(244, 63, 94, 0.3);
            
            --listing-color: #d946ef;
            --listing-bg: rgba(217, 70, 239, 0.1);
            --listing-border: rgba(217, 70, 239, 0.3);
            
            --others-color: #3b82f6;
            --others-bg: rgba(59, 130, 246, 0.1);
            --others-border: rgba(59, 130, 246, 0.3);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        
        .container {{
            width: 100%;
            max-width: 1100px;
            display: flex;
            flex-direction: column;
            gap: 28px;
        }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
        }}
        
        .logo-section h1 {{
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(to right, #3b82f6, #93c5fd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        
        .logo-section p {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        
        .date-badge {{
            background-color: #1e293b;
            border: 1px solid var(--border-color);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            color: #60a5fa;
        }}
        
        /* AI 브리핑 배너 */
        .ai-banner {{
            background: linear-gradient(135deg, #1e1b4b, #2e1065);
            border-left: 4px solid #8b5cf6;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 4px 10px -5px rgba(139, 92, 246, 0.2);
        }}
        
        .ai-banner h2 {{
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #c084fc;
            margin-bottom: 12px;
            letter-spacing: -0.2px;
        }}
        
        .ai-content {{
            font-size: 14px;
        }}
        
        /* 메인 리드 대시보드 리스트 */
        .dashboard-grid {{
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            transition: transform 0.28s ease, border-color 0.28s ease;
        }}
        
        .card:hover {{
            border-color: #374151;
            transform: translateY(-2px);
        }}
        
        .card-header {{
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .card-header.warning {{ border-top: 3px solid var(--warning-color); }}
        .card-header.trading {{ border-top: 3px solid var(--trading-color); }}
        .card-header.listing {{ border-top: 3px solid var(--listing-color); }}
        .card-header.others {{ border-top: 3px solid var(--others-color); }}
        
        .card-title {{
            font-size: 15px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .badge {{
            font-size: 11px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 10px;
        }}
        
        .badge.warning {{ background-color: var(--warning-bg); color: var(--warning-color); border: 1px solid var(--warning-border); }}
        .badge.trading {{ background-color: var(--trading-bg); color: var(--trading-color); border: 1px solid var(--trading-border); }}
        .badge.listing {{ background-color: var(--listing-bg); color: var(--listing-color); border: 1px solid var(--listing-border); }}
        .badge.others {{ background-color: var(--others-bg); color: var(--others-color); border: 1px solid var(--others-border); }}
        
        /* 리스트 형식 테이블 */
        .table-container {{
            width: 100%;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13.5px;
        }}
        
        th {{
            background-color: #111827;
            color: var(--text-secondary);
            font-weight: 600;
            padding: 12px 20px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        td {{
            padding: 14px 20px;
            border-bottom: 1px solid var(--border-color);
            color: #d1d5db;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tr:hover td {{
            background-color: rgba(255, 255, 255, 0.02);
            color: #ffffff;
        }}
        
        .time-cell {{
            font-family: 'Courier New', Courier, monospace;
            color: #a78bfa;
            font-weight: 600;
        }}
        
        .company-name {{
            font-weight: 600;
            color: #f3f4f6;
        }}
        
        .stock-code {{
            font-size: 11.5px;
            color: #6b7280;
            margin-left: 5px;
        }}
        
        .submitter-cell {{
            font-size: 12.5px;
            color: var(--text-secondary);
        }}
        
        .empty-state {{
            padding: 28px;
            text-align: center;
            color: #10b981;
            font-size: 13.5px;
            font-weight: 600;
            background-color: rgba(16, 185, 129, 0.02);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 6px;
        }}
        
        footer {{
            text-align: center;
            font-size: 12px;
            color: #4b5563;
            margin-top: 20px;
            border-top: 1px solid var(--border-color);
            padding-top: 20px;
        }}
        
        /* 탭 네비게이션 스타일 추가 */
        .tabs-nav {{
            display: flex;
            gap: 10px;
            margin-bottom: 24px;
            overflow-x: auto;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .tab-btn {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
        }}
        
        .tab-btn:hover {{
            border-color: #3b82f6;
            color: var(--text-primary);
        }}
        
        .tab-btn.active {{
            background-color: #2563eb;
            border-color: #3b82f6;
            color: #ffffff;
            box-shadow: 0 0 12px rgba(37, 99, 235, 0.3);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo-section">
                <h1>📊 KIND 기업 공시 리스크 감시 보드</h1>
                <p>한국거래소 시장 경보 조치사항 및 공매도 과열 규제 종합 대시보드</p>
            </div>
            <div class="date-badge">{today_date} 수집분</div>
        </header>

        <!-- 탭 네비게이션 메뉴 영역 -->
        <div class="tabs-nav">
            <button class="tab-btn active" onclick="switchTab(event, 'all')">전체보기</button>
            <button class="tab-btn" onclick="switchTab(event, 'caution_overheating')">⚠️ 투자주의 & 단기과열</button>
            <button class="tab-btn" onclick="switchTab(event, 'warning_risk_trading')">🚨 투자경고 & 투자위험 & 매매거래</button>
            <button class="tab-btn" onclick="switchTab(event, 'short_selling')">📉 공매도</button>
            <button class="tab-btn" onclick="switchTab(event, 'others')">📝 기타</button>
        </div>
        
        <!-- AI 종합 시장 평론 브리핑 -->
        <div class="ai-banner">
            <h2>✍️ 봇 금융 분석관 코멘트 (AI Summary)</h2>
            <div class="ai-content">
                {html_brief}
            </div>
        </div>
        
        <!-- 종류별 공시 정보 카드리스트 -->
        <main class="dashboard-grid">
"""
    
    for cat_key, cat_val in categories.items():
        badge_class = cat_val["color"]
        length = len(cat_val["items"])
        html_content += f"""
            <section class="card" id="card-{cat_key}">
                <div class="card-header {badge_class}">
                    <h3 class="card-title">{cat_val['icon']} {cat_val['title']}</h3>
                    <span class="badge {badge_class}">{length}건 발생</span>
                </div>
                <div class="table-container">
        """
        
        if not cat_val["items"]:
            html_content += f"""
                    <div class="empty-state">
                        ✓ 당일 해당 유형의 특이사항 리스크 공시 내역이 없습니다. (안전)
                    </div>
            """
        else:
            html_content += """
                    <table>
                        <thead>
                            <tr>
                                <th width="10%">시간</th>
                                <th width="25%">회사명</th>
                                <th width="50%">📢 주요 공시 내용</th>
                                <th width="15%">제출인</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            for item in cat_val["items"]:
                html_content += f"""
                            <tr>
                                <td class="time-cell">{item['time']}</td>
                                <td>
                                    <span class="company-name">{item['company']}</span>
                                    <span class="stock-code">({item['code']})</span>
                                </td>
                                <td>{item['title']}</td>
                                <td class="submitter-cell">{item['submitter']}</td>
                            </tr>
                """
            html_content += """
                        </tbody>
                    </table>
            """
            
        html_content += """
                </div>
            </section>
        """
        
    html_content += """
        </main>
        
        <footer>
            본 보드는 공시 데이터를 파싱하여 가상 리스크 키워드 필터링 과정을 거쳐 자동 생성된 요약 참고용 리포트입니다.
        </footer>
    </div>
    
    <!-- 탭 전환 제어 스크립트 -->
    <script>
        function switchTab(e, tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            if (e && e.currentTarget) {
                e.currentTarget.classList.add('active');
            }
            const cards = document.querySelectorAll('.card');
            if (tabId === 'all') {
                cards.forEach(card => card.style.display = 'block');
            } else {
                cards.forEach(card => {
                    if (card.id === 'card-' + tabId) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
            }
        }
    </script>
</body>
</html>
"""

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
        
        report_content = generate_report_from_agent_md(file_path, keywords_to_search, bypass_time_filter=args.bypass_time_filter)
        if report_content:
            save_report(report_content, keywords_to_search)
            
    else:
        # 대화형 일반 모드 -> 대화 형식으로 키워드를 묻지 않고, 바로 최신 엑셀 파일의 전체 공시 리포트 생성
        excel_file = get_latest_excel_in_current_dir()
        if excel_file:
            print(f"✨ [일반 모드] 대상 파일: {os.path.basename(excel_file)}")
            print(f"✨ 키워드 선택을 생략하고 20:00 이후 전체 공시 데이터를 리포팅합니다.")
            report_content = generate_report_from_agent_md(excel_file, [], bypass_time_filter=args.bypass_time_filter)
            if report_content:
                save_report(report_content, [])