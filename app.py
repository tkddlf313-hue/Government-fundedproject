import io
import streamlit as st
from datetime import datetime
from utils.api_client import fetch_support_programs, is_deadline_soon, KEYWORDS_PAPER
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
    .card { background:#f8f9fa; border-radius:10px; padding:16px 20px; margin-bottom:12px; border-left:4px solid #1f77b4; }
    .card.urgent { border-left-color:#e74c3c; }
    .card-title { font-size:1.05rem; font-weight:700; color:#1a1a2e; }
    .card-meta { font-size:0.82rem; color:#666; margin-top:4px; }
    .tag { display:inline-block; background:#e3f0ff; color:#1f77b4; border-radius:12px; padding:2px 10px; font-size:0.75rem; margin-right:4px; }
    .tag.urgent { background:#ffe3e3; color:#e74c3c; }
    .section-header { font-size:1.3rem; font-weight:700; color:#1a1a2e; padding-bottom:6px; border-bottom:2px solid #1f77b4; margin-bottom:16px; }
</style>
""", unsafe_allow_html=True)

# ── 세션 초기화 ──────────────────────────────────────────────
if "favorites" not in st.session_state:
    st.session_state.favorites = set()

# ── 데이터 로드 ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_programs(keywords: tuple) -> tuple:
    return fetch_support_programs(list(keywords), page_size=500)


# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/document.png", width=60)
    st.title("📄 제지업 지원사업")
    st.caption("기업마당 + Gemini AI")
    st.divider()

    page = st.radio(
        "메뉴",
        ["🏠 대시보드", "⭐ 즐겨찾기", "🤖 AI 맞춤 추천", "💬 AI 챗봇"],
        label_visibility="collapsed",
    )
    st.divider()

    st.subheader("🔍 키워드 필터")
    KW_OPTIONS = ["스마트팩토리", "스마트공장", "제조", "공장", "중견기업",
                  "에너지", "R&D", "설비", "투자", "환경",
                  "로봇", "AX", "DX", "AI", "기술"]
    selected_kw = st.multiselect(
        "검색 키워드",
        options=KW_OPTIONS,
        default=[],
        placeholder="키워드 없이 전체 조회",
        accept_new_options=True,
    )

    st.subheader("📍 지역 필터")
    selected_region = st.selectbox(
        "공장 소재지",
        options=["전체", "신탄진", "장항", "천안", "대전"],
    )

    st.subheader("📊 정렬")
    sort_option = st.radio(
        "정렬 기준",
        ["최신등록순", "마감임박순"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    biz_ok = bool(st.secrets.get("BIZINFO_API_KEY"))
    gem_ok = bool(st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY_1"))
    st.markdown(
        f"기업마당: {'🟢 연결됨' if biz_ok else '🔴 미설정'}  \n"
        f"Gemini: {'🟢 연결됨' if gem_ok else '🔴 미설정'}  \n"
        f"즐겨찾기: ⭐ {len(st.session_state.favorites)}건"
    )


# ── 공통 필터 함수 ───────────────────────────────────────────
EXCLUDE_KW = ["농어업", "농업", "어업", "수산", "건설업", "건설사",
              "농어업인", "농업인", "어업인", "축산", "임업",
              "부동산", "의료", "관광", "문화", "예술", "교육기관",
              "소상공인", "자영업", "청년창업"]

REGION_KEYWORDS = {
    "천안": ["천안", "충남", "충청남도"],
    "장항": ["장항", "서천", "충남", "충청남도"],
    "대전": ["대전", "충청"],
    "신탄진": ["신탄진", "대덕", "대전"],
}

today = datetime.now().strftime("%Y%m%d")

def is_paper_related(p):
    text = (p["title"] + p["description"] + p["category"]).lower()
    return not any(k in text for k in EXCLUDE_KW)

def is_expired(p):
    end = p.get("end_date", "")
    return bool(end) and end < today

# 지역명 — 하나라도 포함되면 지자체 공고로 판단
ALL_REGION_KW = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "충청", "전북", "전남", "경북", "경남", "제주",
    "경상북도", "경상남도", "전라북도", "전라남도", "충청북도", "충청남도", "강원도",
    "수원", "성남", "안양", "청주", "천안", "아산", "서천", "공주", "논산",
    "전주", "광양", "포항", "구미", "창원", "진주", "제천", "춘천",
    "도청", "시청", "군청", "구청", "광역시", "특별시",
]

def is_national_agency(p) -> bool:
    raw = p.get("raw", {})
    agency_text = " ".join([
        p["agency"],
        raw.get("jrsdInsttNm", ""),
        raw.get("excInsttNm", ""),
    ])
    return not any(k in agency_text for k in ALL_REGION_KW)

def apply_region(items, region):
    if region == "전체":
        return items
    search_kw = REGION_KEYWORDS.get(region, [region])
    result = []
    for p in items:
        raw = p.get("raw", {})
        agency_text = " ".join([p["title"], p["agency"],
                                 raw.get("jrsdInsttNm", ""), raw.get("excInsttNm", "")])
        is_local_match = any(k in agency_text for k in search_kw)
        if is_local_match or is_national_agency(p):
            result.append(p)
    return result

def sort_programs(items, option):
    if option == "마감임박순":
        def sort_key(p):
            e = p.get("end_date", "")
            return e if e else "99999999"
        return sorted(items, key=sort_key)
    else:  # 최신등록순
        def sort_key(p):
            raw = p.get("raw", {})
            return raw.get("creatPnttm", raw.get("updtPnttm", ""))
        return sorted(items, key=sort_key, reverse=True)

def make_excel(items):
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "지원사업목록"
        headers = ["사업명", "주관기관", "분야", "신청시작일", "신청마감일", "대상", "공고URL"]
        ws.append(headers)
        for p in items:
            ws.append([
                p["title"], p["agency"], p["category"],
                p.get("start_date", ""), p.get("end_date", ""),
                p.get("target", ""), p.get("detail_url", ""),
            ])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    except ImportError:
        return None

def render_program_card(p, idx, show_fav=True):
    """공고 expander 카드 렌더링"""
    pid = p["id"]
    is_urgent = is_deadline_soon(p)
    expired = is_expired(p)
    fav = pid in st.session_state.favorites
    prefix = "🔴 " if is_urgent else ("⚫ " if expired else "")
    fav_icon = "⭐" if fav else "☆"

    with st.expander(f"{prefix}**{p['title']}** — {p['agency']}"):
        c1, c2 = st.columns([3, 2])
        with c1:
            st.write(f"**담당기관:** {p['agency']}")
            st.write(f"**분야:** {p['category'] or '미분류'}")
            if p.get("target"):
                st.write(f"**지원대상:** {p['target']}")
        with c2:
            if p.get("start_date") or p.get("end_date"):
                st.write(f"**신청기간:** {p['start_date'] or '?'} ~ {p['end_date'] or '?'}")
            if expired:
                st.caption("⚫ 마감된 공고입니다")
            if p.get("detail_url"):
                st.markdown(f"[🔗 공고 바로가기]({p['detail_url']})")
        if p.get("description"):
            st.write(f"**내용:** {p['description']}")

        if show_fav:
            if st.button(f"{fav_icon} {'즐겨찾기 해제' if fav else '즐겨찾기 추가'}", key=f"fav_{idx}_{pid}"):
                if fav:
                    st.session_state.favorites.discard(pid)
                else:
                    st.session_state.favorites.add(pid)
                    if "fav_data" not in st.session_state:
                        st.session_state.fav_data = {}
                    st.session_state.fav_data[pid] = p
                st.rerun()


# ── 데이터 로드 ──────────────────────────────────────────────
programs, api_error = load_programs(tuple(selected_kw))


# ============================================================
# 페이지 1: 대시보드
# ============================================================
if page == "🏠 대시보드":
    st.markdown("## 🏠 정부지원사업 대시보드")

    if api_error:
        st.error(api_error)

    biz_all = [p for p in programs if is_paper_related(p)]
    biz_region = apply_region(biz_all, selected_region)
    biz_filtered = sort_programs(biz_region, sort_option)

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
  <div class="card-meta">📌 {p['agency']} &nbsp;|&nbsp; 🗓 마감: {p['end_date'] or '미정'}</div>
  <div class="card-meta" style="margin-top:6px">{p['description'][:120]}...</div>
</div>
""", unsafe_allow_html=True)
        st.divider()

    if selected_region != "전체":
        st.info(f"📍 지역 필터: **{selected_region}** — 주관·집행기관에 지역명 포함된 항목만 표시")

    # 헤더 + 엑셀 다운로드 버튼
    hcol1, hcol2 = st.columns([4, 1])
    with hcol1:
        st.markdown(f'<div class="section-header">📋 지원사업목록 ({len(biz_filtered)}건) — {sort_option}</div>', unsafe_allow_html=True)
    with hcol2:
        excel_buf = make_excel(biz_filtered)
        if excel_buf:
            st.download_button(
                "📥 엑셀 다운로드",
                data=excel_buf,
                file_name=f"지원사업목록_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    if not biz_filtered:
        st.info("해당 조건의 지원사업이 없습니다.")
    else:
        for i, p in enumerate(biz_filtered):
            render_program_card(p, i)


# ============================================================
# 페이지 2: 즐겨찾기
# ============================================================
elif page == "⭐ 즐겨찾기":
    st.markdown("## ⭐ 즐겨찾기")

    fav_data = st.session_state.get("fav_data", {})
    fav_ids = st.session_state.favorites
    fav_list = [fav_data[pid] for pid in fav_ids if pid in fav_data]

    if not fav_list:
        st.info("즐겨찾기한 공고가 없습니다. 대시보드에서 ☆ 버튼을 눌러 추가하세요.")
    else:
        hcol1, hcol2 = st.columns([4, 1])
        with hcol1:
            st.caption(f"총 {len(fav_list)}건 저장됨")
        with hcol2:
            excel_buf = make_excel(fav_list)
            if excel_buf:
                st.download_button(
                    "📥 엑셀 다운로드",
                    data=excel_buf,
                    file_name=f"즐겨찾기_{today}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        for i, p in enumerate(fav_list):
            render_program_card(p, f"fav_{i}", show_fav=True)


# ============================================================
# 페이지 3: AI 맞춤 추천
# ============================================================
elif page == "🤖 AI 맞춤 추천":
    st.markdown("## 🤖 AI 맞춤 지원사업 추천")
    st.caption("회사 프로필을 입력하면 Gemini AI가 적합한 사업을 선별해 추천합니다.")

    with st.form("profile_form"):
        st.subheader("📋 기업 프로필 입력")
        col1, col2 = st.columns(2)
        with col1:
            company_name = st.text_input("기업명", placeholder="예: (주)한솔제지")
            company_size = st.selectbox("기업 규모", ["중견기업", "중소기업", "대기업", "스타트업"])
            employees = st.number_input("직원 수 (명)", min_value=1, max_value=99999, value=500)
        with col2:
            industry = st.text_input("업종", value="제지·펄프 제조업 (KSIC 1700)")
            location = st.text_input("소재지", placeholder="예: 충남 천안시")
            concerns = st.text_area("현재 고민/니즈", placeholder="예: 생산설비 자동화, 에너지 비용 절감", height=80)
        interests = st.multiselect(
            "관심 분야",
            ["스마트팩토리", "에너지효율화", "R&D/기술개발", "설비투자", "환경/탄소중립",
             "수출지원", "인력개발", "디지털전환", "금융/보증"],
            default=["스마트팩토리", "에너지효율화"],
        )
        submitted = st.form_submit_button("🔍 AI 추천 받기", use_container_width=True)

    if submitted:
        profile = {"name": company_name, "size": company_size, "employees": employees,
                   "industry": industry, "location": location, "concerns": concerns, "interests": interests}
        with st.spinner("Gemini AI가 맞춤 사업을 분석 중입니다..."):
            result = recommend_programs(profile, programs)
        st.divider()
        st.subheader("📊 AI 추천 결과")
        st.markdown(result)


# ============================================================
# 페이지 4: AI 챗봇
# ============================================================
elif page == "💬 AI 챗봇":
    st.markdown("## 💬 AI 지원사업 챗봇")
    st.caption("제지업 정부지원사업에 대해 자유롭게 질문하세요.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

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
        if q_cols[i % 3].button(q, key=f"quick_{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": q})
            with st.spinner("답변 생성 중..."):
                answer = chat_with_gemini(st.session_state.chat_history, q, programs)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

    st.divider()

    if not st.session_state.chat_history:
        st.info("💬 위의 빠른 질문을 클릭하거나 아래에 직접 질문을 입력하세요.")
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("질문을 입력하세요..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                answer = chat_with_gemini(st.session_state.chat_history[:-1], user_input, programs)
            st.markdown(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    if st.session_state.chat_history:
        if st.button("🗑 대화 초기화", type="secondary"):
            st.session_state.chat_history = []
            st.rerun()
