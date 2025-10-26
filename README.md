# 자기소개서 자동화

자소설(jasoseol.com)과 ChatGPT를 활용한 자기소개서 자동 작성 시스템

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [시스템 구조](#시스템-구조)
- [설치 및 설정](#설치-및-설정)
- [사용 방법](#사용-방법)
- [스케줄 설정](#스케줄-설정)
- [문제 해결](#문제-해결)

## 개요

### 목적
- 자소설 사이트의 채용 공고를 자동으로 확인하고 자기소개서 작성
- ChatGPT '테오 입사지원' 프로젝트를 활용한 고품질 답변 생성
- 매일 반복되는 작업을 완전 자동화하여 시간 절약

### 핵심 가치
- **완전 자동화**: 공고 확인부터 저장까지 사람 개입 없이 실행
- **품질 유지**: ChatGPT Projects에 저장된 개인 정보 활용
- **시간 절약**: 매일 2-3시간 소요 작업을 자동화

## 주요 기능

### 1. 일일 자동화 (`daily_automation.py`)
- **캘린더 기반 공고 수집**: 당일 날짜의 공고만 자동 추출
- **즐겨찾기 필터링**: 이미 처리한 공고는 자동 제외
- **키워드 매칭**: 설정한 직무 키워드와 일치하는 공고만 처리
- **자동 종료**: 모든 작업 완료 후 브라우저 자동 종료

### 2. 단일 공고 처리 (`complete_automation.py`)
- 특정 공고 ID를 지정하여 테스트 가능
- 디버깅 및 검증용

### 3. 자동 프로세스
```
1. 캘린더에서 당일 공고 확인
2. 즐겨찾기 안 된 공고 필터링
3. 키워드 매칭 확인
4. ChatGPT로 답변 생성
5. 자소설 페이지에 답변 입력
6. 저장 및 즐겨찾기
7. 브라우저 종료
```

## 시스템 구조

### 디렉토리 구조
```
jasoseol-auto/
├── config/
│   ├── keywords.yaml        # 키워드 설정
│   └── prompts.yaml         # ChatGPT 프롬프트
├── scripts/
│   ├── daily_automation.py  # 일일 자동화 메인 스크립트
│   └── complete_automation.py  # 단일 공고 테스트
├── output/
│   ├── browser_profile/     # 자소설 세션 정보
│   ├── chatgpt_profile/     # ChatGPT 세션 정보
│   ├── daily_automation.log # 실행 로그
│   └── questions_*.json     # 추출된 질문/답변
├── com.jasoseol.daily.plist # macOS 스케줄 설정
└── README.md
```

### 기술 스택
- **언어**: Python 3.10+
- **웹 자동화**: Playwright (persistent context)
- **AI**: ChatGPT Web (chat.openai.com)
- **스케줄**: macOS launchd

## 설치 및 설정

### 1. 가상환경 및 패키지 설치
```bash
# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
playwright install chromium
```

### 2. 초기 로그인 (최초 1회만)

자소설과 ChatGPT에 수동 로그인하여 세션 정보 저장:

```bash
# 자소설 로그인
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch_persistent_context('output/browser_profile', headless=False); browser.pages[0].goto('https://jasoseol.com'); input('로그인 후 엔터...')"

# ChatGPT 로그인
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch_persistent_context('output/chatgpt_profile', headless=False); browser.pages[0].goto('https://chatgpt.com'); input('로그인 후 엔터...')"
```

### 3. 키워드 설정

`config/keywords.yaml` 파일에서 원하는 직무 키워드 설정:

```yaml
career_types:
  - 신입
  - 신입/경력

keywords:
  priority_1:
    - Frontend
    - Front-end
    - 프론트엔드

  priority_2:
    - IT
    - 개발
    - Backend
    - 백엔드
```

## 사용 방법

### 수동 실행
```bash
# 일일 자동화 실행
source venv/bin/activate
python scripts/daily_automation.py

# 로그 실시간 확인
tail -f output/daily_automation.log
```

### 특정 공고 테스트
```bash
# 공고 ID를 지정하여 테스트
python scripts/complete_automation.py
```

## 스케줄 설정

### macOS에서 매일 자동 실행 설정

스케줄 작업이 이미 등록되어 있습니다 (매일 오후 2시 실행).

#### 스케줄 관리 명령어
```bash
# 스케줄 상태 확인
launchctl list | grep jasoseol

# 스케줄 중지
launchctl unload ~/Library/LaunchAgents/com.jasoseol.daily.plist

# 스케줄 재시작
launchctl load ~/Library/LaunchAgents/com.jasoseol.daily.plist
```

### 필수 조건 (자동 실행 시)
1. **노트북 전원 연결**: 항상 전원에 연결되어 있어야 함
2. **슬립 방지**: 컴퓨터가 슬립 모드로 들어가지 않도록 설정
   ```bash
   sudo pmset -c sleep 0
   sudo pmset -c disksleep 0
   sudo pmset -c displaysleep 10
   ```
3. **화면 잠금 해제**: 화면이 꺼져도 암호 요구하지 않도록 설정
   - 시스템 설정 > 잠금 화면 > "화면이 꺼진 후 로그인 요구" → "안 함"

## 설정 파일

### keywords.yaml
직무 키워드 및 경력 타입 설정:
- `career_types`: 지원 가능한 경력 타입
- `keywords.priority_1`: 우선순위 높은 키워드
- `keywords.priority_2`: 일반 키워드

### prompts.yaml
ChatGPT 프롬프트 템플릿:
- `company_research`: 회사/직무 정보 조사 프롬프트
- `writing_rules`: 자기소개서 작성 규칙
- `question`: 문항별 질문 프롬프트

## 로그 및 출력

### 로그 파일
- `output/daily_automation.log`: 실행 로그 (실시간 기록)
- `output/launchd.log`: 스케줄 실행 로그

### JSON 출력
- `output/questions_{공고ID}.json`: 각 공고별 질문 및 답변 저장

```json
{
  "job_id": "100514",
  "company_name": "회사명",
  "job_title": "공고명",
  "position": "직무",
  "questions": [
    {
      "number": 1,
      "text": "질문 내용",
      "char_limit": "1000",
      "answer": "생성된 답변"
    }
  ]
}
```

## 문제 해결

### 자주 발생하는 문제

**Q: 스케줄이 실행되지 않아요**
- 노트북이 슬립 모드인지 확인
- `launchctl list | grep jasoseol`로 등록 여부 확인
- `output/launchd.log`에서 오류 확인

**Q: 로그인이 필요하다고 나와요**
- 세션이 만료되었을 수 있음
- 수동으로 다시 로그인 (위 "초기 로그인" 참고)

**Q: 키워드 매칭이 안 돼요**
- `config/keywords.yaml` 파일 확인
- 대소문자 구분 없이 매칭되므로 키워드 추가

**Q: ChatGPT 답변이 생성되지 않아요**
- '테오 입사지원' 프로젝트가 있는지 확인
- ChatGPT 세션 다시 로그인

### 디버깅

```bash
# 상세 로그 확인
tail -f output/daily_automation.log

# 백그라운드 프로세스 확인
ps aux | grep daily_automation

# 프로세스 종료
pkill -f daily_automation.py
```

## 주의사항

1. **브라우저 프로필 백업**: `output/browser_profile`, `output/chatgpt_profile` 디렉토리는 `.gitignore`에 등록되어 있음
2. **로그 파일 관리**: 로그 파일이 계속 누적되므로 주기적으로 삭제 권장
3. **ChatGPT 사용량**: ChatGPT Plus 구독 필요 (프로젝트 기능)
4. **개인정보 보호**: JSON 파일에 개인 정보가 포함되므로 공유 금지

## 라이선스

개인 사용 목적

## 문의

이슈 또는 개선 사항은 GitHub Issues에 등록해주세요.
