#!/usr/bin/env python3
"""
일일 자동화 스크립트
- 당일 날짜의 공고들을 확인
- 즐겨찾기 안된 공고들 차례대로 자동화 진행
- 처리할 공고 없으면 브라우저 종료
"""
import asyncio
import yaml
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# 알림 시스템 import
sys.path.append(str(Path(__file__).parent.parent))
from src.utils.notifications import NotificationManager

# .env 로드
load_dotenv()

# 로그 파일 설정
LOG_FILE = Path("output/daily_automation.log")
LOG_FILE.parent.mkdir(exist_ok=True)

# 로그 파일 초기화 (새 실행마다 새 로그)
with open(LOG_FILE, 'w', encoding='utf-8') as f:
    f.write(f"=== 일일 자동화 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")

# print 함수를 로그 파일에도 기록하도록 오버라이드
_original_print = print
def print(*args, **kwargs):
    _original_print(*args, **kwargs)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        _original_print(*args, **kwargs, file=f)
    sys.stdout.flush()


def load_keywords():
    """키워드 설정 로드"""
    config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_prompts():
    """프롬프트 템플릿 로드"""
    config_path = Path(__file__).parent.parent / "config" / "prompts.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


async def get_today_job_list(page):
    """29일 공고만 가져오기"""
    # 29일 고정
    date_list = ["20251029"]

    print(f"  처리 대상 날짜: {date_list[0]} (29일 고정)")

    jobs = []

    for target_date in date_list:
        # 해당 날짜의 day-content 찾기
        day_selector = f'div.day-content[day="{target_date}"]'
        day_content = await page.query_selector(day_selector)

        if not day_content:
            print(f"  ⚠️ {target_date} 날짜에 공고가 없습니다")
            continue

        # 해당 날짜의 모든 공고 아이템 찾기
        job_items = await day_content.query_selector_all('.calendar-item.employment')

        if not job_items:
            print(f"  ⚠️ {target_date} 날짜에 공고가 없습니다")
            continue

        for item in job_items:
            # 클래스 목록 가져오기
            class_name = await item.get_attribute('class')

            # 즐겨찾기 확인 (no-favorite 클래스가 있으면 즐겨찾기 안됨)
            if 'no-favorite' not in class_name:
                continue  # 이미 즐겨찾기된 공고는 건너뛰기

            # 단일 공고인지 그룹 공고인지 확인
            if 'single_employment' in class_name:
                # 단일 공고 - employment_id로 바로 접근 가능
                employment_id = await item.get_attribute('employment_id')
                if employment_id:
                    jobs.append({
                        'type': 'single',
                        'employment_id': employment_id,
                        'date': target_date
                    })
            elif 'grouped_employment' in class_name:
                # 그룹 공고 - 클릭해서 목록 봐야함 (일단 스킵)
                print(f"  ⚠️ 그룹 공고는 현재 지원하지 않습니다 (추후 구현 예정)")
                continue

    return jobs


async def find_matching_positions(page):
    """키워드 매칭되는 직무 찾기"""
    config = load_keywords()
    allowed_career_types = config['career_types']

    keywords_by_priority = []
    for priority in ['priority_1', 'priority_2', 'priority_3']:
        if priority in config['keywords']:
            keywords_by_priority.append({
                'priority': priority,
                'keywords': config['keywords'][priority]
            })

    positions = await page.query_selector_all(".bg-white.hover\\:bg-gray-100")
    matched_positions = []

    print(f"  [디버그] 총 {len(positions)}개 직무 박스 발견")

    for pos in positions:
        position_text = await pos.inner_text()
        lines = [line.strip() for line in position_text.split('\n') if line.strip()]

        print(f"  [디버그] 직무 박스 내용: {lines[:5]}")  # 처음 5줄만

        if len(lines) < 2:
            print(f"  [디버그] 건너뛰기: lines 개수 부족 ({len(lines)}개)")
            continue

        # 실제 DOM 구조: [경력타입, 직무명, 작성자수]
        career_type = lines[0]
        position_name = lines[1]
        # 직무명 + 키워드 텍스트 모두 매칭 대상에 포함
        keywords_text = ' '.join([position_name] + lines[2:])

        print(f"  [디버그] 경력: {career_type}, 직무명: {position_name}, 키워드: {keywords_text}")

        if career_type not in allowed_career_types:
            continue

        for prio_group in keywords_by_priority:
            priority = prio_group['priority']
            keywords = prio_group['keywords']

            # 대소문자 구분 없이 키워드 매칭
            matched_keywords = [kw for kw in keywords if kw.lower() in keywords_text.lower()]
            if matched_keywords:
                matched_positions.append({
                    'position_name': position_name,
                    'career_type': career_type,
                    'keywords': keywords_text,
                    'matched_keywords': matched_keywords,
                    'priority': priority
                })
                break

    return matched_positions


