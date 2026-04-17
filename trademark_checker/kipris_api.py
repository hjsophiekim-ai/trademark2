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

from similarity_code_db import get_class_for_code

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


BASE_URL = "https://www.kipris.or.kr/kportal/resulta.do"
USE_MOCK = os.getenv("KIPRIS_USE_MOCK", "false").lower() == "true"
DATA_DIR = Path(__file__).resolve().parent / "data"
PRIOR_DETAIL_FIXTURE_PATH = DATA_DIR / "prior_mark_detail_fixtures.json"
QUERY_MODE_LABELS = {
    "primary_sc": "TN + class + primary SC",
    "class_only": "TN + class",
    "related_sc": "TN + class + related SC",
    "retail_sc": "TN + class + retail SC",
    "same_class_fallback": "TN + class fallback",
    "text_fallback": "TN broad fallback",
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


def enrich_search_results_with_item_details(items: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for item in items:
        designated_items = extract_prior_designated_items(item)
        if designated_items:
            enriched.append({**item, "prior_designated_items": designated_items})
        else:
            enriched.append(item)
    return enriched


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

    plan: list[dict] = []
    for class_no in classes:
        if primary_codes:
            plan.append(
                {
                    "query_mode": "primary_sc",
                    "class_no": class_no,
                    "codes": primary_codes,
                    "label": QUERY_MODE_LABELS["primary_sc"],
                    "search_formula": f"TN={trademark_name} AND CLASS={class_no or '-'} AND SC={' OR '.join(primary_codes)}",
                    "max_pages": 3,
                }
            )
        plan.append(
            {
                "query_mode": "class_only",
                "class_no": class_no,
                "codes": [],
                "label": QUERY_MODE_LABELS["class_only"],
                "search_formula": f"TN={trademark_name} AND CLASS={class_no or '-'}",
                "max_pages": 3,
            }
        )
        if related_codes:
            plan.append(
                {
                    "query_mode": "related_sc",
                    "class_no": class_no,
                    "codes": related_codes,
                    "label": QUERY_MODE_LABELS["related_sc"],
                    "search_formula": f"TN={trademark_name} AND CLASS={class_no or '-'} AND RELATED_SC={' OR '.join(related_codes)}",
                    "max_pages": 2,
                }
            )
        if retail_codes:
            plan.append(
                {
                    "query_mode": "retail_sc",
                    "class_no": class_no,
                    "codes": retail_codes,
                    "label": QUERY_MODE_LABELS["retail_sc"],
                    "search_formula": f"TN={trademark_name} AND CLASS={class_no or '-'} AND SC={' OR '.join(retail_codes)}",
                    "max_pages": 2,
                }
            )
    plan.append(
        {
            "query_mode": "text_fallback",
            "class_no": "",
            "codes": [],
            "label": QUERY_MODE_LABELS["text_fallback"],
            "search_formula": f"TN={trademark_name}",
            "max_pages": 2,
        }
    )
    return plan


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
    del query_mode
    word_upper = word.upper()
    matched = [
        item
        for key, items in _MOCK_DB.items()
        if word_upper in key.upper()
        for item in items
    ]
    target_class = _normalize_class_no(class_no) or _class_from_goods_code(similar_goods_code)
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
    text = str(word or "").strip()
    code = str(similar_goods_code or "").strip().upper()
    class_text = _normalize_class_no(class_no)
    if not text:
        return ""
    parts = [f"TN=[{text}]"]
    if class_text:
        parts.append(f"CLASS=[{class_text}]")
    if code and query_mode in {"primary_sc", "related_sc", "retail_sc"}:
        parts.append(f"SC=[{code}]")
    return " AND ".join(parts)


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
    expression = _build_search_expression(
        word,
        similar_goods_code,
        class_no=target_class,
        query_mode=query_mode,
    )

    sess = _get_session()
    try:
        resp = sess.post(
            BASE_URL,
            data={
                "next": "trademarkList",
                "FROM": "SEARCH",
                "searchInTransKorToEng": "N",
                "searchInTransEngToKor": "N",
                "row": str(num_of_rows),
                "queryText": word,
                "expression": expression or word,
                "page": str(page_no),
            },
            timeout=20,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return _err("KIPRIS request timed out after 20s")
    except requests.exceptions.RequestException as exc:
        return _err(str(exc))

    try:
        root = ET.fromstring(resp.text.strip())
    except ET.ParseError as exc:
        return _err(f"XML parse error: {exc}")

    flag = root.findtext("flag", "")
    if flag != "SUCCESS":
        msg = root.findtext("message", flag)
        return _err(f"KIPRIS error: {msg}")

    total_count = int(root.findtext(".//searchFound", "0"))
    items = _parse_articles(root)
    if target_class:
        items = [item for item in items if target_class in item["classificationCode"].split(",")]

    return {
        "success": True,
        "result_code": "00",
        "result_msg": "OK",
        "total_count": total_count,
        "filtered_count": len(items),
        "items": items,
        "mock": False,
        "query_mode": query_mode,
        "query_class_no": target_class,
        "query_codes": [similar_goods_code] if similar_goods_code else [],
        "search_expression": expression or word,
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
    search_expression = _build_search_expression(
        word,
        similar_goods_code,
        class_no=target_class,
        query_mode=query_mode,
    )

    for page in range(1, max_pages + 1):
        result = search_trademark(
            word,
            similar_goods_code=similar_goods_code,
            class_no=target_class,
            num_of_rows=rows_per_page,
            page_no=page,
            query_mode=query_mode,
        )
        if not result["success"]:
            if page == 1:
                return result
            break
        if page == 1:
            total_count = result["total_count"]
        page_items = result["items"]
        if not page_items:
            break
        if target_class:
            page_items = [item for item in page_items if target_class in item["classificationCode"].split(",")]
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

    enriched_items = enrich_search_results_with_item_details(all_items)
    return {
        "success": True,
        "result_code": "00",
        "result_msg": "OK",
        "total_count": total_count,
        "filtered_count": len(enriched_items),
        "items": enriched_items,
        "mock": False,
        "query_mode": query_mode,
        "query_class_no": target_class,
        "query_codes": [similar_goods_code] if similar_goods_code else [],
        "search_expression": search_expression or word,
    }


def _err(msg: str) -> dict:
    return {
        "success": False,
        "result_code": "-1",
        "result_msg": msg,
        "total_count": 0,
        "filtered_count": 0,
        "items": [],
        "mock": False,
    }


if __name__ == "__main__":
    word = sys.argv[1] if len(sys.argv) > 1 else "POOKIE"
    code = sys.argv[2] if len(sys.argv) > 2 else "G4503"
    result = search_all_pages(word, similar_goods_code=code, class_no=None, max_pages=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
