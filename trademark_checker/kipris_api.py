"""KIPRIS trademark search helpers.

This module keeps the existing public surface (`search_trademark`,
`search_all_pages`) but adds:
- search-plan metadata for `TN + class + SC` queries
- designated-item parsing/enrichment for prior marks
- fixture-backed item-level detail fallback for known scenarios
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

try:
    from .similarity_code_db import get_class_for_code
except ImportError:
    from similarity_code_db import get_class_for_code

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
try:
    from .resource_paths import data_dir as _data_dir
except ImportError:
    from resource_paths import data_dir as _data_dir


BASE_URL = "https://www.kipris.or.kr/kportal/resulta.do"
USE_MOCK = os.getenv("KIPRIS_USE_MOCK", "false").lower() == "true"
DATA_DIR = _data_dir()
PRIOR_DETAIL_FIXTURE_PATH = DATA_DIR / "prior_mark_detail_fixtures.json"

# Search Status Constants
STATUS_SUCCESS_HITS = "success_with_hits"
STATUS_SUCCESS_ZERO = "success_zero_hits"
STATUS_TRANSPORT_ERROR = "transport_error"
STATUS_PARSE_ERROR = "parse_error"
STATUS_DETAIL_PARSE_ERROR = "detail_parse_error"
STATUS_BLOCKED = "blocked_or_unexpected_page"

_DETAIL_CACHE: dict[str, dict] = {}

QUERY_MODE_LABELS = {
    "primary_sc_only": "TN + primary SC",
    "primary_sc": "TN + class + primary SC",
    "class_only": "TN + class",
    "related_sc_only": "TN + related SC",
    "retail_sc_only": "TN + retail SC",
    "same_class_fallback": "TN + class fallback",
    "text_fallback": "TN broad fallback",
    "phonetic_text_fallback": "TN phonetic fallback",
    "phonetic_class_fallback": "TN + class phonetic fallback",
}

_SESSION: requests.Session | None = None


def _dedupe_strings(values: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    seen = set()
    items: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _normalize_name_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).upper()


def _normalize_class_no(value: str | int | None) -> str:
    digits = re.findall(r"\d+", str(value or ""))
    return str(int(digits[0])) if digits else ""


def _search_mode_for_query_mode(query_mode: str) -> str:
    if query_mode in {"class_only", "same_class_fallback"}:
        return "class"
    if query_mode in {"primary_sc_only", "primary_sc", "related_sc_only", "retail_sc_only"}:
        return "sc"
    return "mixed"


def dedupe_search_candidates(items: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for item in items:
        app_no = str(item.get("applicationNumber", "")).strip()
        reg_no = str(item.get("registrationNumber", "")).strip()
        name = _normalize_name_key(item.get("trademarkName", ""))
        key = (app_no, reg_no, name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _parse_similarity_codes_from_html(html: str) -> list[str]:
    """HTML 본문에서 유사군코드(S0201 등)를 추출한다."""
    # S[0-9]{2}[0-9]{2} 형식의 유사군코드 추출 (S0201, G0201 등)
    # KIPRIS 상세 페이지는 보통 td 태그 안에 [G0101] 또는 (G0101) 형태로 표시함
    # 더 정확하게는 <td ...>G0101</td> 또는 <td>[G0101]</td> 형태를 찾음
    import re
    
    # 1. 태그 내부 텍스트 추출 (간단한 방식)
    codes = re.findall(r'[GS][0-9]{2}[0-9]{2,}', html)
    
    # 2. 지정상품 테이블 내에서 추출 시도 (더 정확함)
    # KIPRIS 상세페이지 지정상품 탭의 구조: <td class="v_left">유사군코드<br/>[G0101]</td>
    table_codes = re.findall(r'\[([GS][0-9]{2}[0-9]{2,})\]', html)
    
    all_codes = set(codes) | set(table_codes)
    return sorted(list(all_codes))

def _parse_designated_items_from_html(html: str, ann: str) -> list[dict]:
    """상세 페이지 HTML에서 지정상품 리스트와 유사군코드를 구조적으로 추출한다."""
    import re
    from html import unescape
    
    items = []
    # KIPRIS 상세페이지 지정상품 행 패턴: <tr> ... <td>순번</td> <td>류</td> <td>지정상품</td> <td>유사군코드</td> ... </tr>
    # 실제로는 매우 복잡하므로, 텍스트 기반으로 우선 파싱하되 
    # 유사군코드가 발견되는 행 주위의 텍스트를 상품명으로 간주함
    
    # 지정상품 테이블 영역 추출 시도
    # <table class="table_style01" ... id="designatedGoodsTable"> ... </table>
    table_match = re.search(r'<table[^>]*id="designatedGoodsTable"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        # 테이블 ID가 없을 경우 일반적인 테이블 구조 시도
        table_match = re.search(r'<table[^>]*>(.*?)지정상품(.*?)</table>', html, re.DOTALL)
        
    if table_match:
        content = table_match.group(1)
        # 각 행(tr) 추출
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cols) >= 3:
                # KIPRIS 상세페이지 지정상품 테이블 구조 대응
                # 보통: 번호(0), 류(1), 유사군코드(2), 지정상품(3) 또는 
                # 번호(0), 류(1), 지정상품(2), 유사군코드(3)
                
                c1 = re.sub(r'<[^>]+>', '', cols[1]).strip() # 류 후보
                c2 = re.sub(r'<[^>]+>', '', cols[2]).strip() # SC 또는 상품명 후보
                c3 = re.sub(r'<[^>]+>', '', cols[3]).strip() if len(cols) > 3 else "" # SC 또는 상품명 후보
                
                # 유사군코드 패턴([GS]\d+)이 어디 있는지 확인
                sc_in_c2 = re.findall(r'[GS][0-9]{2}[0-9]{2,}', c2)
                sc_in_c3 = re.findall(r'[GS][0-9]{2}[0-9]{2,}', c3)
                
                if sc_in_c2:
                    sc_codes = sc_in_c2
                    label = c3 if c3 else c2 # c2에 코드만 있으면 c3가 상품명, 아니면 c2 자체가 상품명 겸용일 수 있음
                elif sc_in_c3:
                    sc_codes = sc_in_c3
                    label = c2
                else:
                    # 코드를 못 찾으면 행 전체에서 검색
                    sc_codes = re.findall(r'[GS][0-9]{2}[0-9]{2,}', row)
                    label = c2 if c2 else c1
                
                class_no = c1 if c1.isdigit() else ""
                
                if label and sc_codes:
                    items.append({
                        "prior_item_label": unescape(label),
                        "prior_class_no": class_no,
                        "prior_similarity_codes": sc_codes,
                        "prior_item_type": "service" if "업" in label or (class_no.isdigit() and int(class_no) >= 35) else "goods",
                        "source_page_or_source_field": f"kipris_detail_api:{ann}",
                        "parsing_confidence": "high"
                    })
    
    # 테이블 파싱 실패 시 텍스트 기반 폴백 (이미 구현된 로직 활용)
    if not items:
        # 기존 텍스트 파싱 로직 호출을 위해 HTML 태그 제거
        text_content = re.sub(r'<[^>]+>', '\n', html)
        items = _parse_designated_items_from_text(text_content, f"kipris_detail_text:{ann}")
        
    return items


def _normalize_similarity_code(value: str) -> str:
    return str(value or "").strip().upper()


def _parse_similarity_codes(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _dedupe_strings(re.findall(r"[GS]\d{4,6}", value.upper()))
    if isinstance(value, list):
        merged: list[str] = []
        for item in value:
            merged.extend(_parse_similarity_codes(item))
        return _dedupe_strings(merged)
    return _parse_similarity_codes(str(value))


def _parse_designated_item_type(value: str, codes: list[str], class_no: str) -> str:
    if any(code.startswith("S20") for code in codes):
        return "retail-service"
    class_value = _normalize_class_no(class_no)
    if class_value:
        return "goods" if int(class_value) <= 34 else "service"
    lowered = str(value or "").lower()
    if "retail" in lowered or "소매" in str(value or ""):
        return "retail-service"
    return "service"


def _parse_underlying_goods_codes(value: object) -> list[str]:
    return _parse_similarity_codes(value)


def _normalize_designated_item(payload: dict, source_field: str, confidence: str) -> dict | None:
    label = str(
        payload.get("prior_item_label")
        or payload.get("item_label")
        or payload.get("label")
        or payload.get("description")
        or ""
    ).strip()
    class_no = _normalize_class_no(
        payload.get("prior_class_no")
        or payload.get("class_no")
        or payload.get("class")
        or payload.get("nice_class")
        or ""
    )
    codes = _parse_similarity_codes(
        payload.get("prior_similarity_codes")
        or payload.get("similarity_codes")
        or payload.get("codes")
        or payload.get("similarityGroupCode")
        or payload.get("similarGoodsCode")
    )
    if not label and not class_no and not codes:
        return None
    item_type = str(
        payload.get("prior_item_type")
        or payload.get("item_type")
        or _parse_designated_item_type(label, codes, class_no)
    ).strip() or "service"
    return {
        "prior_item_label": label or "-",
        "prior_class_no": class_no,
        "prior_similarity_codes": codes,
        "prior_item_type": item_type,
        "prior_underlying_goods_codes": _parse_underlying_goods_codes(
            payload.get("prior_underlying_goods_codes")
            or payload.get("underlying_goods_codes")
            or payload.get("underlying_goods")
        ),
        "source_page_or_source_field": str(
            payload.get("source_page_or_source_field")
            or payload.get("source_field")
            or source_field
        ).strip()
        or source_field,
        "parsing_confidence": str(payload.get("parsing_confidence") or confidence).strip() or confidence,
    }


def _parse_designated_items_from_text(text: str, source_field: str) -> list[dict]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return []

    parsed: list[dict] = []
    current: dict[str, object] = {}
    for line in lines:
        if re.fullmatch(r"\d+", line):
            if current:
                normalized = _normalize_designated_item(current, source_field, "medium")
                if normalized:
                    parsed.append(normalized)
                current = {}
            continue
        if re.fullmatch(r"(제\s*)?\d+\s*류", line):
            current["class_no"] = line
            continue
        codes = re.findall(r"[GS]\d{4,6}", line.upper())
        if codes:
            current["similarity_codes"] = codes
            continue
        if not current.get("label"):
            current["label"] = line
        else:
            current["label"] = f"{current['label']} {line}".strip()

    if current:
        normalized = _normalize_designated_item(current, source_field, "medium")
        if normalized:
            parsed.append(normalized)
    return parsed


def _load_prior_detail_fixtures() -> list[dict]:
    if not PRIOR_DETAIL_FIXTURE_PATH.exists():
        return []
    try:
        with PRIOR_DETAIL_FIXTURE_PATH.open(encoding="utf-8") as file:
            payload = json.load(file)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _fixture_designated_items_for_name(name: str) -> list[dict]:
    target = _normalize_name_key(name)
    if not target:
        return []
    for entry in _load_prior_detail_fixtures():
        names = entry.get("match_names", [])
        normalized_names = {_normalize_name_key(value) for value in names}
        if target not in normalized_names:
            continue
        source_field = str(entry.get("source_field", "fixture")).strip() or "fixture"
        confidence = str(entry.get("parsing_confidence", "high")).strip() or "high"
        items = [
            normalized
            for normalized in (
                _normalize_designated_item(payload, source_field, confidence)
                for payload in entry.get("designated_items", [])
            )
            if normalized
        ]
        if items:
            return items
    return []


def extract_prior_designated_items(item: dict) -> list[dict]:
    for key in ("prior_designated_items", "designated_items", "designatedItems", "prior_items"):
        raw = item.get(key)
        if isinstance(raw, list):
            parsed = [
                normalized
                for normalized in (
                    _normalize_designated_item(payload, key, "high")
                    for payload in raw
                )
                if normalized
            ]
            if parsed:
                return parsed

    for key in (
        "designated_items_text",
        "designatedItemsText",
        "detail_text",
        "detailText",
        "detail_html_text",
        "detailHtmlText",
        "raw_detail_text",
    ):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            parsed = _parse_designated_items_from_text(raw, key)
            if parsed:
                return parsed

    fixture_items = _fixture_designated_items_for_name(
        item.get("trademarkName", item.get("trademark_name", ""))
    )
    if fixture_items:
        return fixture_items

    return []


def fetch_trademark_detail(ann: str) -> dict:
    """상표 상세 정보를 조회한다 (지정상품 및 유사군코드 추출용)."""
    cached = _DETAIL_CACHE.get(str(ann or ""))
    if cached is not None:
        return cached

    if USE_MOCK:
        result = {"success": False, "msg": "MOCK mode - detail fetch skipped"}
        _DETAIL_CACHE[str(ann or "")] = result
        return result

    sess = _get_session()
    # KIPRIS 상세 페이지 URL
    url = f"https://www.kipris.or.kr/kportal/search/selectTmDetail.do?applno={ann}"
    
    try:
        # KIPRIS는 세션과 Referer를 엄격하게 체크함
        resp = sess.get(url, timeout=15, headers={
            "Referer": "https://www.kipris.or.kr/kportal/search/search_trademark.do",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        resp.raise_for_status()
        html = resp.text
        
        # KIPRIS 상세페이지는 AJAX로 지정상품을 불러오기도 함
        # 하지만 초기 HTML에 일부 정보가 포함되어 있을 수 있으므로 추출 시도
        sc_codes = _parse_similarity_codes_from_html(html)
        designated_items = _parse_designated_items_from_html(html, ann)
        
        # 만약 초기 HTML에 지정상품이 없으면 AJAX API 직접 호출 시도
        if not designated_items:
            # KIPRIS의 지정상품 리스트 AJAX 호출 패턴
            ajax_url = "https://www.kipris.or.kr/kportal/search/selectTmGoodsList.do"
            ajax_resp = sess.post(ajax_url, data={"applno": ann}, timeout=10)
            if ajax_resp.status_code == 200 and ajax_resp.text.strip():
                ajax_html = ajax_resp.text
                ajax_items = _parse_designated_items_from_html(ajax_html, ann)
                if ajax_items:
                    designated_items = ajax_items
                    sc_codes = sorted(list(set(sc_codes) | set(_parse_similarity_codes_from_html(ajax_html))))

        result = {
            "success": True,
            "html": html,
            "sc_codes": sc_codes,
            "designated_items": designated_items,
            "has_designated_items": len(designated_items) > 0
        }
        _DETAIL_CACHE[str(ann or "")] = result
        return result
    except Exception as e:
        result = {
            "success": False,
            "msg": f"Detail fetch failed: {str(e)}"
        }
        _DETAIL_CACHE[str(ann or "")] = result
        return result

def enrich_search_results_with_item_details(items: list[dict]) -> dict:
    """선행상표 목록에 상세 정보(지정상품/유사군코드)를 연동한다.
    
    각 선행상표에 대해 KIPRIS '상표지정상품조회' 상세 페이지를 호출하여
    실제 지정상품별 유사군코드(S0201, S1212 등)를 수집하고,
    이를 prior_designated_items 및 queried_codes에 정확히 반영한다.
    
    핵심 목적:
    - 금융(S0201) 검색 시 오렌G트리가 S0201 코드를 가졌는지 정밀 확인
    - same_class_only vs exact_primary_overlap 구분이 가능하도록 SC 코드 수집
    """
    enriched: list[dict] = []
    detail_parse_count = 0
    detail_parse_error_count = 0
    MAX_DETAIL_FETCH = 10  # 상위 후보들만 상세 조회 (KIPRIS 차단 방지)
    
    for idx, item in enumerate(items):
        ann = item.get("applicationNumber")
        
        # 1. 기존 fixture나 텍스트에서 먼저 추출 시도
        designated_items = extract_prior_designated_items(item)
        
        # 2. 상세 페이지에서 실제 SC 코드 수집
        # 상위 10개 후보에 대해 반드시 상세 조회 시도 (정밀 매칭을 위해)
        if len(enriched) < MAX_DETAIL_FETCH and ann:
            detail = fetch_trademark_detail(ann)
            item["detail_fetch_success"] = detail["success"]
            
            if detail["success"]:
                html_sc_codes = detail.get("sc_codes", [])
                html_designated_items = detail.get("designated_items", [])
                
                # HTML에서 추출한 지정상품 리스트가 있으면 사용
                if html_designated_items:
                    designated_items = html_designated_items
                    item["detail_html_text"] = detail.get("html", "")
                    item["detail_sc_codes"] = html_sc_codes
                elif html_sc_codes:
                    # SC 코드만 추출되고 지정상품 리스트는 없으면,
                    # 기존 designated_items의 모든 item에 SC 코드 병합 (중요!)
                    if designated_items:
                        for d in designated_items:
                            existing = set(d.get("prior_similarity_codes", []))
                            existing.update(html_sc_codes)
                            d["prior_similarity_codes"] = sorted(list(existing))
                    else:
                        # 지정상품 자체가 없으면 dummy item으로 코드 정보만 기록
                        designated_items = [{
                            "prior_item_label": "상표지정상품(상세정보)",
                            "prior_class_no": item.get("classificationCode", ""),
                            "prior_similarity_codes": html_sc_codes,
                            "prior_item_type": "unknown",
                            "source_page_or_source_field": f"kipris_detail:{ann}",
                            "parsing_confidence": "high"
                        }]
                    item["detail_sc_codes"] = html_sc_codes
            else:
                item["detail_fetch_error"] = detail.get("msg")
        
        # 3. 추출된 유사군코드를 queried_codes에도 반영 (검색 가시성 및 비교용)
        all_sc = set(item.get("queried_codes", []))
        for d in designated_items:
            for code in d.get("prior_similarity_codes", []):
                all_sc.add(code)
        item["queried_codes"] = sorted(list(all_sc))
        
        # 4. prior_designated_items은 항상 설정 (SC 코드가 없어도 빈 리스트로)
        item["prior_designated_items"] = designated_items
        has_item_level_sc = any(d.get("prior_similarity_codes") for d in designated_items)
        if has_item_level_sc:
            detail_parse_count += 1
        elif ann:
            detail_parse_error_count += 1
            item["detail_parse_error"] = True
        enriched.append(item)

    return {
        "items": enriched,
        "detail_parse_count": detail_parse_count,
        "detail_parse_error_count": detail_parse_error_count,
    }


def build_kipris_search_plan(
    trademark_name: str,
    selected_classes: list[int | str],
    primary_codes: list[str],
    related_codes: list[str] | None = None,
    retail_codes: list[str] | None = None,
) -> list[dict]:
    classes = [_normalize_class_no(value) for value in selected_classes]
    classes = [value for value in classes if value]
    primary_codes = _dedupe_strings([_normalize_similarity_code(value) for value in primary_codes if value])
    related_codes = _dedupe_strings([_normalize_similarity_code(value) for value in (related_codes or []) if value])
    retail_codes = _dedupe_strings([_normalize_similarity_code(value) for value in (retail_codes or []) if value])

    if not classes:
        classes = [""]

    query_terms = _derive_query_terms(trademark_name)
    plan: list[dict] = []

    # Query A: TN + class (class 기반 recall)
    for class_no in classes:
        plan.append(
            {
                "query_mode": "class_only",
                "search_mode": "class",
                "word": trademark_name,
                "class_no": class_no,
                "codes": [],
                "label": QUERY_MODE_LABELS["class_only"],
                "search_formula": f"({trademark_name}) * ({class_no or '-'})",
                "max_pages": 3,
            }
        )

    # Query B: TN + primary SC (same class 밖 후보 회수 핵심)
    for code in primary_codes:
        plan.append(
            {
                "query_mode": "primary_sc_only",
                "search_mode": "sc",
                "word": trademark_name,
                "class_no": "",
                "codes": [code],
                "label": QUERY_MODE_LABELS["primary_sc_only"],
                "search_formula": f"({trademark_name}) * ({code})",
                "max_pages": 3,
            }
        )

    # Query C: TN + class + primary SC
    for class_no in classes:
        for code in primary_codes:
            plan.append(
                {
                    "query_mode": "primary_sc",
                    "search_mode": "mixed",
                    "word": trademark_name,
                    "class_no": class_no,
                    "codes": [code],
                    "label": QUERY_MODE_LABELS["primary_sc"],
                    "search_formula": f"({trademark_name}) * ({class_no or '-'}) * ({code})",
                    "max_pages": 3,
                }
            )

    # Query D: TN + related SC
    for code in related_codes:
        plan.append(
            {
                "query_mode": "related_sc_only",
                "search_mode": "sc",
                "word": trademark_name,
                "class_no": "",
                "codes": [code],
                "label": QUERY_MODE_LABELS["related_sc_only"],
                "search_formula": f"({trademark_name}) * ({code})",
                "max_pages": 2,
            }
        )

    # Query E: TN + retail SC
    for code in retail_codes:
        plan.append(
            {
                "query_mode": "retail_sc_only",
                "search_mode": "sc",
                "word": trademark_name,
                "class_no": "",
                "codes": [code],
                "label": QUERY_MODE_LABELS["retail_sc_only"],
                "search_formula": f"({trademark_name}) * ({code})",
                "max_pages": 2,
            }
        )

    # Query F: TN only fallback
    plan.append(
        {
            "query_mode": "text_fallback",
            "search_mode": "mixed",
            "word": trademark_name,
            "class_no": "",
            "codes": [],
            "label": QUERY_MODE_LABELS["text_fallback"],
            "search_formula": f"({trademark_name})",
            "max_pages": 3,
        }
    )

    for term in query_terms:
        if term.upper() == str(trademark_name or "").strip().upper():
            continue
        plan.append(
            {
                "query_mode": "phonetic_text_fallback",
                "search_mode": "mixed",
                "word": term,
                "class_no": "",
                "codes": [],
                "label": QUERY_MODE_LABELS["phonetic_text_fallback"],
                "search_formula": f"({term})",
                "max_pages": 2,
            }
        )
        for class_no in classes:
            if not class_no:
                continue
            plan.append(
                {
                    "query_mode": "phonetic_class_fallback",
                    "search_mode": "class",
                    "word": term,
                    "class_no": class_no,
                    "codes": [],
                    "label": QUERY_MODE_LABELS["phonetic_class_fallback"],
                    "search_formula": f"({term}) * ({class_no})",
                    "max_pages": 2,
                }
            )

    return plan


def _derive_query_terms(trademark_name: str) -> list[str]:
    raw = str(trademark_name or "").strip()
    if not raw:
        return [""]
    compact = re.sub(r"[^0-9A-Za-z]+", "", raw).upper()
    if not compact:
        return [raw]
    if not re.fullmatch(r"[0-9A-Z]+", compact):
        return [raw]
    if len(compact) < 4:
        return [raw]

    base_terms = [compact, raw]
    prefix = compact[:4]
    base_terms.append(prefix)

    first = compact[0]
    first_groups = [
        ("P", ("P", "B", "F", "V")),
        ("B", ("P", "B", "F", "V")),
        ("F", ("P", "B", "F", "V")),
        ("V", ("P", "B", "F", "V")),
        ("K", ("K", "G", "C", "Q")),
        ("G", ("K", "G", "C", "Q")),
        ("C", ("K", "G", "C", "Q")),
        ("Q", ("K", "G", "C", "Q")),
        ("T", ("T", "D")),
        ("D", ("T", "D")),
        ("S", ("S", "Z")),
        ("Z", ("S", "Z")),
    ]
    replacements = dict(first_groups).get(first, ())
    for rep in replacements:
        if rep == first:
            continue
        base_terms.append(rep + compact[1:])

    vowel_term = compact
    vowel_term = re.sub(r"OO", "U", vowel_term)
    vowel_term = re.sub(r"OU", "U", vowel_term)
    vowel_term = re.sub(r"EE", "I", vowel_term)
    vowel_term = re.sub(r"IE", "I", vowel_term)
    vowel_term = re.sub(r"Y$", "I", vowel_term)
    vowel_term = re.sub(r"E$", "", vowel_term)
    if vowel_term and vowel_term != compact:
        base_terms.append(vowel_term)
        base_terms.append(vowel_term[:4])

    deduped = []
    seen = set()
    for term in base_terms:
        t = str(term or "").strip()
        if not t:
            continue
        key = t.upper()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
        if len(deduped) >= 6:
            break
    return deduped


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.kipris.or.kr/kportal/search/search_trademark.do",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
    return _SESSION


_MOCK_DB = {
    "POOKIE": [
        {
            "applicationNumber": "4020230012345",
            "trademarkName": "POOKIE",
            "applicantName": "테스트주식회사",
            "applicationDate": "20230315",
            "registerStatus": "등록",
            "classificationCode": "45",
            "registrationNumber": "4012340000",
        },
        {
            "applicationNumber": "4020220098765",
            "trademarkName": "POOKIE BEAR",
            "applicantName": "홍길동",
            "applicationDate": "20220810",
            "registerStatus": "출원",
            "classificationCode": "18",
            "registrationNumber": "",
        },
    ],
    # ── G트리 관련 선행상표 (시나리오 테스트용) ────────────────────────────────────
    # "G트리" 검색 시 "G트리"가 포함된 상표명이 반환됨 (substring 매칭)
    "오렌G트리": [
        {
            "applicationNumber": "4020200012399",
            "trademarkName": "오렌G트리",
            "applicantName": "주식회사오렌G트리",
            "applicationDate": "20200801",
            "registerStatus": "등록",
            "classificationCode": "36,38,41",
            "registrationNumber": "4020200099999",
            # prior_designated_items는 prior_mark_detail_fixtures.json 에서 자동 주입됨
        },
    ],
}


def _mock_search(
    word: str,
    similar_goods_code: str,
    class_no: str | int | None,
    num_of_rows: int,
    page_no: int,
    query_mode: str,
) -> dict:
    word_upper = word.upper()
    matched = [
        item
        for key, items in _MOCK_DB.items()
        if word_upper in key.upper()
        for item in items
    ]
    target_class = _normalize_class_no(class_no) or _class_from_goods_code(similar_goods_code)
    if query_mode in {"primary_sc_only", "related_sc_only", "retail_sc_only"}:
        target_class = ""
    if target_class:
        matched = [m for m in matched if target_class in m["classificationCode"].split(",")]
    start = (page_no - 1) * num_of_rows
    return {
        "success": True,
        "result_code": "00",
        "result_msg": "MOCK data",
        "total_count": len(matched),
        "filtered_count": len(matched),
        "items": matched[start : start + num_of_rows],
        "mock": True,
    }


def _class_from_goods_code(code: str) -> str:
    return get_class_for_code(code) or ""


def _build_search_expression(
    word: str,
    similar_goods_code: str = "",
    class_no: str | int | None = None,
    query_mode: str = "",
) -> str:
    """KIPRIS 검색식 빌더.

    - class 축: TN + class
    - sc 축: TN + SC
    - mixed 축: TN + class + SC
    """
    text = str(word or "").strip()
    code = str(similar_goods_code or "").strip().upper()
    class_text = _normalize_class_no(class_no)

    if not text:
        return ""

    parts = [f"({text})"]
    if query_mode in {"class_only", "same_class_fallback"} and class_text:
        parts.append(f"({class_text})")
    elif query_mode in {"primary_sc_only", "related_sc_only", "retail_sc_only"} and code:
        parts.append(f"({code})")
    elif query_mode == "primary_sc":
        if class_text:
            parts.append(f"({class_text})")
        if code:
            parts.append(f"({code})")
    else:
        # fallback: 기존 동작 유지
        if class_text:
            parts.append(f"({class_text})")
        if code:
            parts.append(f"({code})")

    return " * ".join(parts)


def _build_request_payload(
    word: str,
    expression: str,
    page_no: int,
    num_of_rows: int,
    query_mode: str,
    class_no: str,
    code: str,
) -> dict:
    payload = {
        "next": "trademarkList",
        "FROM": "SEARCH",
        "searchInTransKorToEng": "N",
        "searchInTransEngToKor": "N",
        "row": str(num_of_rows),
        "queryText": word,
        "expression": expression or word,
        "page": str(page_no),
    }
    # KIPRIS 상세검색 분류정보->유사군(SC) 경로를 최대한 재현하기 위한 필드 힌트
    if query_mode in {"primary_sc_only", "primary_sc", "related_sc_only", "retail_sc_only"} and code:
        payload.update(
            {
                "searchType": "detail",
                "classificationSearchType": "SC",
                "searchField": "SC",
                "similarGroupCode": code,
                "scQuery": code,
            }
        )
    if class_no:
        payload["classNo"] = class_no
    return payload


def _parse_classes(prc_html: str) -> list[str]:
    font_match = re.search(r'<font title="([^"]+)"', prc_html or "")
    if font_match:
        nums = font_match.group(1).split()
        return [str(int(n)) for n in nums if n.isdigit()]
    nums = re.findall(r">(\d+)<", prc_html or "")
    return [str(int(n)) for n in nums if n.isdigit()]


def _clean_name(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html or "").strip()
    return text.strip("\"'")


def _parse_articles(root: ET.Element) -> list[dict]:
    items: list[dict] = []
    for art in root.findall(".//article"):
        ktn = art.findtext("KTN", "").strip()
        etn = _clean_name(art.findtext("ETN", ""))
        name = ktn if ktn else etn
        classes = _parse_classes(art.findtext("PRC", ""))
        cls_str = ",".join(classes) if classes else ""
        items.append(
            {
                "applicationNumber": art.findtext("ANN", "").strip(),
                "trademarkName": name,
                "applicantName": art.findtext("APNM", "").strip(),
                "applicationDate": art.findtext("AD", "").strip(),
                "registerStatus": art.findtext("LST", "").strip(),
                "classificationCode": cls_str,
                "registrationNumber": art.findtext("RNN", "").strip(),
            }
        )
    return items


def search_trademark(
    word: str,
    similar_goods_code: str = "",
    class_no: str | int | None = None,
    num_of_rows: int = 10,
    page_no: int = 1,
    query_mode: str = "",
) -> dict:
    if USE_MOCK:
        return _mock_search(word, similar_goods_code, class_no, num_of_rows, page_no, query_mode)

    target_class = _normalize_class_no(class_no) or (
        _class_from_goods_code(similar_goods_code) if similar_goods_code else ""
    )
    if query_mode in {"primary_sc_only", "related_sc_only", "retail_sc_only"}:
        target_class = ""
    expression = _build_search_expression(
        word,
        similar_goods_code,
        class_no=target_class,
        query_mode=query_mode,
    )
    payload = _build_request_payload(
        word=word,
        expression=expression,
        page_no=page_no,
        num_of_rows=num_of_rows,
        query_mode=query_mode,
        class_no=target_class,
        code=str(similar_goods_code or "").strip().upper(),
    )

    sess = _get_session()
    resp_text = ""
    try:
        resp = sess.post(
            BASE_URL,
            data=payload,
            timeout=20,
        )
        resp_text = resp.text.strip()
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return _err("KIPRIS request timed out after 20s", status=STATUS_TRANSPORT_ERROR)
    except requests.exceptions.RequestException as exc:
        return _err(str(exc), status=STATUS_TRANSPORT_ERROR)

    # 1단계: Transport success 확인
    if not resp_text:
        return _err("Empty response from KIPRIS", status=STATUS_BLOCKED)
    
    if "<!DOCTYPE html>" in resp_text.lower() or "<html" in resp_text.lower():
        # KIPRIS may return HTML for blocks/errors
        return _err("Unexpected HTML response (possible block or captcha)", 
                    status=STATUS_BLOCKED, 
                    preview=resp_text[:500])

    # 2단계: Result extraction
    try:
        root = ET.fromstring(resp_text)
    except ET.ParseError as exc:
        return _err(f"XML parse error: {exc}", status=STATUS_PARSE_ERROR, preview=resp_text[:500])

    flag = root.findtext("flag", "")
    if flag != "SUCCESS":
        msg = root.findtext("message", flag)
        return _err(f"KIPRIS error: {msg}", status=STATUS_PARSE_ERROR, preview=resp_text[:500])

    total_count = int(root.findtext(".//searchFound", "0"))
    items = _parse_articles(root)
    
    # 류(Class) 필터링 - KIPRIS 검색 결과에 다른 류가 포함될 수 있으므로 클라이언트 사이드에서 재검증
    if target_class:
        items = [item for item in items if target_class in item["classificationCode"].split(",")]

    status = STATUS_SUCCESS_HITS if items else STATUS_SUCCESS_ZERO
    
    return {
        "success": True,
        "search_status": status,
        "http_status": 200,
        "result_code": "00",
        "result_msg": "OK",
        "total_count": total_count,
        "filtered_count": len(items),
        "items": items,
        "mock": False,
        "query_mode": query_mode,
        "search_mode": _search_mode_for_query_mode(query_mode),
        "query_class_no": target_class,
        "query_codes": [similar_goods_code] if similar_goods_code else [],
        "search_expression": expression or word,
        "request_payload_summary": {
            "next": payload.get("next"),
            "query_mode": query_mode,
            "search_mode": _search_mode_for_query_mode(query_mode),
            "classNo": payload.get("classNo", ""),
            "similarGroupCode": payload.get("similarGroupCode", ""),
            "expression": payload.get("expression", ""),
        },
        "response_text_preview": resp_text[:500],
    }


def search_all_pages(
    word: str,
    similar_goods_code: str = "",
    class_no: str | int | None = None,
    max_pages: int = 5,
    rows_per_page: int = 10,
    query_mode: str = "",
) -> dict:
    all_items: list[dict] = []
    total_count = 0
    target_class = _normalize_class_no(class_no) or (
        _class_from_goods_code(similar_goods_code) if similar_goods_code else ""
    )
    if query_mode in {"primary_sc_only", "related_sc_only", "retail_sc_only"}:
        target_class = ""
    search_expression = _build_search_expression(
        word,
        similar_goods_code,
        class_no=target_class,
        query_mode=query_mode,
    )

    last_result = None
    for page in range(1, max_pages + 1):
        result = search_trademark(
            word,
            similar_goods_code=similar_goods_code,
            class_no=target_class,
            num_of_rows=rows_per_page,
            page_no=page,
            query_mode=query_mode,
        )
        last_result = result
        if not result["success"]:
            if page == 1:
                return result
            break
        if page == 1:
            total_count = result["total_count"]
        page_items = result["items"]
        if not page_items:
            break
            
        all_items.extend(
            [
                {
                    **item,
                    "queried_codes": [similar_goods_code] if similar_goods_code else [],
                    "query_mode": query_mode,
                    "query_class_no": target_class,
                    "search_expression": search_expression or word,
                }
                for item in page_items
            ]
        )

        if page * rows_per_page >= total_count:
            break
        time.sleep(0.5)

    merged_candidates = len(all_items)
    deduped_items = dedupe_search_candidates(all_items)
    deduped_candidates = len(deduped_items)
    
    # search_all_pages에서도 최종 상태를 집계하여 반환
    final_status = STATUS_SUCCESS_HITS if deduped_items else STATUS_SUCCESS_ZERO
    if last_result and not last_result["success"]:
        final_status = last_result["search_status"]

    return {
        "success": True,
        "search_status": final_status,
        "result_code": "00",
        "result_msg": "OK",
        "total_count": total_count,
        "filtered_count": len(deduped_items),
        "items": deduped_items,
        "mock": last_result.get("mock", False) if last_result else False,
        "query_mode": query_mode,
        "search_mode": _search_mode_for_query_mode(query_mode),
        "query_class_no": target_class,
        "query_codes": [similar_goods_code] if similar_goods_code else [],
        "search_expression": search_expression or word,
        "request_payload_summary": last_result.get("request_payload_summary", {}) if last_result else {},
        "extracted_total_count": total_count,
        "merged_candidates": merged_candidates,
        "deduped_candidates": deduped_candidates,
        "detail_parse_count": 0,
        "detail_parse_error_count": 0,
        "response_text_preview": last_result.get("response_text_preview", "") if last_result else "",
    }


def _err(msg: str, status: str = "error", preview: str = "") -> dict:
    return {
        "success": False,
        "search_status": status,
        "result_code": "-1",
        "result_msg": msg,
        "total_count": 0,
        "filtered_count": 0,
        "items": [],
        "mock": False,
        "response_text_preview": preview,
    }


if __name__ == "__main__":
    word = sys.argv[1] if len(sys.argv) > 1 else "POOKIE"
    code = sys.argv[2] if len(sys.argv) > 2 else "G4503"
    result = search_all_pages(word, similar_goods_code=code, class_no=None, max_pages=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