async def extract_questions_from_jasoseol(page):
    """자소설 페이지에서 질문 추출"""
    questions = []

    # "+" 버튼과 "—" 버튼 제외하고 실제 질문 탭만 선택
    tabs = await page.query_selector_all("ul.nav-pills li.uib-tab")

    print(f"  [디버그] 탭 개수: {len(tabs)}")

    for idx, tab in enumerate(tabs, 1):
        await tab.click()
        await asyncio.sleep(0.5)

        active_tab = await page.query_selector(".tab-pane.active")
        if not active_tab:
            print(f"  [디버그] 문항 {idx}: active 탭 없음")
            continue

        # 질문 텍스트 (textarea.qna-question)
        question_elem = await active_tab.query_selector("textarea.qna-question")
        if not question_elem:
            print(f"  [디버그] 문항 {idx}: 질문 요소 없음")
            continue

        question_text = await question_elem.input_value()
        question_text = question_text.strip()

        # 글자수 제한 (span.total)
        char_limit_elem = await active_tab.query_selector("span.total")
        char_limit = "1000"
        if char_limit_elem:
            char_limit_text = await char_limit_elem.inner_text()
            # "1000" 또는 "제한 없음"
            if char_limit_text != "제한 없음":
                char_limit = char_limit_text.strip()

        print(f"  [디버그] 문항 {idx}: 질문='{question_text[:30]}...', 제한={char_limit}")

        questions.append({
            "number": idx,
            "text": question_text,
            "char_limit": char_limit
        })

    return questions


async def find_teo_project(page):
    """'테오 입사지원' 프로젝트 찾기"""
    print("\n['테오 입사지원' 프로젝트 찾기]")

    try:
        # 페이지 로드 대기
        await asyncio.sleep(3)

        # 첫 번째 시도: 보이는 프로젝트에서 찾기
        project_links = await page.query_selector_all("a[href^='/g/']")
        print(f"  [디버그] 발견된 프로젝트 링크 개수: {len(project_links)}")

        for link in project_links:
            text = await link.inner_text()
            print(f"  [디버그] 프로젝트: {text.strip()}")
            if "테오 입사지원" in text:
                await link.click()
                await asyncio.sleep(3)
                print(f"  ✓ 프로젝트 발견: {text.strip()}")
                return True

        # 못 찾았으면 "더 보기" 버튼 클릭
        print("  [디버그] '테오 입사지원'을 찾지 못함, '더 보기' 버튼 찾는 중...")
        more_button = await page.query_selector("div.__menu-item:has-text('더 보기')")

        if more_button:
            print("  [디버그] '더 보기' 버튼 클릭")
            await more_button.click()
            await asyncio.sleep(2)

            # 다시 검색
            project_links = await page.query_selector_all("a[href^='/g/']")
            print(f"  [디버그] '더 보기' 후 프로젝트 링크 개수: {len(project_links)}")

            for link in project_links:
                text = await link.inner_text()
                print(f"  [디버그] 프로젝트: {text.strip()}")
                if "테오 입사지원" in text:
                    await link.click()
                    await asyncio.sleep(3)
                    print(f"  ✓ 프로젝트 발견: {text.strip()}")
                    return True

        print("  ❌ '테오 입사지원' 프로젝트를 찾을 수 없음")
        print(f"  [힌트] ChatGPT 페이지 URL: {page.url}")
        return False

    except Exception as e:
        print(f"  ❌ 프로젝트 검색 실패: {e}")
        return False


