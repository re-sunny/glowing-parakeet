import os
import sys
import glob
import re
import urllib.request
import pandas as pd

def get_latest_excel_in_current_dir():
    """
    현재 디렉토리에서 가장 최근에 수정된 엑셀 파일(.xlsx, .xls)을 탐색하여 반환합니다.
    """
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
        # 주요 컬럼 중 최소 2개 이상이 매칭되는 행 탐색
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


def get_html2canvas_script():
    """
    html2canvas.min.js 파일을 로컬 캐시하거나 CDN에서 받아와 HTML에 직접 인라인합니다.
    """
    script_filename = "html2canvas.min.js"
    
    # 1. 먼저 로컬 캐시 파일 확인
    if os.path.exists(script_filename):
        try:
            with open(script_filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            print(f"⚠️ 로컬 html2canvas.min.js 파일 로드 실패: {e}")
            
    # 2. 로컬 캐시가 없으면 CDN 다운로드 시도
    cdn_url = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"
    print(f"🌐 오프라인 단독 구동을 위해 html2canvas.min.js 라이브러리를 CDN에서 받아옵니다...")
    try:
        req = urllib.request.Request(
            cdn_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            content_bytes = response.read()
            # 다운로드 성공 시 로컬 캐파일로 저장하여 다음 실행 시 오프라인 구동 가능토록 함
            try:
                with open(script_filename, "wb") as f:
                    f.write(content_bytes)
                print(f"💾 html2canvas.min.js 라이브러리를 로컬 캐시({script_filename})로 저장했습니다.")
            except Exception as save_err:
                print(f"⚠️ 라이브러리 로컬 캐시 파일 저장 중 실패(사용에는 지장 없음): {save_err}")
                
            return content_bytes.decode("utf-8")
    except Exception as cdn_err:
        print(f"⚠️ html2canvas.min.js 라이브러리 다운로드 실패(CDN 예외): {cdn_err}")
        return None


def extract_hour_from_time_value(time_val):
    """
    시간 컬럼의 데이터(문자열, datetime, Timestamp 등)로부터 시간(hour) 정수를 안전하게 추출합니다.
    """
    if pd.isnull(time_val):
        return None
        
    # datetime, time, Timestamp 속성을 가진 경우
    if hasattr(time_val, 'hour'):
        return time_val.hour
        
    # 문자열 파싱 시도
    time_str = str(time_val).strip()
    
    # "2026-07-02 18:30:00" 등 년월일이 포함된 경우 시간만 떼내기
    if " " in time_str:
        time_str = time_str.split()[-1]
        
    # HH:MM:SS 이거나 HH:MM
    if ":" in time_str:
        try:
            return int(time_str.split(":")[0])
        except ValueError:
            pass
            
    # 정규식으로 "18시" 등 한글 표현 파싱
    match = re.search(r'(\d+)\s*(?:시|:)', time_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
            
    # 첫 2자리 숫자 추출구조
    match_digits = re.match(r'^\s*(\d{1,2})', time_str)
    if match_digits:
        try:
            return int(match_digits.group(1))
        except ValueError:
            pass
            
    return None

