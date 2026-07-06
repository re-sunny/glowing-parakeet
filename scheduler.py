import os
import sys
import time
import datetime
import subprocess

# Windows CP949 console encoding fix
if sys.platform.startswith('win'):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

from scraper_krx import download_today_disclosures


def run_schedule_loop(target_hour=20, target_minute=5):
    """
    백그라운드에서 대기하며 매일 지정된 시간(실제 로컬 컴퓨터 시간 기준)에 엑셀 다운로드를 트리거합니다.
    """
    print(f"⏰ 공시 스케줄러가 활성화되었습니다. (매일 {target_hour:02d}:{target_minute:02d}에 작동)")
    print("💡 이 스크립트를 백그라운드에 켜두시면 정밀 감시를 수행합니다.")
    
    last_triggered_date = None
    
    while True:
        now = datetime.datetime.now()
        current_date = now.date()
        
        # 특정 서브 타켓 시간에 진입했고, 오늘 아직 다운로드가 실행되지 않았는지 체크
        if now.hour == target_hour and now.minute == target_minute:
            if last_triggered_date != current_date:
                print(f"\n {now.strftime('%Y-%m-%d %H:%M:%S')} 스케줄 발동! 크롤링 및 다운로드를 개시합니다.")
                
                try:
                    file_path = download_today_disclosures()
                    
                    if file_path and os.path.exists(file_path):
                        print(f"✅ 파일 다운로드 완료: {file_path}")
                        
                        # [선택사항] 20:05 자동 수집 후, 기본 사전 정의 키워드로 바로 보고서 생성 자동화
                        # 예시로 default_keywords가 있는 경우 리포팅 프로세스 자동 실행
                        print(" [자동화] 20:00시 이후 모든 공시 데이터를 기반으로 리포트를 생성합니다...")
                        
                        # read_excel_auto.py를 실행하거나 패키지 모듈 함수 호출
                        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "read_excel_auto.py")
                        if os.path.exists(script_path):
                            # Python 스크립트 실행으로 트리거 (파이썬 프로세스 호출)
                            import sys
                            args_to_run = [
                                sys.executable, script_path, 
                                "--auto", 
                                "--file", file_path
                            ]
                            if "--no-ai" in sys.argv:
                                args_to_run.append("--no-ai")
                                
                            subprocess.run(args_to_run)
                        else:
                            print(" read_excel_auto.py 스크립트를 찾을 수 없어 자동 리포트 작성을 건너뜁니다.")
                                    
                    else:
                        print(" 다운로드된 파일을 찾지 못했습니다. 크롤러 응답을 점검하세요.")
                        
                except Exception as e:
                    print(f" 작업 수행 중 이상 오류 감지: {e}")
                    
                # 오늘자 작업 수행으로 락 걸기 (한 번만 일하도록 방지)
                last_triggered_date = current_date
        
        # 30초 대기 후 재 검사
        time.sleep(30)

if __name__ == "__main__":
    # 테스트 목적: 스케줄러 시뮬레이션을 쉽게 할 수 있도록 
    # 현재 시간 기준 1분 후로 자동 트리거하는 기능 추가 가능
    import sys
    if "--test" in sys.argv:
        test_now = datetime.datetime.now() + datetime.timedelta(minutes=1)
        
        print(f"🧪 [테스트 모드 활성화] {test_now.strftime('%H:%M')} 에 즉시 구동을 시작하도록 예약합니다.")
        print(test_now.hour+":"+test_now.minute)
        run_schedule_loop(target_hour=test_now.hour, target_minute=test_now.minute)
    else:
        # test_now = datetime.datetime.now() + datetime.timedelta(minutes=1)
        # print(str(test_now.hour)+":"+test_now.minute)
        run_schedule_loop(target_hour=20, target_minute=5)
        # 20시 5분에 하기 위해서 수동 조정