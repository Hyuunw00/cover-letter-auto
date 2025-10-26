#!/usr/bin/env python3
"""
알림 시스템 모듈
- Slack 알림
- 이메일 알림
"""
import requests
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

# .env 로드
load_dotenv()


class NotificationManager:
    """알림 관리 클래스"""
    
    def __init__(self):
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.email_smtp_server = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.email_smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
        self.email_username = os.getenv('EMAIL_USERNAME')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_to = os.getenv('EMAIL_TO')
        
    def send_slack_notification(self, title, message, success=True):
        """Slack 알림 전송"""
        if not self.slack_webhook_url:
            print("⚠️ Slack 웹훅 URL이 설정되지 않았습니다")
            return False
            
        try:
            # 색상 설정 (성공: 초록, 실패: 빨강)
            color = "#36a64f" if success else "#ff0000"
            emoji = "✅" if success else "❌"
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{emoji} {title}",
                        "text": message,
                        "footer": "자소설 자동화",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
            
            response = requests.post(
                self.slack_webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                print("✓ Slack 알림 전송 성공")
                return True
            else:
                print(f"❌ Slack 알림 전송 실패: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Slack 알림 전송 오류: {e}")
            return False
    
    def send_email_notification(self, title, message, success=True):
        """이메일 알림 전송"""
        if not all([self.email_username, self.email_password, self.email_to]):
            print("⚠️ 이메일 설정이 완전하지 않습니다")
            return False
            
        try:
            # 이메일 구성
            msg = MIMEMultipart()
            msg['From'] = self.email_username
            msg['To'] = self.email_to
            msg['Subject'] = f"[자소설 자동화] {title}"
            
            # 상태에 따른 내용 구성
            status_text = "성공" if success else "실패"
            status_emoji = "✅" if success else "❌"
            
            body = f"""
{status_emoji} 자소설 자동화 작업 결과

제목: {title}
상태: {status_text}
시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

내용:
{message}

---
자소설 자동화 시스템
            """
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # SMTP 서버 연결 및 전송
            server = smtplib.SMTP(self.email_smtp_server, self.email_smtp_port)
            server.starttls()
            server.login(self.email_username, self.email_password)
            
            text = msg.as_string()
            server.sendmail(self.email_username, self.email_to, text)
            server.quit()
            
            print("✓ 이메일 알림 전송 성공")
            return True
            
        except Exception as e:
            print(f"❌ 이메일 알림 전송 오류: {e}")
            return False
    
    def send_job_completion_notification(self, job_results):
        """작업 완료 알림 전송"""
        total_jobs = len(job_results)
        successful_jobs = sum(1 for result in job_results if result.get('success', False))
        failed_jobs = total_jobs - successful_jobs
        
        # 제목 생성
        if successful_jobs == total_jobs:
            title = f"모든 작업 완료 ({successful_jobs}개)"
            success = True
        elif successful_jobs > 0:
            title = f"부분 완료 ({successful_jobs}/{total_jobs})"
            success = True
        else:
            title = f"작업 실패 ({failed_jobs}개)"
            success = False
        
        # 메시지 생성
        message_lines = [
            f"📊 처리 결과: {successful_jobs}개 성공, {failed_jobs}개 실패",
            f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # 각 작업 결과 상세
        for i, result in enumerate(job_results, 1):
            status_emoji = "✅" if result.get('success', False) else "❌"
            company = result.get('company_name', '알 수 없음')
            job_title = result.get('job_title', '알 수 없음')
            error = result.get('error', '')
            
            message_lines.append(f"{i}. {status_emoji} {company} - {job_title}")
            if error:
                message_lines.append(f"   오류: {error}")
        
        message = "\n".join(message_lines)
        
        # 알림 전송
        slack_success = self.send_slack_notification(title, message, success)
        email_success = self.send_email_notification(title, message, success)
        
        return slack_success or email_success
    
    def send_error_notification(self, error_message, job_id=None):
        """오류 알림 전송"""
        title = f"자동화 오류 발생"
        if job_id:
            title += f" (공고 ID: {job_id})"
        
        message = f"""
🚨 자소설 자동화에서 오류가 발생했습니다

오류 내용:
{error_message}

시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

확인이 필요합니다.
        """
        
        # 알림 전송
        slack_success = self.send_slack_notification(title, message, success=False)
        email_success = self.send_email_notification(title, message, success=False)
        
        return slack_success or email_success


def test_notifications():
    """알림 시스템 테스트"""
    print("🔔 알림 시스템 테스트 시작")
    
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
            'success': False,
            'company_name': '테스트 회사 B',
            'job_title': '프론트엔드 개발자',
            'error': '키워드 매칭 실패'
        }
    ]
    
    # 작업 완료 알림 테스트
    print("\n📧 작업 완료 알림 테스트")
    notifier.send_job_completion_notification(test_results)
    
    # 오류 알림 테스트
    print("\n🚨 오류 알림 테스트")
    notifier.send_error_notification("테스트 오류 메시지", "TEST123")


if __name__ == "__main__":
    test_notifications()
