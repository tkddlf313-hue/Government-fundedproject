import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash"

_clients: list = []
_current_index: int = 0


def get_clients() -> list:
    """secrets에서 키 목록을 읽어 클라이언트 리스트 반환"""
    global _clients
    keys = []
    for i in range(1, 11):
        key = st.secrets.get(f"GEMINI_API_KEY_{i}", "")
        if key:
            keys.append(key)
    if not keys:
        single = st.secrets.get("GEMINI_API_KEY", "")
        if single:
            keys.append(single)

    if keys:
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


def summarize_program(program: dict) -> str:
    prompt = (
        f"다음 정부지원사업을 제지·제조업 담당자 관점에서 3줄로 요약해줘.\n"
        f"사업명: {program['title']}\n기관: {program['agency']}\n"
        f"분야: {program['category']}\n기간: {program.get('start_date','')} ~ {program.get('end_date','')}\n"
        f"내용: {program.get('description','')}\n\n"
        f"형식 — 1. 지원내용 2. 신청대상 3. 핵심포인트 (각 줄 30자 이내, 한국어)"
    )
    result, err = _call_with_retry(
        lambda c: c.models.generate_content(model=MODEL, contents=prompt).text
    )
    return result if result else err


def recommend_programs(company_profile: dict, programs: list[dict]) -> str:
    programs_text = "\n".join([
        f"[{i+1}] {p['title']}|{p['agency']}|{p['category']}|{p['amount']}|{p['description'][:50]}"
        for i, p in enumerate(programs[:10])  # 최대 10개만 전송
    ])

    prompt = (
        f"제지·펄프 제조 {company_profile.get('size','')} 기업 "
        f"({company_profile.get('employees','')}명, {company_profile.get('location','')}), "
        f"관심:{','.join(company_profile.get('interests',[]))}, "
        f"고민:{company_profile.get('concerns','')}\n\n"
        f"지원사업:\n{programs_text}\n\n"
        f"TOP3 추천+적합이유2줄+준비사항 간략히+전략한줄요약. 한국어로."
    )

    result, err = _call_with_retry(
        lambda c: c.models.generate_content(model=MODEL, contents=prompt).text
    )
    return result if result else err


def chat_with_gemini(history: list[dict], user_message: str, programs: list[dict]) -> str:
    programs_context = "\n".join([
        f"- {p['title']} ({p['agency']}, {p['category']}, 마감: {p['end_date'] or '미정'})"
        for p in programs[:8]  # 최대 8개만 전송
    ])

    system_instruction = (
        f"제지·펄프 제조업 정부지원사업 컨설턴트. 모르면 모른다고 답변.\n"
        f"현재 사업:{programs_context}\n간결하고 실무적으로 한국어 답변."
    )

    contents = []
    for msg in history[-5:]:  # 최근 5개만 유지
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
