import os
import glob
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
            # 일반적인 xls는 xlrd로 읽지만, 에러 대비를 위해 예외 처리로 넘김
            df = pd.read_excel(file_path, engine='xlrd', header=None)
        else:
            df = pd.read_excel(file_path, header=None)
    except Exception:
        pass

    # 만약 위에서 못 읽었거나 HTML 형식이 의심될 때
    if df is None or df.empty:
        try:
            # HTML 형식으로 저장된 .xls 파일 처리 (한글 깨짐 방지를 위해 encoding='cp949' 추가)
            dfs = pd.read_html(file_path, encoding='cp949')
            if dfs:
                df = dfs[0]
                df.columns = range(df.shape[1])
        except Exception:
            try:
                df = pd.read_csv(file_path, sep='\t', encoding='utf-8', header=None)
            except Exception:
                try:
                    df = pd.read_csv(file_path, sep='\t', encoding='cp949', header=None)
                except Exception as e:
                    raise ValueError(f"파일을 읽을 수 없습니다: {e}")

    # 🔥 [핵심 로직] '회사명'이나 '공시제목'이 들어있는 행을 진짜 헤더(컬럼명)로 지정
    actual_header_idx = 0
    for idx, row in df.iterrows():
        row_str = "".join(row.dropna().astype(str))
        if "회사명" in row_str or "공시제목" in row_str or "종목" in row_str:
            actual_header_idx = idx
            break
            
    # 발견한 헤더 위치를 기준으로 데이터프레임 재정의
    df.columns = df.iloc[actual_header_idx].astype(str).str.strip()
    df = df.iloc[actual_header_idx + 1:].reset_index(drop=True)
    return df

def generate_report_from_agent_md(file_path, search_keywords, agent_md_path="agents.md"):
    if not os.path.exists(agent_md_path):
        print(f"❌ '{agent_md_path}' 파일을 찾을 수 없습니다.")
        return
        
    with open(agent_md_path, "r", encoding="utf-8") as f:
        agent_prompt_template = f.read()

    try:
        # 헤더 없이 데이터만 온전하게 읽어옵니다.
        df = pd.read_excel(file_path, header=None)
    except Exception:
        try:
            dfs = pd.read_html(file_path, encoding='cp949')
            df = dfs[0] if dfs else None
        except Exception:
            try:
                df = pd.read_csv(file_path, sep='\t', encoding='cp949', header=None)
            except Exception as e:
                print(f"❌ 파일을 읽는 중 오류가 발생했습니다: {e}")
                return

    if df is None or df.empty:
        print("❌ 엑셀 파일에 데이터가 존재하지 않습니다.")
        return

    # 810, 20:01, 도우인시스, 484120, 공매도 과열종목... 데이터 구조 분석 및 자동 매핑
    # 데이터의 형태(숫자, 시간, 문자열 길이 등)를 기반으로 컬럼을 추정합니다.
    time_col, com_col, code_col, title_col = None, None, None, None
    
    # 첫 번째 행을 샘플로 조사하여 각 열의 특징 파악
    sample_row = df.iloc[0].astype(str).tolist()
    for idx, val in enumerate(sample_row):
        val = val.strip()
        if ":" in val: # 20:01 같은 시간 형태
            time_col = idx
        elif val.isdigit() and len(val) >= 4: # 484120 같은 종목코드 형태
            code_col = idx
        elif len(val) > 15: # 글자 수가 긴 것은 공시제목일 확률이 높음
            title_col = idx
    
    # 위 조건으로 못 찾은 경우, 남은 열 중에서 회사명 지정 (보통 2~3번째 열)
    # 현재 출력 기준 ['810'(0), '20:01'(1), '도우인시스'(2), '484120'(3), '공매도...'(4)]
    if time_col is None: time_col = 1
    if com_col is None: com_col = 2
    if code_col is None: code_col = 3
    if title_col is None: title_col = 4

    matched_rows = []
    for idx, row in df.iterrows():
        # 1. 시간 조건 검사 (20:00시부터 포함)
        if time_col is not None and time_col < len(row):
            time_val = str(row.iloc[time_col]).strip()
            
            # 'HH:MM' 형태로 들어오는 경우 비교
            if ":" in time_val:
                try:
                    # 시간 문자열을 '시:분' 구조에서 공백을 제거하고 정규화
                    # '20:00' 이상의 문자열인지 직접 비교 (예: '20:00' >= '20:00' -> True)
                    # 만약 초 단위까지 있다면(20:00:15) 앞의 5글자(20:00)만 추출하여 비교
                    time_hm = time_val[:5] 
                    
                    if time_hm < "20:00":  # 20:00보다 이른 시간(19:59 등)은 모두 제외
                        continue
                except Exception:
                    pass

        # 2. 키워드 조건 검사
        full_row_text = "".join(row.dropna().astype(str)).replace(" ", "").lower()
        if any(keyword.replace(" ", "").lower() in full_row_text for keyword in search_keywords):
            matched_rows.append(row)
            
            
    filtered_df = pd.DataFrame(matched_rows)
    
    if filtered_df.empty:
        print(f"\n[안내] 입력하신 키워드 {search_keywords}가 포함된 공시 데이터가 존재하지 않습니다.")
        return

    # LLM 컨텍스트 구성
    data_lines = []
    for _, row in filtered_df.iterrows():
        time_val = row.iloc[time_col] if time_col < len(row) else ""
        com_val = row.iloc[com_col] if com_col < len(row) else ""
        code_val = row.iloc[code_col] if code_col < len(row) else ""
        title_val = row.iloc[title_col] if title_col < len(row) else ""
        
        data_lines.append(
            f"- [{time_val}] 회사명: {com_val}({code_val}) | 공시제목: {title_val}"
        )
        
    excel_context = "\n".join(data_lines)
    keywords_summary = ", ".join(search_keywords)

    final_prompt = agent_prompt_template.replace("{search_keywords}", keywords_summary)
    final_prompt = final_prompt.replace("{excel_context}", excel_context)
    print(excel_context)
    # ⚠️ DeprecationWarning 해결을 위해 OllamaLLM 사용 추천 (langchain-ollama 패키지 필요)
    try:
        llm = OllamaLLM(model="gemma4")
    except ImportError:
        llm = Ollama(model="gemma4")
        
    print(f"\n🤖 데이터 매칭 완료! [{keywords_summary}] 관련 표를 생성하고 있습니다...\n")
    report_output = llm.invoke(final_prompt)
    print(report_output)


if __name__ == "__main__":
    print("📢 기업 공시 필터링 프로그램입니다.")
    excel_file = get_latest_excel_in_current_dir()
    
    if excel_file:
        user_input = input("💡 추출할 키워드를 입력하세요 (여러 개일 경우 쉼표로 구분): ")
        keywords_to_search = [kw.strip() for kw in user_input.split(",") if kw.strip()]
        
        if not keywords_to_search:
            print("❌ 입력된 키워드가 없습니다.")
        else:
            generate_report_from_agent_md(excel_file, keywords_to_search)