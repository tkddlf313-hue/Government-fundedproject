import requests
import streamlit as st
from datetime import datetime

BIZINFO_BASE = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
KEYWORDS_PAPER = ["제지", "펄프", "종이", "제조", "스마트팩토리", "스마트공장", "중견기업"]


def get_bizinfo_key() -> str:
    return st.secrets.get("BIZINFO_API_KEY", "")


def fetch_support_programs(keywords: list[str], page_size: int = 500) -> tuple[list[dict], str | None]:
    """기업마당 지원사업 전체 조회 후 Python에서 키워드 필터링. (data, error_msg) 반환"""
    key = get_bizinfo_key()
    if not key:
        return [], "기업마당 API 키가 설정되지 않았습니다. Streamlit Secrets에 BIZINFO_API_KEY를 추가해주세요."

    params = {
        "crtfcKey": key,
        "dataType": "json",
        "pageUnit": page_size,
        "pageIndex": 1,
    }

    try:
        resp = requests.get(BIZINFO_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("jsonArray", [])
    except requests.exceptions.HTTPError:
        return [], f"API 오류: HTTP {resp.status_code}"
    except Exception as e:
        return [], f"API 오류: {type(e).__name__}: {e}"

    # Python에서 키워드 필터링 (제목 + hashtags + 대상)
    kw_lower = [k.lower() for k in keywords]
    results = []
    seen = set()
    for item in items:
        pid = item.get("pblancId", item.get("pblancNm", "")[:20])
        if pid in seen:
            continue
        seen.add(pid)
        if kw_lower:
            text = " ".join([
                item.get("pblancNm", ""),
                item.get("hashtags", ""),
                item.get("trgetNm", ""),
                item.get("pldirSportRealmLclasCodeNm", ""),
                item.get("bsnsSumryCn", ""),
            ]).lower()
            if not any(k in text for k in kw_lower):
                continue
        results.append(normalize_bizinfo(item))

    return results, None


def normalize_bizinfo(raw: dict) -> dict:
    """기업마당 API 응답을 통일된 형식으로 변환"""
    title = raw.get("pblancNm") or "제목 없음"
    agency = raw.get("jrsdInsttNm") or raw.get("excInsttNm") or "기업마당"
    category = raw.get("pldirSportRealmLclasCodeNm") or "기타"
    target = raw.get("trgetNm") or ""
    description = raw.get("bsnsSumryCn") or raw.get("hashtags") or ""
    detail_url = raw.get("pblancUrl") or ""

    # 신청기간: "2026-06-26 ~ 2026-07-16" 형식
    period = raw.get("reqstBeginEndDe") or ""
    start_date, end_date = "", ""
    if "~" in period:
        parts = period.split("~")
        start_date = parts[0].strip()[:10].replace("-", "")
        end_date = parts[1].strip()[:10].replace("-", "")

    # HTML 태그 제거
    import re
    description = re.sub(r"<[^>]+>", "", description)[:200]

    return {
        "id": raw.get("pblancId", title[:20]),
        "title": title,
        "agency": agency,
        "category": category,
        "start_date": start_date,
        "end_date": end_date,
        "amount": "",
        "target": target,
        "detail_url": detail_url,
        "description": description,
        "source": "지원사업",
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
    return []
