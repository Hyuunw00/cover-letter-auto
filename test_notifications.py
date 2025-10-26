#!/usr/bin/env python3
"""
알림 시스템 테스트 스크립트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from src.utils.notifications import NotificationManager


def test_notifications():
    """알림 시스템 테스트"""
    print("🔔 알림 시스템 테스트 시작")
    print("=" * 50)
    
    notifier = NotificationManager()
    
    # 테스트 데이터
    test_results = [
        {
            'success': True,
            'company_name': '테스트 회사 A',
            'job_title': '백엔드 개발자',
            'error': None
        },
        {
            'success': True,
            'company_name': '테스트 회사 B',
            'job_title': '프론트엔드 개발자',
            'error': None
        },
        {
            'success': False,
            'company_name': '테스트 회사 C',
            'job_title': '데이터 분석가',
            'error': '키워드 매칭 실패'
        }
    ]
    
    print("📧 작업 완료 알림 테스트")
    print("-" * 30)
    success = notifier.send_job_completion_notification(test_results)
    print(f"결과: {'성공' if success else '실패'}")
    
    print("\n🚨 오류 알림 테스트")
    print("-" * 30)
    success = notifier.send_error_notification("테스트 오류 메시지입니다", "TEST123")
    print(f"결과: {'성공' if success else '실패'}")
    
    print("\n" + "=" * 50)
    print("테스트 완료!")
    
    if not success:
        print("\n⚠️ 알림 전송이 실패했습니다.")
        print("다음을 확인해주세요:")
        print("1. .env 파일에 올바른 설정이 있는지")
        print("2. Slack 웹훅 URL이 유효한지")
        print("3. 이메일 계정 설정이 올바른지")
        print("4. 인터넷 연결 상태")


if __name__ == "__main__":
    test_notifications()
