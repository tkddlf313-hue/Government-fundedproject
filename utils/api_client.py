import requests
import streamlit as st
from datetime import datetime

BASE_URL = "https://apis.data.go.kr"

KEYWORDS_PAPER = ["제지", "펄프", "종이", "paper", "제조", "스마트팩토리", "스마트공장"]

def get_api_key() -> str:
    return st.secrets.get("PUBLIC_DATA_API_KEY", "")


def fetch_bizinfo_list(keyword: str = "", page: int = 1, page_size: int = 20) -> dict:
    """
    기업마당 지원사업 공고 API (중소기업기술정보진흥원)
    endpoint: /B552735/kisedBizInfo/getBizInfo
    """
    url = f"{BASE_URL}/B552735/kisedBizInfo/getBizInfo"
    params = {
        "serviceKey": get_api_key(),
        "pageNo": page,
        "numOfRows": page_size,
        "returnType": "json",
        "srchTxt": keyword,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        total = (
            data.get("response", {})
                .get("body", {})
                .get("totalCount", 0)
        )
        if isinstance(items, dict):
            items = [items]
        return {"items": items, "total": total, "success": True}
    except Exception as e:
        return {"items": [], "total": 0, "success": False, "error": str(e)}


def fetch_support_programs(keywords: list[str], page_size: int = 30) -> list[dict]:
    """여러 키워드로 지원사업 통합 조회 후 중복 제거"""
    seen_ids = set()
    results = []

    for kw in keywords:
        resp = fetch_bizinfo_list(keyword=kw, page_size=page_size)
        if resp["success"]:
            for item in resp["items"]:
                item_id = item.get("bizId") or item.get("pbanc_rcpt_no") or item.get("title", "")
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    results.append(normalize_item(item))

    return results


def normalize_item(raw: dict) -> dict:
    """API 응답 필드를 통일된 형식으로 변환"""
    return {
        "id": raw.get("bizId") or raw.get("pbanc_rcpt_no", ""),
        "title": raw.get("bizNm") or raw.get("title", "제목 없음"),
        "agency": raw.get("suprtInstNm") or raw.get("creatOrgnztNm", "미확인"),
        "category": raw.get("bizTpcdNm") or raw.get("bizClsfc", ""),
        "start_date": raw.get("reqstBgnde") or raw.get("pbancBgngYmd", ""),
        "end_date": raw.get("reqstEndde") or raw.get("pbancEndYmd", ""),
        "amount": raw.get("sprtAmt") or raw.get("suprtLmttAmt", ""),
        "target": raw.get("trgetNm") or raw.get("bsnsSumryCn", ""),
        "detail_url": raw.get("detailUrl") or raw.get("pbanc_url", ""),
        "description": raw.get("bizCn") or raw.get("bsnsSumryCn", ""),
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
