"""
완전 자동화 스크립트

1. 로그인 (프로필 사용)
2. 공고 페이지 접근
3. 키워드 매칭으로 직무 찾기
4. "자기소개서 쓰기" 버튼 클릭
5. 모달 "아니오" 클릭 (자동 대기)
6. 자소서 질문 3개 추출
7. (향후) ChatGPT로 답변 생성
8. (향후) 답변 입력 및 저장
"""

import asyncio
import yaml
import json
from pathlib import Path
from playwright.async_api import async_playwright


def load_keywords():
    """키워드 설정 로드"""
    config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


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


async def extract_questions(page):
    """자소서 질문 추출 (동적으로 개수 감지 + 글자수 제한 추출)"""
    questions = []
    max_questions = 20  # 최대 20개까지 확인

    for i in range(1, max_questions + 1):
        # 왼쪽 사이드바에서 숫자 버튼 클릭 (nav-pills 영역 내의 숫자)
        clicked = False

        try:
            # nav-pills 내에서 숫자 버튼 찾기
            nav_buttons = await page.query_selector_all("ul.nav-pills li")
            for li in nav_buttons:
                text = await li.inner_text()
                if text.strip() == str(i):
                    await li.click()
                    clicked = True
                    # 클릭 후 탭이 활성화될 때까지 대기
                    await asyncio.sleep(1)
                    break
        except Exception as e:
            print(f"  버튼 클릭 실패: {e}")

        if not clicked:
            # 더 이상 질문이 없음
            break

        # 활성화된 탭(.active)의 textarea 읽기
        # .tab-pane.active 내의 textarea.qna-question을 찾음
        active_tab = await page.query_selector(".tab-pane.active")
        if not active_tab:
            print(f"  활성 탭을 찾을 수 없습니다")
            break

        # 활성 탭 내의 질문 textarea 찾기
        question_textarea = await active_tab.query_selector("textarea.qna-question")
        if question_textarea:
            # AngularJS 바인딩된 값을 JavaScript로 직접 읽기
            question_text = await question_textarea.evaluate("el => el.value")
        else:
            question_text = ""

        # 활성 탭 내의 글자수 제한 추출 (span.count-indicator)
        count_indicator = await active_tab.query_selector("span.count-indicator")
        if count_indicator:
            # current와 total 값 추출
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
            print(f"✓ 질문 {i} 추출: {question_text[:50]}... (제한: {char_limit}자)")

    return questions


