import streamlit as st
from utils.api_client import (
    fetch_support_programs,
    get_sample_data,
    is_deadline_soon,
    KEYWORDS_PAPER,
)
from utils.gemini_client import recommend_programs, chat_with_gemini

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="제지업 정부지원사업 탐색기",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
    .card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        border-left: 4px solid #1f77b4;
    }
    .card.urgent { border-left-color: #e74c3c; }
    .card-title { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; }
    .card-meta { font-size: 0.82rem; color: #666; margin-top: 4px; }
    .tag {
        display: inline-block;
        background: #e3f0ff;
        color: #1f77b4;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.75rem;
        margin-right: 4px;
    }
    .tag.urgent { background: #ffe3e3; color: #e74c3c; }
    .section-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1a1a2e;
        padding-bottom: 6px;
        border-bottom: 2px solid #1f77b4;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ── 데이터 로드 (세션 캐시) ──────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_programs(keywords: tuple) -> tuple:
    data, err = fetch_support_programs(list(keywords), page_size=30)
    return data, err


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/document.png", width=60)
    st.title("📄 제지업 지원사업")
    st.caption("공공데이터포털 + Gemini AI")
    st.divider()

    page = st.radio(
        "메뉴",
        ["🏠 대시보드", "🤖 AI 맞춤 추천", "💬 AI 챗봇"],
        label_visibility="collapsed",
    )
    st.divider()

    st.subheader("🔍 키워드 필터")
    KW_OPTIONS = ["스마트팩토리", "스마트공장", "제조업", "중견기업", "제지", "펄프",
                  "에너지", "에너지효율", "R&D", "설비투자", "환경", "디지털전환"]
    selected_kw = st.multiselect(
        "검색 키워드",
        options=KW_OPTIONS,
        default=[],
        placeholder="키워드 없이 전체 조회",
    )

    st.subheader("📍 지역 필터")
    selected_region = st.selectbox(
        "공장 소재지",
        options=["전체", "신탄진", "장항", "천안", "대전"],
    )

    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    pub_ok = bool(st.secrets.get("PUBLIC_DATA_API_KEY"))
    gem_ok = bool(st.secrets.get("GEMINI_API_KEY"))
    st.markdown(
        f"공공데이터: {'🟢 연결됨' if pub_ok else '🔴 미설정'}  \n"
        f"Gemini: {'🟢 연결됨' if gem_ok else '🔴 미설정'}"
    )


# ── 데이터 로드 ──────────────────────────────────────────────
programs, api_error = load_programs(tuple(selected_kw))

# 마감임박 필터
urgent = [p for p in programs if is_deadline_soon(p)]

# ============================================================
# 페이지 1: 대시보드
# ============================================================
if page == "🏠 대시보드":
    st.markdown("## 🏠 정부지원사업 대시보드")

    if api_error:
        st.error(api_error)

    # 제지산업 관련 포함 키워드 (하나라도 있으면 OK)
    INCLUDE_KW = ["제지", "펄프", "종이", "스마트팩토리", "스마트공장",
                  "에너지효율", "에너지절감", "신재생에너지", "환경설비",
                  "탄소중립", "온실가스", "폐수", "대기오염",
                  "제조업", "중견기업", "스마트제조", "디지털전환", "설비투자"]

    # 무관 업종 제외 키워드 (하나라도 있으면 제외)
    EXCLUDE_KW = ["농어업", "농업", "어업", "수산", "건설업", "건설사",
                  "농어업인", "농업인", "어업인", "축산", "임업",
                  "부동산", "의료", "관광", "문화", "예술", "교육기관",
                  "소상공인", "자영업", "청년창업"]

    def is_paper_related(p: dict) -> bool:
        text = (p["title"] + p["description"] + p["category"]).lower()
        if any(k in text for k in EXCLUDE_KW):
            return False
        return any(k in text for k in INCLUDE_KW)

    def apply_region(items: list, region: str) -> list:
        if region == "전체":
            return items
        return [p for p in items if region in (p["title"] + p["description"] + p.get("target", ""))]

    biz_all = [p for p in programs if is_paper_related(p)]
    biz_filtered = apply_region(biz_all, selected_region)

    # 요약 지표
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 공고", f"{len(biz_filtered)}건")
    col2.metric("🔴 마감임박", f"{len([p for p in biz_filtered if is_deadline_soon(p)])}건")
    col3.metric("분야 수", f"{len(set(p['category'] for p in biz_filtered if p['category']))}개")
    col4.metric("조회 키워드", f"{len(selected_kw)}개")

    st.divider()

    # 마감임박 알림
    urgent_filtered = [p for p in biz_filtered if is_deadline_soon(p)]
    if urgent_filtered:
        st.markdown('<div class="section-header">🔴 마감임박 사업</div>', unsafe_allow_html=True)
        for p in urgent_filtered:
            st.markdown(f"""
<div class="card urgent">
  <div class="card-title">{p['title']} <span class="tag urgent">마감임박</span></div>
  <div class="card-meta">
    📌 {p['agency']} &nbsp;|&nbsp; 🗓 마감: {p['end_date'] or '미정'} &nbsp;|&nbsp; 💰 {p['amount'] or '금액 미정'}
  </div>
  <div class="card-meta" style="margin-top:6px">{p['description'][:120]}...</div>
</div>
""", unsafe_allow_html=True)
        st.divider()

    if selected_region != "전체":
        st.info(f"📍 지역 필터: **{selected_region}** — 제목·내용에 지역명 포함된 항목만 표시")

    st.markdown(f'<div class="section-header">📋 지원사업목록 ({len(biz_filtered)}건)</div>', unsafe_allow_html=True)

    if not biz_filtered:
        st.info("해당 조건의 지원사업이 없습니다.")
    else:
        for p in biz_filtered:
            is_urgent = is_deadline_soon(p)
            with st.expander(f"{'🔴 ' if is_urgent else ''}**{p['title']}** — {p['agency']}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**담당기관:** {p['agency']}")
                    st.write(f"**분야:** {p['category'] or '미분류'}")
                with c2:
                    if p.get("start_date") or p.get("end_date"):
                        st.write(f"**신청기간:** {p['start_date'] or '?'} ~ {p['end_date'] or '?'}")
                    if p.get("detail_url"):
                        st.markdown(f"[🔗 공고 바로가기]({p['detail_url']})")
                if p.get("description"):
                    st.write(f"**내용:** {p['description']}")


# ============================================================
# 페이지 2: AI 맞춤 추천
# ============================================================
elif page == "🤖 AI 맞춤 추천":
    st.markdown("## 🤖 AI 맞춤 지원사업 추천")
    st.caption("회사 프로필을 입력하면 Gemini AI가 적합한 사업을 선별해 추천합니다.")

    with st.form("profile_form"):
        st.subheader("📋 기업 프로필 입력")
        col1, col2 = st.columns(2)
        with col1:
            company_name = st.text_input("기업명", placeholder="예: (주)한솔제지")
            company_size = st.selectbox(
                "기업 규모",
                ["중견기업", "중소기업", "대기업", "스타트업"],
            )
            employees = st.number_input("직원 수 (명)", min_value=1, max_value=99999, value=500)
        with col2:
            industry = st.text_input("업종", value="제지·펄프 제조업 (KSIC 1700)")
            location = st.text_input("소재지", placeholder="예: 경기도 안양시")
            concerns = st.text_area(
                "현재 고민/니즈",
                placeholder="예: 생산설비 자동화 검토 중, 에너지 비용 절감 필요",
                height=80,
            )
        interests = st.multiselect(
            "관심 분야 (복수 선택)",
            ["스마트팩토리", "에너지효율화", "R&D/기술개발", "설비투자", "환경/탄소중립",
             "수출지원", "인력개발", "디지털전환", "금융/보증"],
            default=["스마트팩토리", "에너지효율화"],
        )
        submitted = st.form_submit_button("🔍 AI 추천 받기", use_container_width=True)

    if submitted:
        profile = {
            "name": company_name,
            "size": company_size,
            "employees": employees,
            "industry": industry,
            "location": location,
            "concerns": concerns,
            "interests": interests,
        }
        with st.spinner("Gemini AI가 맞춤 사업을 분석 중입니다..."):
            result = recommend_programs(profile, programs)

        st.divider()
        st.subheader("📊 AI 추천 결과")
        st.markdown(result)

        st.divider()
        st.subheader("📋 전체 공고 목록 (참고)")
        for i, p in enumerate(programs, 1):
            st.markdown(f"**{i}. {p['title']}** — {p['agency']} | {p['amount'] or '금액 미정'}")


# ============================================================
# 페이지 3: AI 챗봇
# ============================================================
elif page == "💬 AI 챗봇":
    st.markdown("## 💬 AI 지원사업 챗봇")
    st.caption("제지업 정부지원사업에 대해 자유롭게 질문하세요.")

    # 대화 히스토리 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 빠른 질문 버튼
    st.subheader("💡 빠른 질문")
    q_cols = st.columns(3)
    quick_questions = [
        "제지공장에 맞는 스마트팩토리 지원사업이 있나요?",
        "중견기업이 신청 가능한 사업은 무엇인가요?",
        "에너지 절감 관련 지원을 받을 수 있나요?",
        "R&D 자금 지원 조건이 어떻게 되나요?",
        "마감이 임박한 사업이 있나요?",
        "신청 절차를 간단히 설명해주세요.",
    ]
    for i, q in enumerate(quick_questions):
        col = q_cols[i % 3]
        if col.button(q, key=f"quick_{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.spinner("답변 생성 중..."):
                answer = chat_with_gemini(st.session_state.chat_history, q, programs)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

    st.divider()

    # 대화 출력
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.info("💬 위의 빠른 질문을 클릭하거나 아래에 직접 질문을 입력하세요.")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 입력창
    if user_input := st.chat_input("질문을 입력하세요... (예: 제지업 탄소중립 지원 있나요?)"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                answer = chat_with_gemini(
                    st.session_state.chat_history[:-1], user_input, programs
                )
            st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    # 대화 초기화
    if st.session_state.chat_history:
        if st.button("🗑 대화 초기화", type="secondary"):
            st.session_state.chat_history = []
            st.rerun()