async def wait_for_response_complete(page, timeout=180):
    """
    ChatGPT 응답 완료 대기
    - stop-button이 사라지고 composer-speech-button이 나타나면 완료
    """
    from datetime import datetime

    start_time = datetime.now()

    # 메시지 전송 직후 약간 대기
    await asyncio.sleep(2)

    print("  [대기] AI 응답 완료 대기 중...")

    while True:
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > timeout:
            print(f"  ⚠️ 응답 대기 타임아웃 ({timeout}초)")
            return False

        # stop-button이 있는지 확인 (응답 중)
        stop_button = await page.query_selector("button[data-testid='stop-button']")

        # 음성버튼이 있는지 확인 (응답 완료 후 기본 상태)
        speech_button = await page.query_selector("button[data-testid='composer-speech-button']")

        # stop-button이 없고 speech-button이 있으면 완료
        if not stop_button and speech_button:
            print(f"  ✓ 응답 완료 감지 (소요시간: {elapsed:.1f}초)")
            # 응답이 완전히 렌더링될 때까지 추가 대기
            await asyncio.sleep(1)
            return True

        await asyncio.sleep(1.5)


async def send_chatgpt_message(page, message):
    """ChatGPT에 메시지 전송하고 응답 받기"""
    # 입력창 찾기 (contenteditable div 사용)
    input_box = await page.query_selector("[contenteditable='true']")

    if not input_box:
        print("  ❌ 입력창을 찾을 수 없습니다")
        return None

    # 메시지 입력
    await input_box.click()
    await asyncio.sleep(0.5)
    await input_box.fill(message)

    # 전송 버튼이 나타날 때까지 대기 (입력값이 있어야 나타남)
    send_button = None
    for _ in range(10):  # 최대 10초 대기
        btn = await page.query_selector("button[data-testid='send-button']")
        if btn:
            try:
                if await btn.is_visible() and await btn.is_enabled():
                    send_button = btn
                    break
            except:
                pass
        await asyncio.sleep(1)

    if send_button:
        await send_button.click()
        print("  ✓ 메시지 전송 완료 (전송 버튼 클릭)")
    else:
        # 전송 버튼이 안 나타나면 Enter로 fallback
        await input_box.press("Enter")
        print("  ⚠️ 전송 버튼 미발견, Enter로 전송")

    # 응답 완료 대기
    response_complete = await wait_for_response_complete(page)
    if not response_complete:
        print("  ❌ 응답 대기 실패")
        return None

    print("  ✓ AI 응답 완료")

    # 마지막 응답 추출
    try:
        messages = await page.query_selector_all("[data-message-author-role='assistant']")
        if messages:
            last_message = messages[-1]
            answer_text = await last_message.inner_text()
            return answer_text.strip()
        else:
            print("  ⚠️ 응답 메시지를 찾을 수 없음")
            return None
    except Exception as e:
        print(f"  ❌ 응답 추출 실패: {e}")
        return None


