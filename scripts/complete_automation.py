#!/usr/bin/env python3
"""
완전 자동화 스크립트
1. 자소설: 정보 추출
2. ChatGPT: 답변 생성
3. 자소설: 답변 입력 및 저장
4. 즐겨찾기 체크
5. 다음 공고 반복
"""
import asyncio
import yaml
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# .env 로드
load_dotenv()


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

    for position_div in positions:
        spans = await position_div.query_selector_all("span")
        if len(spans) < 2:
            continue

        career_type = await spans[0].inner_text()
        position_name = await spans[1].inner_text()

        if career_type not in allowed_career_types:
            continue

        matched = False
        matched_keyword = None
        matched_priority = None

        for priority_group in keywords_by_priority:
            for keyword in priority_group['keywords']:
                if keyword.lower() in position_name.lower():
                    matched = True
                    matched_keyword = keyword
                    matched_priority = priority_group['priority']
                    break
            if matched:
                break

        if matched:
            matched_positions.append({
                "career_type": career_type,
                "position_name": position_name,
                "matched_keyword": matched_keyword,
                "priority": matched_priority
            })

    priority_order = {'priority_1': 1, 'priority_2': 2, 'priority_3': 3}
    matched_positions.sort(key=lambda x: priority_order.get(x['priority'], 999))

    return matched_positions


async def extract_questions_from_jasoseol(page):
    """자소설에서 질문 추출"""
    questions = []
    max_questions = 20

    for i in range(1, max_questions + 1):
        clicked = False

        try:
            nav_buttons = await page.query_selector_all("ul.nav-pills li")
            for li in nav_buttons:
                text = await li.inner_text()
                if text.strip() == str(i):
                    await li.click()
                    await asyncio.sleep(1)
                    clicked = True
                    break
        except Exception as e:
            print(f"  버튼 클릭 실패: {e}")

        if not clicked:
            break

        # 활성 탭의 textarea 읽기
        active_tab = await page.query_selector(".tab-pane.active")
        if not active_tab:
            break

        question_textarea = await active_tab.query_selector("textarea.qna-question")
        if question_textarea:
            question_text = await question_textarea.evaluate("el => el.value")
        else:
            question_text = ""

        count_indicator = await active_tab.query_selector("span.count-indicator")
        if count_indicator:
            char_info = await count_indicator.evaluate("""el => {
                const currentSpan = el.querySelector('span.current');
                const totalSpan = el.querySelector('span.total');
                return {
                    current: currentSpan ? currentSpan.innerText : '0',
                    total: totalSpan ? totalSpan.innerText : '제한 없음'
                };
            }""")
            char_limit = char_info['total']
        else:
            char_limit = "제한 없음"

        if question_text:
            questions.append({
                'number': i,
                'text': question_text,
                'char_limit': char_limit
            })

    return questions


async def login_chatgpt(page):
    """ChatGPT 자동 로그인"""
    print("\n[ChatGPT 로그인]")

    await page.goto("https://chatgpt.com")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)

    # 로그인 버튼 확인 (우측 상단)
    login_button = await page.query_selector("button:has-text('로그인')")

    if login_button and await login_button.is_visible():
        print("  로그인 시작...")

        # 1. 로그인 버튼 클릭 → 모달 팝업
        await login_button.click()
        await asyncio.sleep(2)

        # 2. 이메일 입력
        email = os.getenv("CHATGPT_EMAIL")
        password = os.getenv("CHATGPT_PASSWORD")

        email_input = await page.query_selector("input[type='email']")
        if email_input:
            print(f"  이메일 입력: {email}")
            await email_input.fill(email)
            await asyncio.sleep(1)

            # "계속" 버튼 클릭
            continue_button = await page.query_selector("button:has-text('계속')")
            if continue_button:
                await continue_button.click()
                await asyncio.sleep(3)

        # 3. 비밀번호 입력 (새 페이지로 이동됨)
        password_input = await page.query_selector("input[type='password']")
        if password_input:
            print("  비밀번호 입력")
            await password_input.fill(password)
            await asyncio.sleep(1)

            # "계속" 버튼 클릭
            continue_button2 = await page.query_selector("button:has-text('계속')")
            if continue_button2:
                await continue_button2.click()
                await asyncio.sleep(5)

        print("  ✓ 로그인 완료")
    else:
        print("  ✓ 이미 로그인됨")


async def find_teo_project(page):
    """'테오 입사지원' 프로젝트 찾기"""
    print("\n['테오 입사지원' 프로젝트 찾기]")

    await asyncio.sleep(2)

    # 먼저 "더보기" 버튼이 있는지 확인하고 클릭
    more_button = await page.query_selector("button:has-text('더보기'), button:has-text('Show more')")
    if more_button and await more_button.is_visible():
        print("  '더보기' 버튼 클릭")
        await more_button.click()
        await asyncio.sleep(1)

    # 모든 링크에서 '테오 입사지원' 찾기
    links = await page.query_selector_all("a")

    for link in links:
        try:
            text = await link.inner_text()
            if "테오" in text and "입사" in text:
                href = await link.get_attribute("href")
                print(f"  ✓ 프로젝트 발견: {text.strip()}")

                # 프로젝트 페이지로 이동
                full_url = f"https://chatgpt.com{href}" if not href.startswith("http") else href
                await page.goto(full_url)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)

                return True
        except:
            continue

    print("  ❌ 프로젝트를 찾을 수 없습니다")
    return False


