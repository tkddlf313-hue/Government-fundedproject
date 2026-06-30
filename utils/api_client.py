import requests
import streamlit as st
from datetime import datetime

ODCLOUD_BASE = "https://api.odcloud.kr/api"
# 중소기업지원사업목록 (2025년 최신)
ENDPOINT_BIZLIST = "3034791/v1/uddi:fa09d13d-bce8-474e-b214-8008e79ec08f"
# 기업마당 정책뉴스 (2025년 최신)
ENDPOINT_NEWS = "15122782/v1/uddi:a9ebbee9-1ee4-4322-be4f-f19444835caa"

KEYWORDS_PAPER = ["제지", "펄프", "종이", "제조", "스마트팩토리", "스마트공장", "중견기업"]

def get_api_key() -> str:
    return st.secrets.get("PUBLIC_DATA_API_KEY", "")


def _fetch_odcloud(endpoint: str, page: int = 1, page_size: int = 30) -> dict:
    """odcloud API 공통 호출"""
    url = f"{ODCLOUD_BASE}/{endpoint}"
    params = {
        "serviceKey": get_api_key(),
        "page": page,
        "perPage": page_size,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {"items": data.get("data", []), "total": data.get("totalCount", 0), "success": True}
    except Exception as e:
        return {"items": [], "total": 0, "success": False, "error": str(e)}


def fetch_support_programs(keywords: list[str], page_size: int = 30) -> list[dict]:
    """중소기업지원사업목록 + 정책뉴스 통합 조회 후 키워드 필터링"""
    all_items = []

    resp1 = _fetch_odcloud(ENDPOINT_BIZLIST, page_size=page_size)
    if resp1["success"]:
        all_items.extend(resp1["items"])

    resp2 = _fetch_odcloud(ENDPOINT_NEWS, page_size=page_size)
    if resp2["success"]:
        all_items.extend(resp2["items"])

    if not all_items:
        return []

    kw_lower = [k.lower() for k in keywords]
    results = []
    seen = set()

    for item in all_items:
        text = " ".join(str(v) for v in item.values()).lower()
        if not kw_lower or any(k in text for k in kw_lower):
            normalized = normalize_item(item)
            if normalized["id"] not in seen:
                seen.add(normalized["id"])
                results.append(normalized)

    return results


def normalize_item(raw: dict) -> dict:
    """odcloud 응답 필드를 통일된 형식으로 변환 (지원사업목록 + 정책뉴스 공용)"""
    title = (
        raw.get("사업명") or raw.get("제목") or
        raw.get("뉴스제목") or "제목 없음"
    )
    agency = (
        raw.get("소관기관") or raw.get("기관명") or
        raw.get("출처") or "중소벤처기업부"
    )
    start_date = (
        raw.get("신청시작일자") or raw.get("시작일") or
        raw.get("등록일") or ""
    )
    end_date = (
        raw.get("신청종료일자") or raw.get("종료일") or ""
    )
    url = (
        raw.get("상세URL") or raw.get("url") or
        raw.get("원문링크") or ""
    )
    category = raw.get("분야") or raw.get("카테고리") or "기타"
    description = raw.get("본문내용") or raw.get("내용") or raw.get("요약") or ""

    return {
        "id": str(raw.get("번호") or raw.get("연번") or title[:20]),
        "title": title,
        "agency": agency,
        "category": category,
        "start_date": start_date.replace("-", "") if start_date else "",
        "end_date": end_date.replace("-", "") if end_date else "",
        "amount": "",
        "target": raw.get("수행기관") or "",
        "detail_url": url,
        "description": description[:200] if description else f"{agency} | {category}",
        "raw": raw,
    }


def is_deadline_soon(item: dict, days: int = 7) -> bool:
    end_str = item.get("end_date", "")
    if not end_str:
        return False
    try:
        end_dt = datetime.strptime(end_str[:8], "%Y%m%d")
        delta = (end_dt - datetime.now()).days
        return 0 <= delta <= days
    except Exception:
        return False


def get_sample_data() -> list[dict]:
    """API 연결 전 테스트용 샘플 데이터"""
    return [
        {
            "id": "S001",
            "title": "스마트공장 보급·확산 사업",
            "agency": "중소벤처기업부",
            "category": "스마트제조",
            "start_date": "20260601",
            "end_date": "20260731",
            "amount": "최대 1억원",
            "target": "중소·중견 제조기업",
            "detail_url": "https://www.smtech.go.kr",
            "description": "제조 현장의 스마트화를 위한 설비·솔루션 도입 지원. 제지·펄프 업종 포함.",
            "raw": {},
        },
        {
            "id": "S002",
            "title": "중견기업 글로벌 경쟁력 강화 R&D 지원",
            "agency": "산업통상자원부",
            "category": "R&D",
            "start_date": "20260615",
            "end_date": "20260808",
            "amount": "최대 5억원",
            "target": "중견기업",
            "detail_url": "https://www.keit.re.kr",
            "description": "중견기업의 핵심기술 개발 및 글로벌 시장 진출 R&D 지원.",
            "raw": {},
        },
        {
            "id": "S003",
            "title": "제조업 에너지효율화 설비투자 지원",
            "agency": "한국에너지공단",
            "category": "에너지",
            "start_date": "20260520",
            "end_date": "20260720",
            "amount": "최대 3억원",
            "target": "제조업 전 업종",
            "detail_url": "https://www.kemco.or.kr",
            "description": "에너지 다소비 제조업체 대상 고효율 설비 교체 및 공정 개선 자금 지원.",
            "raw": {},
        },
        {
            "id": "S004",
            "title": "산업단지 스마트화 지원사업",
            "agency": "한국산업단지공단",
            "category": "스마트제조",
            "start_date": "20260701",
            "end_date": "20260930",
            "amount": "최대 2억원",
            "target": "산업단지 입주 제조기업",
            "detail_url": "https://www.kicox.or.kr",
            "description": "산업단지 내 스마트팩토리 구축 및 디지털 전환 지원.",
            "raw": {},
        },
        {
            "id": "S005",
            "title": "중소·중견기업 환경설비 지원",
            "agency": "환경부",
            "category": "환경",
            "start_date": "20260601",
            "end_date": "20261031",
            "amount": "최대 2억원",
            "target": "중소·중견 제조기업",
            "detail_url": "https://www.me.go.kr",
            "description": "폐수·대기오염 저감 설비 도입 지원. 제지업 환경 규제 대응에 활용 가능.",
            "raw": {},
        },
    ]
