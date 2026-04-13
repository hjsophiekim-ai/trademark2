"""등록 가능성을 높이기 위한 개선안."""

from __future__ import annotations

from typing import Iterable, List

from scoring import similarity_percent


def _latin_variants(name: str) -> List[str]:
    base = name.upper().replace(" ", "")
    return [f"{base}Z", f"{base}X", f"{base}IA", f"{base}ONE", f"{base}LAB"]


def _korean_variants(name: str) -> List[str]:
    base = name.replace(" ", "")
    return [f"{base}온", f"{base}리", f"{base}랩", f"{base}플러스", f"{base}앤코"]


def _name_variants(name: str) -> List[str]:
    if not name.strip():
        return []
    if name.encode("utf-8", errors="ignore").isascii():
        return _latin_variants(name)
    return _korean_variants(name)


def get_improvements(
    trademark_name: str,
    selected_codes: Iterable[str],
    search_results: List[dict],
    current_score: int,
) -> dict:
    """초보 사용자용 개선안 묶음."""
    name_suggestions = []
    seen = set()
    for index, candidate in enumerate(_name_variants(trademark_name), start=1):
        if candidate in seen:
            continue
        seen.add(candidate)
        max_conflict = 0
        for item in search_results[:5]:
            baseline = item.get("mark_similarity", item.get("similarity", 0))
            compared = similarity_percent(candidate, item.get("trademarkName", ""))
            max_conflict = max(max_conflict, int(max(baseline, compared)))
        bonus = max(5, 16 - int(max_conflict / 10))
        expected_score = min(96, max(current_score + 1, current_score + bonus - index))
        name_suggestions.append(
            {
                "name": candidate,
                "score": expected_score,
                "reason": "기존 선행상표와 발음·철자를 조금 더 다르게 조정한 안입니다.",
            }
        )

    selected_codes = list(selected_codes)
    code_suggestions = []
    sale_codes = [code for code in selected_codes if code.startswith("S")]
    goods_codes = [code for code in selected_codes if code.startswith("G")]

    if sale_codes:
        code_suggestions.append(
            {
                "description": f"{', '.join(sale_codes)}는 실제 운영 범위와 일치할 때 유지, 필요 없으면 분리 출원 검토",
                "reason": "판매업 코드는 보호 범위 확대 목적이어서 기본적으로 중립입니다. 실제 충돌 후보가 있을 때만 분리 전략을 검토하세요.",
                "expected_score": min(95, current_score + 4),
            }
        )

    if goods_codes:
        code_suggestions.append(
            {
                "description": f"{goods_codes[0]} 중심으로 좁혀서 우선 출원",
                "reason": "처음에는 가장 중요한 상품만 출원하면 거절 위험을 낮추기 좋습니다.",
                "expected_score": min(95, current_score + 7),
            }
        )

    class_suggestions = [
        {
            "description": "35류 소매업 대신 실제 제공 서비스군 재검토",
            "reason": "온라인 판매보다 개발·교육·제조 중심이면 다른 류가 더 적합할 수 있습니다.",
            "expected_score": min(95, current_score + 8),
        },
        {
            "description": "핵심 업종 1개만 먼저 출원 후 추후 확대",
            "reason": "초기 충돌 리스크를 줄이고 등록 전략을 단순하게 만들 수 있습니다.",
            "expected_score": min(95, current_score + 5),
        },
    ]

    return {
        "name_suggestions": name_suggestions[:5],
        "code_suggestions": code_suggestions[:3],
        "class_suggestions": class_suggestions[:3],
    }


def build_improvement_plan(
    trademark_name: str,
    current_score: int,
    selected_codes: Iterable[str],
    prior_items: List[dict],
    selected_fields: Iterable[dict],
) -> dict:
    """기존 호환용 래퍼."""
    payload = get_improvements(trademark_name, selected_codes, prior_items, current_score)
    return {
        "name_options": [{"name": item["name"], "expected_score": item["score"]} for item in payload["name_suggestions"]],
        "scope_options": [
            {
                "title": item["description"],
                "description": item["reason"],
                "expected_score": item["expected_score"],
            }
            for item in payload["code_suggestions"]
        ],
        "class_options": [
            {
                "title": item["description"],
                "description": item["reason"],
                "expected_score": item["expected_score"],
            }
            for item in payload["class_suggestions"]
        ],
    }