async def process_single_job(job_id, jasoseol_context, chatgpt_page):
    """단일 공고 처리 (기존 complete_automation 로직)"""
    print("\n" + "=" * 80)
    print(f"공고 처리 시작: {job_id}")
    print("=" * 80)

    jasoseol_page = jasoseol_context.pages[0] if jasoseol_context.pages else await jasoseol_context.new_page()
    
    # 결과 추적을 위한 변수들
    job_result = {
        'job_id': job_id,
        'success': False,
        'company_name': '',
        'job_title': '',
        'error': None
    }

    try:
        # === 1단계: 자소설에서 정보 추출 ===
        print("\n[1단계] 자소설 - 정보 추출")

        # 공고 페이지 접근
        await jasoseol_page.goto(f"https://jasoseol.com/recruit/{job_id}")
        await jasoseol_page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 회사명/공고명 추출
        page_title = await jasoseol_page.title()
        company_name = page_title.split("채용공고")[0].strip() if "채용공고" in page_title else ""

        h1_element = await jasoseol_page.query_selector("h1")
        job_title = await h1_element.inner_text() if h1_element else ""

        # 결과에 정보 저장
        job_result['company_name'] = company_name
        job_result['job_title'] = job_title

        print(f"  회사명: {company_name}")
        print(f"  공고명: {job_title}")

        # 키워드 매칭
        await jasoseol_page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        matched = await find_matching_positions(jasoseol_page)
        if not matched:
            print("  ❌ 매칭된 직무 없음 - 건너뛰기")
            job_result['error'] = "키워드 매칭 실패"
            return job_result

        top_position = matched[0]
        print(f"  직무: {top_position['position_name']}")

        # 자기소개서 준비중인지 체크
        preparing_element = await jasoseol_page.query_selector('td[ng-if="!employment.employment_resume"]:has-text("자기소개서 준비중")')
        if preparing_element:
            print("  ⚠️ 자기소개서 준비중 - 건너뛰기")
            job_result['error'] = "자기소개서 준비중"
            return job_result

        # 자기소개서 쓰기 버튼 클릭 (div.write-resume-button 또는 기존 button 방식 둘다 지원)
        write_buttons = await jasoseol_page.query_selector_all("div.write-resume-button:has-text('자기소개서 쓰기'), button:has-text('자기소개서 쓰기')")
        if write_buttons:
            async with jasoseol_context.expect_page() as new_page_info:
                await write_buttons[0].click()

            new_page = await new_page_info.value
            await new_page.wait_for_load_state("networkidle")
            jasoseol_page = new_page
            await asyncio.sleep(2)

            # 모달 처리 - "예" 버튼 클릭
            try:
                yes_button = await jasoseol_page.wait_for_selector(
                    "div.modal-footer button.btn-primary:has-text('예')",
                    timeout=5000
                )
                if yes_button:
                    await yes_button.click()
                    await asyncio.sleep(1)
                    print("  ✓ 팝업창 '예' 클릭")
            except:
                pass

        # 질문 추출
        questions = await extract_questions_from_jasoseol(jasoseol_page)
        print(f"  ✓ {len(questions)}개 질문 추출")

        # JSON 저장
        output_dir = Path("output")
        job_data = {
            "job_id": job_id,
            "company_name": company_name,
            "job_title": job_title,
            "position": top_position['position_name'],
            "career_type": top_position['career_type'],
            "questions": questions
        }

        json_path = output_dir / f"questions_{job_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, ensure_ascii=False, indent=2)

        print(f"  ✓ 데이터 저장: {json_path}")

        # === 2단계: ChatGPT에서 답변 생성 ===
        print("\n[2단계] ChatGPT - 답변 생성")

        # 프롬프트 로드
        prompts = load_prompts()

        # 프롬프트 1: 회사/직무 정보 조사
        prompt1 = prompts['company_research'].format(
            company_name=company_name,
            job_title=job_title,
            position=top_position['position_name']
        )
        print("\n  [프롬프트 1] 회사/직무 정보 조사")
        await send_chatgpt_message(chatgpt_page, prompt1)
        print("  ✓ 응답 받음")

        # 프롬프트 2: 작성 규칙
        prompt2 = prompts['writing_rules'].format(
            company_name=company_name,
            position=top_position['position_name']
        )
        print("\n  [프롬프트 2] 작성 규칙")
        await send_chatgpt_message(chatgpt_page, prompt2)
        print("  ✓ 응답 받음")

        # 각 문항 질문 전송
        for q in questions:
            prompt_q = prompts['question_template'].format(
                number=q['number'],
                question=q['text'],
                char_limit=q['char_limit']
            )
            print(f"\n  [문항 {q['number']}] 질문 전송")
            answer = await send_chatgpt_message(chatgpt_page, prompt_q)

            # 답변 저장
            q['answer'] = answer if answer else "응답 없음"
            print(f"  ✓ 답변 받음 ({len(answer) if answer else 0}자)")

        # 업데이트된 JSON 저장
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, ensure_ascii=False, indent=2)

        print(f"\n  ✓ 답변이 포함된 데이터 저장: {json_path}")

        # === 3단계: 자소설에 답변 입력 ===
        print("\n[3단계] 자소설 - 답변 입력")

        # 자소설 페이지로 전환 (이미 열려있음)
        await jasoseol_page.bring_to_front()
        await asyncio.sleep(1)

        # 팝업창이 뜨면 "예" 버튼 클릭
        try:
            yes_button = await jasoseol_page.wait_for_selector(
                "div.modal-footer button.btn-primary:has-text('예')",
                timeout=3000
            )
            if yes_button:
                await yes_button.click()
                await asyncio.sleep(1)
                print("  ✓ 팝업창 '예' 클릭")
        except:
            # 팝업이 없으면 무시
            pass

        # 각 질문 탭 클릭하고 답변 입력
        for q in questions:
            question_num = q['number']
            answer = q.get('answer', '')

            if not answer or answer == "응답 없음":
                print(f"  [문항 {question_num}] 답변 없음 - 건너뛰기")
                continue

            print(f"  [문항 {question_num}] 답변 입력 중...")

            # 해당 번호의 탭 버튼 클릭
            nav_buttons = await jasoseol_page.query_selector_all("ul.nav-pills li")
            for btn in nav_buttons:
                text = await btn.inner_text()
                if text.strip() == str(question_num):
                    await btn.click()
                    await asyncio.sleep(1)
                    break

            # 활성화된 탭의 답변 textarea 찾기
            active_tab = await jasoseol_page.query_selector(".tab-pane.active")
            if not active_tab:
                print(f"  ⚠️ 활성화된 탭을 찾을 수 없음")
                continue

            answer_textarea = await active_tab.query_selector("textarea.answer")
            if not answer_textarea:
                print(f"  ⚠️ 답변 입력창을 찾을 수 없음")
                continue

            # AngularJS를 위한 입력 (JavaScript로 직접 값 설정 + 이벤트 트리거)
            await answer_textarea.click()
            await asyncio.sleep(0.3)

            # JavaScript로 값 설정하고 AngularJS 이벤트 트리거
            await jasoseol_page.evaluate("""
                (answer) => {
                    const textarea = document.querySelector('.tab-pane.active textarea.answer');
                    if (textarea) {
                        textarea.value = answer;
                        // AngularJS의 change 감지를 위해 input 이벤트 트리거
                        textarea.dispatchEvent(new Event('input', { bubbles: true }));
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                        // AngularJS scope apply
                        const scope = angular.element(textarea).scope();
                        if (scope) {
                            scope.$apply();
                        }
                    }
                }
            """, answer)

            await asyncio.sleep(0.5)
            print(f"    ✓ 입력 완료 ({len(answer)}자)")

        print("  ✓ 모든 답변 입력 완료")

        # === 4단계: 저장 및 즐겨찾기 ===
        print("\n[4단계] 저장 및 즐겨찾기")

        # 저장 버튼 클릭 (자기소개서 페이지)
        save_button = await jasoseol_page.query_selector("div.btn-save")
        if save_button:
            await save_button.click()
            await asyncio.sleep(2)
            print("  ✓ 저장 완료")
        else:
            print("  ⚠️ 저장 버튼을 찾을 수 없음")

        # 공고 페이지로 이동 (즐겨찾기는 공고 페이지에 있음)
        await jasoseol_page.goto(f"https://jasoseol.com/recruit/{job_id}")
        await jasoseol_page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 즐겨찾기 버튼 클릭
        bookmark_button = await jasoseol_page.query_selector("button:has-text('공고 즐겨찾기')")
        if bookmark_button:
            await bookmark_button.click()
            await asyncio.sleep(1)
            print("  ✓ 공고 즐겨찾기 완료")
        else:
            print("  ⚠️ 즐겨찾기 버튼을 찾을 수 없음")

        # 성공으로 표시
        job_result['success'] = True

        print("\n" + "=" * 80)
        print(f"공고 처리 완료: {job_id}")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 공고 처리 중 오류 발생: {e}")
        job_result['error'] = str(e)
        job_result['success'] = False

    return job_result


