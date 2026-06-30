import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"

_clients: list = []
_current_index: int = 0


def get_clients() -> list:
    """secrets에서 키 목록을 읽어 클라이언트 리스트 반환"""
    global _clients
    if _clients:
        return _clients

    keys = []
    # GEMINI_API_KEY_1, _2, _3 ... 순서로 읽기
    for i in range(1, 11):
        key = st.secrets.get(f"GEMINI_API_KEY_{i}", "")
        if key:
            keys.append(key)
    # 단일 키 폴백
    if not keys:
        single = st.secrets.get("GEMINI_API_KEY", "")
        if single:
            keys.append(single)

    _clients = [genai.Client(api_key=k) for k in keys]
    return _clients


def get_client():
    """429/503 발생 시 다음 키로 자동 순환"""
    global _current_index
    clients = get_clients()
    if not clients:
        return None
    client = clients[_current_index % len(clients)]
    return client


def _rotate():
    global _current_index, _clients
    _current_index = (_current_index + 1) % max(len(_clients), 1)


def _call_with_retry(fn, max_retries: int = None):
    """429/503이면 다음 키로 교체 후 재시도"""
    clients = get_clients()
    max_retries = max_retries or max(len(clients), 1)
    last_err = None
    for _ in range(max_retries):
        client = get_client()
        if client is None:
            return None, "⚠️ Gemini API 키가 설정되지 않았습니다. Streamlit Secrets에 GEMINI_API_KEY_1 을 추가해주세요."
        try:
            return fn(client), None
        except Exception as e:
            msg = str(e)
            last_err = msg
            if "429" in msg or "503" in msg:
                _rotate()
            else:
                break
    return None, f"❌ Gemini 호출 오류: {last_err}"


def recommend_programs(company_profile: dict, programs: list[dict]) -> str:
    programs_text = "\n".join([
        f"[{i+1}] {p['title']} | 기관: {p['agency']} | 분야: {p['category']} | "
        f"지원금: {p['amount']} | 대상: {p['target']} | 내용: {p['description'][:100]}"
        for i, p in enumerate(programs)
    ])

    prompt = f"""당신은 정부 지원사업 전문 컨설턴트입니다. 아래 기업 프로필을 분석하고 지원사업 목록에서 가장 적합한 사업을 추천해주세요.

## 기업 프로필
- 기업명: {company_profile.get('name', '미입력')}
- 기업 규모: {company_profile.get('size', '미입력')}
- 업종: {company_profile.get('industry', '제지·펄프 제조업')}
- 직원 수: {company_profile.get('employees', '미입력')}명
- 관심 분야: {', '.join(company_profile.get('interests', []))}
- 소재지: {company_profile.get('location', '미입력')}
- 현재 고민: {company_profile.get('concerns', '미입력')}

## 지원사업 목록
{programs_text}

## 요청사항
1. 위 기업에 **가장 적합한 TOP 3 사업**을 선정하고 번호를 명시하세요.
2. 각 사업별로:
   - 적합 이유 (2~3줄)
   - 준비해야 할 서류나 조건 (간략히)
   - 주의사항 (있다면)
3. 마지막에 전체적인 지원 전략 한 줄 요약

응답은 명확하고 실무적으로 작성해주세요."""

    result, err = _call_with_retry(
        lambda c: c.models.generate_content(model=MODEL, contents=prompt).text
    )
    return result if result else err


def chat_with_gemini(history: list[dict], user_message: str, programs: list[dict]) -> str:
    programs_context = "\n".join([
        f"- {p['title']} ({p['agency']}, {p['category']}, 마감: {p['end_date'] or '미정'})"
        for p in programs[:15]
    ])

    system_instruction = f"""당신은 제지·펄프 제조업체를 전담하는 정부 지원사업 컨설턴트입니다.
현재 조회된 지원사업 목록을 기반으로 답변하되, 모르는 내용은 솔직히 모른다고 하세요.

현재 조회된 지원사업:
{programs_context}

답변 스타일: 친절하고 실무적으로, 핵심만 간결하게, 필요시 신청 절차·담당 기관 안내, 한국어로 답변"""

    contents = []
    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    def call(c):
        return c.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        ).text

    result, err = _call_with_retry(call)
    return result if result else err
