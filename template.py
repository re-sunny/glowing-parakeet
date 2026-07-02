# -*- coding: utf-8 -*-

HTML_HEADER = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KIND 기업 공시 리스크 감시 보드</title>
    <style>
        :root {{
            --bg-color: #0f172a;        /* Deep slate background */
            --card-bg: #1e293b;         /* Slate card background */
            --border-color: #334155;     /* Slate-700 for clear borders */
            --text-primary: #f8fafc;     /* Near pure white for high readability */
            --text-secondary: #cbd5e1;   /* Slate-300 for highly readable labels */
            --text-muted: #94a3b8;       /* Slate-400 for secondary codes */
            --th-bg: #0f172a;
            --th-text: #ffffff;
            --time-color: #a78bfa;       /* Purple timestamp */
            --row-even-bg: rgba(255, 255, 255, 0.015);
            --hover-row-bg: rgba(255, 255, 255, 0.04);
            
            --caution-color: #f59e0b;    /* Amber Yellow */
            --caution-bg: rgba(245, 158, 11, 0.12);
            --caution-border: rgba(245, 158, 11, 0.35);
            
            --overheating-color: #ff7828; /* Warm Orange red */
            --overheating-bg: rgba(255, 120, 40, 0.12);
            --overheating-border: rgba(255, 120, 40, 0.35);
            
            --trading-color: #f43f5e;    /* Bright pinkish-red */
            --trading-bg: rgba(244, 63, 94, 0.12);
            --trading-border: rgba(244, 63, 94, 0.35);
            
            --short-color: #3b82f6;      /* Bright blue */
            --short-bg: rgba(59, 130, 246, 0.12);
            --short-border: rgba(59, 130, 246, 0.35);
            
            --other-color: #64748b;      /* Muted gray */
            --other-bg: rgba(100, 116, 139, 0.12);
            --other-border: rgba(100, 116, 139, 0.35);
        }}
        
        /* Light Mode CSS Variable Overrides */
        body.light-mode {{
            --bg-color: #f8fafc;        /* Slate-50 soft background */
            --card-bg: #ffffff;         /* Pure white cards */
            --border-color: #e2e8f0;     /* Slate-200 light dividers */
            --text-primary: #0f172a;     /* Slate-900 high contrast dark text */
            --text-secondary: #334155;   /* Slate-700 label text */
            --text-muted: #576574;       /* Darker grey codes */
            --th-bg: #e2e8f0;           /* Slate-200 header background */
            --th-text: #0f172a;         /* Slate-900 header text */
            --time-color: #5b21b6;       /* Deep high-visibility purple */
            --row-even-bg: #fcfcfc;
            --hover-row-bg: #f1f5f9;     
            
            --caution-bg: #fffbeb;
            --caution-border: #fde68a;
            
            --overheating-bg: #fff7ed;
            --overheating-border: #ffedd5;
            
            --trading-bg: #fff5f5;
            --trading-border: #fed7d7;
            
            --short-bg: #eff6ff;
            --short-border: #dbeafe;
            
            --other-bg: #f8fafc;
            --other-border: #e2e8f0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            padding: 24px 16px;
            min-height: 100vh;
            line-height: 1.5;
            transition: background-color 0.3s, color 0.3s;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 16px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        
        .logo-section h1 {{
            font-size: 24px;
            font-weight: 800;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}
        
        .logo-section p {{
            font-size: 14px;
            color: var(--text-secondary);
        }}
        
        .date-badge {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        
        /* 탭 네비게이션 컨테이너 */
        .tabs-container {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 10px 14px;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}
        
        .tabs-nav {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;  /* 탭 버튼들 세로 늘어남 방지 */
        }}
        
        .tab-btn {{
            background-color: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 9px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13.5px;
            font-weight: 700;
            transition: all 0.2s ease;
        }}
        
        .tab-btn:hover {{
            background-color: var(--row-even-bg);
            color: var(--text-primary);
        }}
        
        .tab-btn.active {{
            background-color: var(--text-primary);
            color: var(--bg-color);
        }}
        
        /* 테마 토글 버튼 스타일 */
        .theme-toggle-btn {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 9px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13.5px;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            min-width: 140px;
            justify-content: center;
        }}
        
        .theme-toggle-btn:hover {{
            background-color: var(--row-even-bg);
            border-color: var(--text-primary);
        }}
        
        /* 이미지 캡쳐 버튼 스타일 */
        .copy-btn {{
            background-color: #2563eb;
            color: #ffffff;
            border: none;
            padding: 9px 16px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
            transition: all 0.2s ease;
            min-width: 160px;
            text-align: center;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}
        
        .copy-btn:hover {{
            background-color: #1d4ed8;
            box-shadow: 0 4px 10px rgba(37, 99, 235, 0.4);
        }}
        
        /* 프리미엄 AI 분석 알림 상자 */
        .ai-banner {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-left: 5px solid #2563eb;
            border-radius: 12px;
            padding: 20px;
            color: var(--text-primary);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        
        .ai-banner h2 {{
            font-size: 16px;
            font-weight: 850;
            margin-bottom: 12px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            letter-spacing: -0.2px;
        }}
        
        .ai-content {{
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .ai-commentary-box {{
            background-color: var(--row-even-bg);
            border: 1px solid var(--border-color);
            border-left: 4px solid #2563eb;
            border-radius: 8px;
            padding: 14px 16px;
            margin-top: 10px;
        }}
        
        .ai-commentary-box p {{
            margin: 0;
            color: var(--text-secondary);
            font-size: 13.5px;
            line-height: 1.6;
        }}
        
        /* 리스크 그리드 레이아웃 */
        .dashboard-grid {{
            display: flex;
            flex-direction: column;
            gap: 24px;
            width: 100%;
        }}
        
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            display: flex;
            flex-direction: column;
            width: 100%;
        }}
        
        .card-header {{
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}
        
        /* 카테고리별 헤더 컬러 액센트 효과 */
        .card-header.caution {{ border-left: 5px solid var(--caution-color); }}
        .card-header.overheating {{ border-left: 5px solid var(--overheating-color); }}
        .card-header.trading {{ border-left: 5px solid var(--trading-color); }}
        .card-header.short {{ border-left: 5px solid var(--short-color); }}
        .card-header.other {{ border-left: 5px solid var(--other-color); }}
        
        .card-title {{
            font-size: 16px;
            font-weight: 800;
        }}
        
        .badge {{
            font-size: 12px;
            font-weight: 750;
            padding: 4px 10px;
            border-radius: 9999px;
            border: 1px solid var(--border-color);
        }}
        
        .badge.caution {{
            background-color: var(--caution-bg);
            color: var(--caution-color);
            border-color: var(--caution-border);
        }}
        
        .badge.overheating {{
            background-color: var(--overheating-bg);
            color: var(--overheating-color);
            border-color: var(--overheating-border);
        }}
        
        .badge.trading {{
            background-color: var(--trading-bg);
            color: var(--trading-color);
            border-color: var(--trading-border);
        }}
        
        .badge.short {{
            background-color: var(--short-bg);
            color: var(--short-color);
            border-color: var(--short-border);
        }}
        
        .badge.other {{
            background-color: var(--other-bg);
            color: var(--other-color);
            border-color: var(--other-border);
        }}
        
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
            background-color: var(--th-bg);
            color: var(--th-text);
            font-weight: 750;
            padding: 12px 20px;
            border-bottom: 2px solid var(--border-color);
        }}
        
        td {{
            padding: 12px 20px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-secondary);
            vertical-align: middle;
        }}
        
        tr:nth-child(even) td {{
            background-color: var(--row-even-bg);
        }}
        
        tr:hover td {{
            background-color: var(--hover-row-bg);
        }}
        
        .time-cell {{
            font-family: Monaco, Consolas, monospace;
            font-weight: 700;
            color: var(--time-color);
        }}
        
        .company-name {{
            font-weight: 800;
            color: var(--text-primary);
        }}
        
        .stock-code {{
            font-size: 12px;
            color: var(--text-muted);
            margin-left: 4px;
        }}
        
        .submitter-cell {{
            font-weight: 700;
            color: var(--text-secondary);
        }}
        
        .empty-state {{
            padding: 40px 24px;
            text-align: center;
            color: var(--text-muted);
            font-size: 13.5px;
            font-weight: 700;
        }}
        
        footer {{
            margin-top: 10px;
            padding: 16px 0;
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            border-top: 1px solid var(--border-color);
            font-weight: 700;
        }}
        
        /* 캡쳐 이미지 다운로드 팝업모달 */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(9, 13, 26, 0.85);
            backdrop-filter: blur(8px);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 10000;
            padding: 20px;
        }}
        
        .modal-overlay.active {{
            display: flex;
        }}
        
        .modal-content {{
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            max-width: 800px;
            width: 100%;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: modalFadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        
        @keyframes modalFadeIn {{
            from {{ transform: translateY(15px); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}
        
        .modal-header {{
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
        }}
        
        .modal-header h3 {{
            font-size: 15.5px;
            font-weight: 800;
            color: #ffffff;
        }}
        
        .modal-close-btn {{
            background: none;
            border: none;
            color: #94a3b8;
            font-size: 24px;
            cursor: pointer;
            line-height: 1;
            transition: color 0.2s;
        }}
        
        .modal-close-btn:hover {{
            color: #fafafa;
        }}
        
        .modal-body {{
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            max-height: 60vh;
            overflow-y: auto;
        }}
        
        .modal-instruction {{
            background-color: #0f172a;
            border: 1px solid #334155;
            border-left: 4px solid #a78bfa;
            border-radius: 8px;
            padding: 12px 16px;
            color: #cbd5e1;
            font-size: 13px;
            line-height: 1.6;
        }}
        
        .modal-image-container {{
            border: 1px solid #334155;
            border-radius: 8px;
            overflow: hidden;
            background-color: #0f172a;
            display: flex;
            justify-content: center;
        }}
        
        .modal-image-container img {{
            max-width: 100%;
            height: auto;
            display: block;
        }}
        
        .modal-footer {{
            padding: 16px 20px;
            display: flex;
            justify-content: flex-end;
            gap: 8px;
            border-top: 1px solid #334155;
            background-color: #1e293b;
        }}
        
        .modal-cancel-btn {{
            background-color: #334155;
            border: 1px solid #475569;
            color: #cbd5e1;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .modal-cancel-btn:hover {{
            background-color: #475569;
            color: #ffffff;
        }}
    </style>
    {html2canvas_script_tag}
    <script>
        // 사전 로드 체크용 객체
        window.html2canvasLoaded = true;
    </script>
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

        <!-- 탭 네비게이션 및 복사 영역 -->
        <div class="tabs-container">
            <div class="tabs-nav">
                <button class="tab-btn active" onclick="switchTab(event, 'all')">전체보기</button>
                <button class="tab-btn" onclick="switchTab(event, 'caution')">⚠️ 투자주의</button>
                <button class="tab-btn" onclick="switchTab(event, 'overheating')">🔥 단기과열</button>
                <button class="tab-btn" onclick="switchTab(event, 'warning_risk_trading')">🚨 투자경고 & 투자위험 & 매매거래</button>
                <button class="tab-btn" onclick="switchTab(event, 'short_selling')">📉 공매도</button>
                <button class="tab-btn" onclick="switchTab(event, 'others')">📝 기타</button>
            </div>
            <div class="controls-area" style="display: flex; gap: 8px;">
                <button class="theme-toggle-btn" onclick="toggleTheme()">
                    <span id="theme-btn-icon">☀️</span> <span id="theme-btn-text">라이트 모드</span>
                </button>
                <button class="copy-btn" onclick="copyCurrentTab()">📋 이미지 복사</button>
            </div>
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

HTML_CARD_START = """
            <section class="card" id="card-{cat_key}">
                <div class="card-header {badge_class}">
                    <h3 class="card-title">{icon} {title}</h3>
                    <span class="badge {badge_class}">{length}건 발생</span>
                </div>
                <div class="table-container">
"""

HTML_EMPTY_STATE = """
                    <div class="empty-state">
                        ✓ 당일 해당 유형의 특이사항 리스크 공시 내역이 없습니다. (안전)
                    </div>
"""

HTML_TABLE_START = """
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

HTML_TABLE_ROW = """
                            <tr>
                                <td class="time-cell">{time}</td>
                                <td>
                                     <span class="company-name">{company}</span>
                                     <span class="stock-code">({code})</span>
                                </td>
                                <td>{title}</td>
                                <td class="submitter-cell">{submitter}</td>
                            </tr>
"""

HTML_TABLE_END = """
                        </tbody>
                    </table>
"""

HTML_CARD_END = """
                </div>
            </section>
"""

HTML_FOOTER = """
        </main>
        
        <footer>
            본 보드는 공시 데이터를 파싱하여 가상 리스크 키워드 필터링 과정을 거쳐 자동 생성된 요약 참고용 리포트입니다.
        </footer>
    </div>
    
    <!-- 이미지 수동 복사 모달 -->
    <div id="image-modal" class="modal-overlay" onclick="closeImageModal()">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h3>📋 이미지 수동 복사 (클립보드 저장)</h3>
                <button class="modal-close-btn" onclick="closeImageModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="modal-instruction">
                    💡 <strong>보안 정책(로컬 파일 실행)으로 인해 자동 복사가 차단되었습니다.</strong><br>
                    아래 이미지를 <strong>우클릭하여 '이미지 복사'</strong>를 누르시면 클립보드에 정상 저장되어 
                    메신저나 메일에 <strong>바로 붙여넣기(Ctrl+V)</strong>하실 수 있습니다.
                </div>
                <div class="modal-image-container">
                    <img id="modal-preview-image" src="" alt="공시 대시보드 캡쳐본" style="cursor: context-menu;">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-cancel-btn" onclick="closeImageModal()" style="background-color: #2563eb; border: 1px solid #1d4ed8; color: #ffffff; min-width: 100px;">확인</button>
            </div>
        </div>
    </div>
    
    <!-- 탭 전환 및 복사 제어 스크립트 -->
    <script>
        let currentActiveTab = 'all';
        
        function toggleTheme() {
            const body = document.body;
            const btnIcon = document.getElementById('theme-btn-icon');
            const btnText = document.getElementById('theme-btn-text');
            
            if (body.classList.contains('light-mode')) {
                body.classList.remove('light-mode');
                if (btnIcon && btnText) {
                    btnIcon.innerText = '☀️';
                    btnText.innerText = '라이트 모드';
                }
            } else {
                body.classList.add('light-mode');
                if (btnIcon && btnText) {
                    btnIcon.innerText = '🌙';
                    btnText.innerText = '다크 모드';
                }
            }
        }
        
        function switchTab(evt, tabName) {
            currentActiveTab = tabName;
            
            // 탭 버튼 활성화 변경
            const tabButtons = document.querySelectorAll('.tab-btn');
            tabButtons.forEach(btn => btn.classList.remove('active'));
            evt.currentTarget.classList.add('active');
            
            // 전체보기일 경우 모든 카드 출력, 개별 탭일 경우 해당 카드만 출력
            const cards = document.querySelectorAll('.card');
            if (tabName === 'all') {
                cards.forEach(card => card.style.display = 'flex');
            } else {
                cards.forEach(card => {
                    if (card.id === 'card-' + tabName) {
                        card.style.display = 'flex';
                    } else {
                        card.style.display = 'none';
                    }
                });
            }
        }
        
        const tabNames = {
            'all': '전체보기',
            'caution': '투자주의',
            'overheating': '단기과열',
            'warning_risk_trading': '투자경고_위험_매매거래',
            'short_selling': '공매도',
            'others': '기타'
        };

        function copyCurrentTab() {
            const copyBtn = document.querySelector('.copy-btn');
            const originalText = copyBtn.innerHTML;
            
            // 이미지 캡쳐 대상 선택
            let targetEl = null;
            if (currentActiveTab === 'all') {
                targetEl = document.querySelector('.dashboard-grid');
            } else {
                targetEl = document.getElementById('card-' + currentActiveTab);
            }
            
            if (!targetEl) {
                alert("복사할 대상 카드를 찾을 수 없습니다.");
                return;
            }
            
            copyBtn.innerHTML = "⏳ 이미지 캡처 중...";
            copyBtn.style.backgroundColor = "#2563eb";
            
            try {
                if (typeof html2canvas === 'undefined') {
                    throw new Error("html2canvas 라이브러리가 로드되지 않았습니다. 인터넷 오프라인 상태이거나 CDN 경로가 연결되지 않았습니다.");
                }
                
                // html2canvas 실행
                let bgColor = getComputedStyle(document.body).getPropertyValue('--bg-color');
                if (!bgColor || bgColor.trim() === '') {
                    bgColor = document.body.classList.contains('light-mode') ? '#f8fafc' : '#0f172a';
                } else {
                    bgColor = bgColor.trim();
                }

                // 전체보기 탭은 크기가 커서 처리량이 상당하므로 scale: 1로 낮춰 속도를 극대화(4배 이상 빠름)하며,
                // 개별 카드 탭은 상대적으로 작으므로 scale: 1.5로 신속함과 선명도 밸런스를 맞춥니다.
                const captureScale = (currentActiveTab === 'all') ? 1.0 : 1.5;

                html2canvas(targetEl, {
                    useCORS: true,
                    allowTaint: true,
                    backgroundColor: bgColor,
                    scale: captureScale
                }).then(canvas => {
                    if (navigator.clipboard && navigator.clipboard.write) {
                        canvas.toBlob(blob => {
                            if (blob) {
                                const data = [new ClipboardItem({ [blob.type]: blob })];
                                navigator.clipboard.write(data).then(() => {
                                    showCopySuccess();
                                }).catch(err => {
                                    console.warn("Clipboard API write failed, trying selection copy fallback:", err);
                                    trySelectionCopy(canvas);
                                });
                            } else {
                                trySelectionCopy(canvas);
                            }
                        }, 'image/png');
                    } else {
                        trySelectionCopy(canvas);
                    }
                }).catch(err => {
                    alert("이미지 생성 중 오류가 발생했습니다: " + err.message);
                    copyBtn.innerHTML = originalText;
                    copyBtn.style.backgroundColor = "";
                });
            } catch (err) {
                alert("오류: " + err.message);
                copyBtn.innerHTML = originalText;
                copyBtn.style.backgroundColor = "";
            }
        }
        
        function trySelectionCopy(canvas) {
            // contenteditable 임시 컨테이너 생성하여 range 지정 후 copy 수행
            const tempDiv = document.createElement('div');
            tempDiv.style.position = 'fixed';
            tempDiv.style.left = '-9999px';
            tempDiv.style.top = '-9999px';
            tempDiv.style.webkitUserSelect = 'all';
            tempDiv.style.userSelect = 'all';
            tempDiv.contentEditable = true;

            const tempImg = document.createElement('img');
            // canvas를 Data URL로 변환하여 img src에 동기 할당
            tempImg.src = canvas.toDataURL('image/png');
            tempDiv.appendChild(tempImg);
            document.body.appendChild(tempDiv);

            // 포커스 후 선택
            tempDiv.focus();

            const range = document.createRange();
            range.selectNode(tempImg);

            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);

            let successful = false;
            try {
                successful = document.execCommand('copy');
            } catch (err) {
                console.error("Selection copy execCommand failed:", err);
            }

            // 선택 영역 및 엘리먼트 정리
            selection.removeAllRanges();
            document.body.removeChild(tempDiv);

            if (successful) {
                showCopySuccess();
            } else {
                console.warn("Selection copy fallback failed.");
                // 전체보기인 경우에는 로컬 복사 모달이 뜨는 것을 금지했으므로
                // 단순히 오류 메시지 또는 복사 실패 알림을 버튼에 출력
                if (currentActiveTab === 'all') {
                    showCopyFailure();
                } else {
                    // 개별 카드는 원래대로 수동 복사 모달 제공
                    fallbackImageModal(canvas);
                }
            }
        }
        
        let currentBlobUrl = null;

        function fallbackImageModal(canvas) {
            const copyBtn = document.querySelector('.copy-btn');
            copyBtn.innerHTML = "📋 이미지 복사";
            copyBtn.style.backgroundColor = "";
            
            canvas.toBlob(blob => {
                if (!blob) {
                    alert("이미지 변환에 실패했습니다.");
                    return;
                }
                if (currentBlobUrl) {
                    URL.revokeObjectURL(currentBlobUrl);
                }
                currentBlobUrl = URL.createObjectURL(blob);
                showImageModal(currentBlobUrl);
            }, 'image/png');
        }
        
        function showImageModal(url) {
            const modal = document.getElementById('image-modal');
            const previewImg = document.getElementById('modal-preview-image');
            previewImg.src = url;
            modal.classList.add('active');
        }
        
        function closeImageModal() {
            const modal = document.getElementById('image-modal');
            modal.classList.remove('active');
            setTimeout(() => {
                if (currentBlobUrl) {
                    URL.revokeObjectURL(currentBlobUrl);
                    currentBlobUrl = null;
                }
                const previewImg = document.getElementById('modal-preview-image');
                if (previewImg) previewImg.src = '';
            }, 300);
        }
        
        function showCopySuccess() {
            const copyBtn = document.querySelector('.copy-btn');
            copyBtn.innerHTML = "✅ 이미지 복사 완료!";
            copyBtn.style.backgroundColor = "#059669";
            setTimeout(() => {
                copyBtn.innerHTML = "📋 이미지 복사";
                copyBtn.style.backgroundColor = "";
            }, 1500);
        }

        function showCopyFailure() {
            const copyBtn = document.querySelector('.copy-btn');
            copyBtn.innerHTML = "❌ 복사 실패 (보안 제한)";
            copyBtn.style.backgroundColor = "#dc2626";
            setTimeout(() => {
                copyBtn.innerHTML = "📋 이미지 복사";
                copyBtn.style.backgroundColor = "";
            }, 2500);
        }
    </script>
</body>
</html>
"""