async def main():
    # 브라우저 프로필
    jasoseol_profile = Path("output/browser_profile")
    chatgpt_profile = Path("output/chatgpt_profile")

    print("=" * 80)
    print("일일 자동화 시작")
    print("=" * 80)

    async with async_playwright() as p:
        # 자소설 브라우저 시작
        jasoseol_context = await p.chromium.launch_persistent_context(
            str(jasoseol_profile),
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )

        # ChatGPT 브라우저 시작
        chatgpt_context = await p.chromium.launch_persistent_context(
            str(chatgpt_profile),
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )

        jasoseol_page = jasoseol_context.pages[0] if jasoseol_context.pages else await jasoseol_context.new_page()
        chatgpt_page = chatgpt_context.pages[0] if chatgpt_context.pages else await chatgpt_context.new_page()

        # === 캘린더에서 당일 공고 목록 가져오기 ===
        print("\n[캘린더 확인]")
        await jasoseol_page.goto("https://jasoseol.com/calendar", timeout=60000)
        await jasoseol_page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(3)

        jobs = await get_today_job_list(jasoseol_page)

        if not jobs:
            print("\n처리할 공고가 없습니다. 브라우저를 종료합니다.")
            await jasoseol_context.close()
            await chatgpt_context.close()
            return

        print(f"\n  ✓ {len(jobs)}개 공고 발견 (즐겨찾기 안됨)")
        for idx, job in enumerate(jobs, 1):
            print(f"    {idx}. 공고 ID: {job['employment_id']}")

        # === ChatGPT 로그인 및 프로젝트 찾기 ===
        print("\n[ChatGPT 로그인]")
        await chatgpt_page.goto("https://chatgpt.com")
        await chatgpt_page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 이미 로그인되어 있는지 확인
        current_url = chatgpt_page.url
        if "chatgpt.com" in current_url and "/auth/" not in current_url:
            print("  ✓ 이미 로그인됨")
        else:
            print("  ⚠️ 로그인 필요 - 수동 로그인 후 진행")
            # 로그인 대기 (수동)
            await asyncio.sleep(30)

        # 프로젝트 찾기
        project_found = await find_teo_project(chatgpt_page)
        if not project_found:
            print("  ❌ 프로젝트를 찾을 수 없어 종료")
            await chatgpt_context.close()
            await jasoseol_context.close()
            return

        # === 각 공고 처리 ===
        job_results = []

        for idx, job in enumerate(jobs, 1):
            print(f"\n{'=' * 80}")
            print(f"진행 상황: {idx}/{len(jobs)}")
            print(f"{'=' * 80}")

            try:
                result = await process_single_job(
                    job['employment_id'],
                    jasoseol_context,
                    chatgpt_page
                )
                job_results.append(result)

            except Exception as e:
                print(f"\n❌ 공고 처리 중 오류 발생: {e}")
                # 오류 발생 시에도 결과에 추가
                job_results.append({
                    'job_id': job['employment_id'],
                    'success': False,
                    'company_name': '알 수 없음',
                    'job_title': '알 수 없음',
                    'error': str(e)
                })
                continue

        # === 최종 결과 및 알림 ===
        print("\n" + "=" * 80)
        print("일일 자동화 완료")
        print("=" * 80)
        
        successful_jobs = sum(1 for result in job_results if result.get('success', False))
        failed_jobs = len(job_results) - successful_jobs
        
        print(f"총 공고 수: {len(jobs)}")
        print(f"처리 성공: {successful_jobs}")
        print(f"처리 실패: {failed_jobs}")

        # 알림 전송
        print("\n📧 작업 완료 알림 전송 중...")
        notifier = NotificationManager()
        notification_sent = notifier.send_job_completion_notification(job_results)
        
        if notification_sent:
            print("✓ 알림 전송 완료")
        else:
            print("⚠️ 알림 전송 실패 (설정 확인 필요)")

        # 브라우저 종료
        print("\n브라우저를 종료합니다...")
        await jasoseol_context.close()
        await chatgpt_context.close()
        print("✓ 브라우저 종료 완료")


if __name__ == "__main__":
    asyncio.run(main())