async def wait_for_response_complete(page, timeout=120):
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
    await asyncio.sleep(1)

    # 전송 버튼 찾아서 클릭 (Enter보다 확실함)
    # 여러 셀렉터 시도 (한국어/영어 버전 대응)
    send_button_selectors = [
        "#composer-submit-button",
        "button[data-testid='send-button']",
        "button[aria-label='프롬프트 보내기']",
        "button[aria-label='Send']",
        "button.composer-submit-button"
    ]

    send_button = None
    for selector in send_button_selectors:
        btn = await page.query_selector(selector)
        if btn:
            try:
                if await btn.is_visible() and await btn.is_enabled():
                    send_button = btn
                    break
            except:
                continue

    if send_button:
        await send_button.click()
        print("  ✓ 메시지 전송 완료 (전송 버튼 클릭)")
    else:
        # 전송 버튼 없으면 Enter 시도
        await input_box.press("Enter")
        print("  ✓ 메시지 전송 완료 (Enter)")

    await asyncio.sleep(1)

    # 응답 완료 대기
    success = await wait_for_response_complete(page, timeout=120)

    if not success:
        print("  ❌ 응답 대기 실패")
        return None

    print("  ✓ AI 응답 완료")

    # 응답 추출
    try:
        response = await page.evaluate("""
            () => {
                const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (messages.length === 0) return null;
                const lastMessage = messages[messages.length - 1];
                return lastMessage.innerText || lastMessage.textContent;
            }
        """)
        return response
    except Exception as e:
        print(f"  ❌ 응답 추출 실패: {e}")
        return None


async def main():
    job_id = "100714"  # TODO: 커맨드라인 인자로 받기

    # 브라우저 프로필
    jasoseol_profile = Path("output/browser_profile")
    chatgpt_profile = Path("output/chatgpt_profile")

    print("=" * 80)
    print("완전 자동화 시작")
    print("=" * 80)

    async with async_playwright() as p:
        # === 1단계: 자소설에서 정보 추출 ===
        print("\n[1단계] 자소설 - 정보 추출")

        jasoseol_context = await p.chromium.launch_persistent_context(
            str(jasoseol_profile),
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        jasoseol_page = jasoseol_context.pages[0] if jasoseol_context.pages else await jasoseol_context.new_page()

        # 공고 페이지 접근
        await jasoseol_page.goto(f"https://jasoseol.com/recruit/{job_id}")
        await jasoseol_page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 회사명/공고명 추출
        page_title = await jasoseol_page.title()
        company_name = page_title.split("채용공고")[0].strip() if "채용공고" in page_title else ""

        h1_element = await jasoseol_page.query_selector("h1")
        job_title = await h1_element.inner_text() if h1_element else ""

        print(f"  회사명: {company_name}")
        print(f"  공고명: {job_title}")

        # 키워드 매칭
        await jasoseol_page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        matched = await find_matching_positions(jasoseol_page)
        if not matched:
            print("  ❌ 매칭된 직무 없음")
            await jasoseol_context.close()
            return

        top_position = matched[0]
        print(f"  직무: {top_position['position_name']}")

        # 자기소개서 쓰기 버튼 클릭
        write_buttons = await jasoseol_page.query_selector_all("button:has-text('자기소개서 쓰기')")
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

        chatgpt_context = await p.chromium.launch_persistent_context(
            str(chatgpt_profile),
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        chatgpt_page = chatgpt_context.pages[0] if chatgpt_context.pages else await chatgpt_context.new_page()

        # ChatGPT 로그인
        await login_chatgpt(chatgpt_page)

        # '테오 입사지원' 프로젝트 찾기
        project_found = await find_teo_project(chatgpt_page)
        if not project_found:
            print("  ❌ 프로젝트를 찾을 수 없어 종료")
            await chatgpt_context.close()
            await jasoseol_context.close()
            return

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
                print(f"  [문항 {question_num}] 답변 없음 - 건너뜀")
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
            if active_tab:
                answer_textarea = await active_tab.query_selector("textarea.answer")
                if answer_textarea:
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

                    # 입력된 글자수 확인
                    current_length = len(answer)
                    print(f"    ✓ 입력 완료 ({current_length}자)")
                else:
                    print(f"    ✗ 답변 입력창을 찾을 수 없음")
            else:
                print(f"    ✗ 활성 탭을 찾을 수 없음")

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

        # === 5단계: 다음 공고 (TODO - 현재는 단일 공고만 처리) ===

        print("\n" + "=" * 80)
        print("자동화 완료!")
        print("=" * 80)

        print("\n브라우저를 확인하세요. 종료하려면 Ctrl+C")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n종료합니다...")
        finally:
            await chatgpt_context.close()
            await jasoseol_context.close()


if __name__ == "__main__":
    asyncio.run(main())