async def full_automation(job_id):
    """완전 자동화 메인 함수"""

    profile_dir = Path(__file__).parent.parent / "output" / "browser_profile"

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={'width': 1920, 'height': 1080},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ],
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.pages[0] if context.pages else await context.new_page()
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        print("=" * 80)
        print(f"완전 자동화 테스트 - 공고 ID: {job_id}")
        print("=" * 80)
        print()

        # 1. 공고 페이지 접근
        print(f"[1단계] 공고 페이지 접근: https://jasoseol.com/recruit/{job_id}")
        await page.goto(f"https://jasoseol.com/recruit/{job_id}")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # 로그인 확인
        login_button = await page.query_selector("button:has-text('회원가입/로그인')")
        if login_button:
            print("⚠️  로그인 필요!")
            print("브라우저에서 로그인 후 60초 대기...")
            await asyncio.sleep(60)
        else:
            print("✓ 로그인 확인됨")

        # 회사명과 공고명 추출
        print("\n[1-1단계] 회사명/공고명 추출")

        # 페이지 제목에서 추출: "네이버파이낸셜(네이버페이) 채용공고 2025 네이버페이 신입채용..."
        page_title = await page.title()

        # 회사명: "채용공고" 앞부분
        company_name = ""
        if "채용공고" in page_title:
            company_name = page_title.split("채용공고")[0].strip()

        # 공고명: h1 태그
        job_title = ""
        h1_element = await page.query_selector("h1")
        if h1_element:
            job_title = await h1_element.inner_text()
            job_title = job_title.strip()

        print(f"  회사명: {company_name}")
        print(f"  공고명: {job_title}")

        # 스크롤
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        # 2. 키워드 매칭
        print("\n[2단계] 키워드 매칭")
        matched = await find_matching_positions(page)

        if not matched:
            print("❌ 매칭된 직무 없음")
            await asyncio.sleep(60)
            await context.close()
            return

        print(f"✓ {len(matched)}개 직무 매칭")
        for pos in matched:
            print(f"  - [{pos['career_type']}] {pos['position_name']} ({pos['priority']})")

        top_position = matched[0]
        print(f"\n[3단계] 최우선 직무: {top_position['position_name']}")

        # 3. "자기소개서 쓰기" 버튼 클릭 (새 탭 열림)
        print("\n[4단계] '자기소개서 쓰기' 버튼 클릭")

        # wait_for_selector로 버튼이 나타날 때까지 대기
        try:
            await page.wait_for_selector("button:has-text('자기소개서 쓰기'), a:has-text('자기소개서 쓰기')", timeout=10000)
            write_buttons = await page.query_selector_all("button:has-text('자기소개서 쓰기'), a:has-text('자기소개서 쓰기')")

            if write_buttons:
                print(f"→ '자기소개서 쓰기' 버튼 {len(write_buttons)}개 발견")

                # 새 탭이 열리는 것을 대기
                async with context.expect_page() as new_page_info:
                    await write_buttons[0].click()

                # 새 탭으로 전환
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("networkidle")
                page = new_page  # 이제 page는 새 탭을 가리킴
                print(f"✓ 버튼 클릭 완료 - 새 탭 열림: {page.url}")
            else:
                print("❌ 버튼 없음")
                await asyncio.sleep(60)
                await context.close()
                return
        except Exception as e:
            print(f"❌ 버튼 클릭 실패: {e}")
            await asyncio.sleep(60)
            await context.close()
            return

        # 4. 모달 처리 - "아니오" 클릭
        print("\n[5단계] 모달 처리")
        try:
            # 모달이 나타날 때까지 대기 (최대 5초)
            await page.wait_for_selector(".modal-footer button, button:has-text('아니오')", timeout=5000)

            # 여러 셀렉터 시도
            selectors = [
                ".modal-footer button.btn-default",
                "button:has-text('아니오')",
                ".modal-footer .btn:first-child"
            ]

            clicked = False
            for selector in selectors:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print(f"✓ '아니오' 버튼 클릭 완료 (셀렉터: {selector})")
                        clicked = True
                        await asyncio.sleep(2)
                        break
                except:
                    continue

            if not clicked:
                print("→ 모달 없음 또는 이미 닫힘")

        except Exception as e:
            print(f"→ 모달 타임아웃 (모달이 없을 수 있음)")

        # 5. URL 변경 확인 (자소서 작성 페이지로 이동했는지)
        await asyncio.sleep(3)
        current_url = page.url
        print(f"\n[6단계] 현재 URL: {current_url}")

        if "/resume/" not in current_url:
            print("❌ 자소서 작성 페이지로 이동하지 못했습니다.")
            print("브라우저를 확인하세요 (60초 후 종료)")
            await asyncio.sleep(60)
            await context.close()
            return

        print("✓ 자소서 작성 페이지 접근 성공!")

        # 6. 질문 추출
        print("\n[7단계] 자소서 질문 추출")
        questions = await extract_questions(page)

        if questions:
            print(f"\n✓ 총 {len(questions)}개 질문 추출 완료:")
            for q in questions:
                print(f"\n질문 {q['number']}:")
                print(f"  {q['text'][:100]}...")

            # 질문 데이터를 JSON 파일로 저장
            output_dir = Path(__file__).parent.parent / "output"
            output_dir.mkdir(exist_ok=True)

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

            print(f"\n✓ 질문 데이터 저장: {json_path}")
        else:
            print("⚠️  질문을 찾지 못했습니다.")

        print("\n" + "=" * 80)
        print("자동화 테스트 완료!")
        print("=" * 80)
        print("\n브라우저를 확인하세요.")
        print("종료하려면 Ctrl+C를 누르세요.")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n종료합니다...")
        finally:
            await context.close()


# 실행
if __name__ == "__main__":
    import sys

    # 커맨드라인 인자로 job_id 받기
    job_id = sys.argv[1] if len(sys.argv) > 1 else "100657"

    asyncio.run(full_automation(job_id))
