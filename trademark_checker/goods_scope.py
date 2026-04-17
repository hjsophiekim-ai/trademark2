"""Item-level similarity classification for goods/services scope."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from legal_scope import SCOPE_GROUP_LABELS, cross_kind_exception, infer_kind_from_classes
from nice_catalog import dedupe_ints, dedupe_strings
from similarity_code_db import get_code_metadata


DATA_DIR = Path(__file__).resolve().parent / "data"
RETAIL_RULES_PATH = DATA_DIR / "retail_goods_relation_rules.json"
RETAIL_CODE_PREFIX = "S20"
BLOCKED_NEAR_RELATION_PAIRS = {
    frozenset({"S0201", "S0301"}),
    frozenset({"G390802", "S123301"}),
}
OVERLAP_LABELS = {
    "exact_primary_overlap": "기본 유사군코드 직접 일치",
    "related_primary_overlap": "근접 유사군코드 충돌",
    "retail_overlap_only": "판매업 코드만 일치",
    "same_class_only": "동일 류 보조 검토",
    "no_material_overlap": "실질 중첩 없음",
}


@lru_cache(maxsize=1)
def _load_retail_rules() -> dict:
    if not RETAIL_RULES_PATH.exists():
        return {"retail_to_goods": {}, "goods_to_retail": {}, "near_relation_pairs": []}
    try:
        with RETAIL_RULES_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"retail_to_goods": {}, "goods_to_retail": {}, "near_relation_pairs": []}


def is_retail_code(code: str) -> bool:
    return str(code or "").strip().upper().startswith(RETAIL_CODE_PREFIX)


def get_underlying_goods_codes(retail_code: str) -> list[str]:
    rules = _load_retail_rules()
    entry = rules.get("retail_to_goods", {}).get(str(retail_code or "").strip().upper(), {})
    return list(entry.get("underlying_groups", []))


def get_related_retail_codes(goods_code: str) -> list[str]:
    rules = _load_retail_rules()
    return list(rules.get("goods_to_retail", {}).get(str(goods_code or "").strip().upper(), []))


def _near_relation_codes(code: str) -> set[str]:
    rules = _load_retail_rules()
    normalized = str(code or "").strip().upper()
    result = set()
    for pair in rules.get("near_relation_pairs", []):
        if len(pair) != 2:
            continue
        normalized_pair = frozenset(str(value or "").strip().upper() for value in pair)
        if normalized_pair in BLOCKED_NEAR_RELATION_PAIRS:
            continue
        if normalized in normalized_pair:
            result.update(normalized_pair)
    result.discard(normalized)
    return result


def _split_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parts = re.split(r"[,/;|·\n]+", text)
        return [part.strip(" []()\"'") for part in parts if part.strip(" []()\"'")]
    if isinstance(value, Iterable):
        merged: list[str] = []
        for item in value:
            merged.extend(_split_values(item))
        return dedupe_strings(merged)
    return [str(value).strip()]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣]+", str(text or "").lower())


def _clean_class_text(value: object) -> int | None:
    digits = re.findall(r"\d+", str(value or ""))
    if not digits:
        return None
    return int(digits[0])


def _extract_classes(value: object) -> list[int]:
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = list(value or [])
    classes: list[int] = []
    for item in raw:
        class_no = _clean_class_text(item)
        if class_no is None or class_no in classes:
            continue
        classes.append(class_no)
    return classes


def _item_code_tokens(code: str) -> set[str]:
    if not code:
        return set()
    row = get_code_metadata(code)
    if not row:
        return set()
    fragments = [row.get("name", ""), row.get("description", ""), row.get("설명", ""), row.get("기준상품", "")]
    return {token for fragment in fragments for token in _tokenize(fragment) if len(token) >= 2}


def normalize_selected_input(
    selected_kind: str | None,
    selected_classes: Iterable[int | str],
    selected_codes: Iterable[str],
    selected_fields: Iterable[dict] | None,
    specific_product_text: str = "",
) -> dict:
    selected_fields = list(selected_fields or [])
    nice_classes = _extract_classes(selected_classes)
    subgroup_ids: list[str] = []
    subgroup_labels: list[str] = []
    group_ids: list[str] = []
    group_labels: list[str] = []
    keywords: list[str] = []
    contextual_similarity_codes: list[str] = []

    for field in selected_fields:
        nice_classes.extend(_extract_classes(field.get("nice_classes", [])))
        maybe_class = _clean_class_text(field.get("class_no", field.get("류", "")))
        if maybe_class is not None:
            nice_classes.append(maybe_class)
        if field.get("field_id"):
            subgroup_ids.append(field["field_id"])
        if field.get("description"):
            subgroup_labels.append(field["description"])
        if field.get("group_id"):
            group_ids.append(field["group_id"])
        if field.get("group_label"):
            group_labels.append(field["group_label"])
        keywords.extend(_split_values(field.get("keywords", [])))
        contextual_similarity_codes.extend(_split_values(field.get("similarity_codes", [])))

    nice_classes = dedupe_ints(nice_classes)
    explicit_similarity_codes = dedupe_strings(selected_codes)
    contextual_similarity_codes = dedupe_strings(contextual_similarity_codes)
    keywords = dedupe_strings(keywords)

    if not selected_kind:
        selected_kind = infer_kind_from_classes(nice_classes)

    all_codes = dedupe_strings([*explicit_similarity_codes, *contextual_similarity_codes])
    base_codes = explicit_similarity_codes or all_codes
    selected_primary_codes = [code for code in base_codes if not is_retail_code(code)]
    selected_related_codes = dedupe_strings(
        [related for code in selected_primary_codes for related in _near_relation_codes(code)]
    )

    explicit_retail_codes = [code for code in base_codes if is_retail_code(code)]
    auto_retail_codes = [retail for code in selected_primary_codes for retail in get_related_retail_codes(code)]
    selected_retail_codes = dedupe_strings([*explicit_retail_codes, *auto_retail_codes])

    text_fragments = [specific_product_text, *subgroup_labels, *group_labels, *keywords]
    for code in all_codes:
        metadata = get_code_metadata(code)
        if metadata:
            text_fragments.extend([metadata.get("name", ""), metadata.get("description", ""), metadata.get("설명", "")])

    return {
        "selected_kind": selected_kind,
        "selected_groups": dedupe_strings(group_labels),
        "selected_group_ids": dedupe_strings(group_ids),
        "selected_subgroups": dedupe_strings(subgroup_labels),
        "selected_subgroup_ids": dedupe_strings(subgroup_ids),
        "selected_nice_classes": nice_classes,
        "selected_similarity_codes": explicit_similarity_codes,
        "contextual_similarity_codes": contextual_similarity_codes,
        "selected_primary_codes": selected_primary_codes,
        "selected_related_codes": selected_related_codes,
        "selected_retail_codes": selected_retail_codes,
        "selected_keywords": keywords,
        "specific_product_text": specific_product_text,
        "tokens": {token for fragment in text_fragments for token in _tokenize(fragment) if len(token) >= 2},
    }


def _confidence_rank(value: str) -> int:
    return {"exact": 4, "high": 3, "medium": 2, "low": 1, "none": 0}.get(str(value or "").lower(), 0)


def _prior_designated_items(item: dict) -> list[dict]:
    designated = item.get("prior_designated_items")
    if isinstance(designated, list) and designated:
        return designated

    explicit_code = str(item.get("similarityGroupCode") or item.get("similarGoodsCode") or "").strip().upper()
    classes = _extract_classes(item.get("classes", item.get("classificationCode", "")))
    if explicit_code:
        return [
            {
                "prior_item_label": item.get("trademarkName", ""),
                "prior_class_no": str(classes[0]) if classes else "",
                "prior_similarity_codes": [explicit_code],
                "prior_item_type": "retail-service" if is_retail_code(explicit_code) else infer_kind_from_classes(classes),
                "prior_underlying_goods_codes": [],
                "source_page_or_source_field": "synthetic_similarityGroupCode",
                "parsing_confidence": "medium",
            }
        ]
    return []


def _evaluate_retail_overlap(selected_codes: list[str], prior_codes: list[str]) -> dict:
    selected_primary = {code for code in selected_codes if not is_retail_code(code)}
    selected_underlying = set(selected_primary)
    for code in selected_codes:
        if is_retail_code(code):
            selected_underlying.update(get_underlying_goods_codes(code))

    prior_primary = {code for code in prior_codes if not is_retail_code(code)}
    prior_underlying = set(prior_primary)
    for code in prior_codes:
        if is_retail_code(code):
            prior_underlying.update(get_underlying_goods_codes(code))

    goods_overlap = sorted(selected_underlying & prior_underlying)
    if goods_overlap:
        return {
            "goods_overlap": True,
            "related_codes": goods_overlap,
            "reason": (
                f"판매업 코드는 같고 기초 상품군 {', '.join(goods_overlap)}도 겹칩니다. "
                "판매업 코드만 같은 경우가 아니라 underlying goods relation이 확인되었습니다."
            ),
        }

    for selected_code in selected_underlying:
        near = _near_relation_codes(selected_code)
        for prior_code in prior_underlying:
            if prior_code in near:
                return {
                    "goods_overlap": True,
                    "related_codes": [selected_code, prior_code],
                    "reason": (
                        f"판매업 코드는 같고 기초 상품군 {selected_code}/{prior_code}가 근접군으로 연결됩니다. "
                        "직접 일치보다는 약하지만 retail-only보다 강한 신호입니다."
                    ),
                }

    return {
        "goods_overlap": False,
        "related_codes": [],
        "reason": (
            "판매업 코드만 같고 기초 상품군은 겹치지 않습니다. "
            "판매업 코드 동일만으로 자동 유사 처리하지 않습니다."
        ),
    }


def _build_overlap_payload(
    *,
    bucket: str,
    scope_bucket: str,
    overlap_type: str,
    overlap_basis: str,
    score: int,
    penalty_weight: float,
    include: bool,
    reason: str,
    confidence: str,
    designated_item: dict | None = None,
    strict_same_code: bool = False,
    overlap_codes: Iterable[str] | None = None,
    primary_overlap_codes: Iterable[str] | None = None,
    related_overlap_codes: Iterable[str] | None = None,
    retail_overlap_codes: Iterable[str] | None = None,
) -> dict:
    primary_overlap_codes = dedupe_strings(primary_overlap_codes or [])
    related_overlap_codes = dedupe_strings(related_overlap_codes or [])
    retail_overlap_codes = dedupe_strings(retail_overlap_codes or [])
    overlap_codes = dedupe_strings(
        overlap_codes or [*primary_overlap_codes, *related_overlap_codes, *retail_overlap_codes]
    )
    strongest_codes = dedupe_strings([*primary_overlap_codes, *related_overlap_codes, *retail_overlap_codes])
    strongest_item_label = ""
    prior_classes: list[str] = []
    prior_item_type = ""
    prior_underlying_goods_codes: list[str] = []
    if designated_item and overlap_type in {"exact_primary_overlap", "related_primary_overlap", "retail_overlap_only"}:
        strongest_item_label = str(designated_item.get("prior_item_label", "")).strip()
        prior_classes = [str(designated_item.get("prior_class_no", "")).strip()] if designated_item.get("prior_class_no") else []
        prior_item_type = str(designated_item.get("prior_item_type", "")).strip()
        prior_underlying_goods_codes = dedupe_strings(designated_item.get("prior_underlying_goods_codes", []))

    return {
        "bucket": bucket,
        "overlap_type": overlap_type,
        "overlap_basis": overlap_basis,
        "scope_bucket": scope_bucket,
        "scope_bucket_label": SCOPE_GROUP_LABELS[scope_bucket],
        "label": OVERLAP_LABELS[overlap_type],
        "score": score,
        "penalty_weight": penalty_weight,
        "strict_same_code": strict_same_code,
        "include": include,
        "overlap_codes": overlap_codes,
        "primary_overlap_codes": primary_overlap_codes,
        "related_overlap_codes": related_overlap_codes,
        "retail_overlap_codes": retail_overlap_codes,
        "primary_code_overlap_count": len(primary_overlap_codes),
        "related_code_overlap_count": len(related_overlap_codes),
        "retail_code_overlap_count": len(retail_overlap_codes),
        "strongest_matching_prior_item": strongest_item_label,
        "strongest_matching_prior_codes": strongest_codes,
        "strongest_matching_prior_class": prior_classes[0] if prior_classes else "",
        "strongest_matching_prior_item_type": prior_item_type,
        "strongest_matching_prior_underlying_goods_codes": prior_underlying_goods_codes,
        "overlap_confidence": confidence,
        "overlap_score_raw": score,
        "reason": reason,
    }


def _evaluate_designated_item(item: dict, context: dict, designated_item: dict) -> dict:
    selected_classes = context["selected_nice_classes"]
    selected_codes = context["selected_similarity_codes"]
    selected_primary = context.get("selected_primary_codes", [code for code in selected_codes if not is_retail_code(code)])
    selected_related = context.get("selected_related_codes", [])
    selected_retail = context.get("selected_retail_codes", [code for code in selected_codes if is_retail_code(code)])

    prior_codes = dedupe_strings(designated_item.get("prior_similarity_codes", []))
    prior_primary = [code for code in prior_codes if not is_retail_code(code)]
    prior_related = dedupe_strings([related for code in prior_primary for related in _near_relation_codes(code)])
    prior_retail = [code for code in prior_codes if is_retail_code(code)]
    prior_classes = _extract_classes([designated_item.get("prior_class_no", "")])
    shared_classes = [value for value in prior_classes if value in selected_classes]

    primary_overlap = sorted(set(selected_primary) & set(prior_primary))
    selected_related_overlap = sorted(set(selected_related) & set(prior_primary))
    prior_related_overlap = sorted(set(selected_primary) & set(prior_related))
    related_overlap = dedupe_strings([*selected_related_overlap, *prior_related_overlap])
    retail_overlap = sorted(set(selected_retail) & set(prior_retail))

    if primary_overlap:
        related_codes = sorted(set(prior_primary) & set(selected_related))
        return _build_overlap_payload(
            bucket="same_code",
            scope_bucket="exact_scope_candidates",
            overlap_type="exact_primary_overlap",
            overlap_basis="primary_exact",
            score=96,
            penalty_weight=1.72,
            include=True,
            reason=(
                f"선택 primary code {', '.join(selected_primary)}와 prior item code "
                f"{', '.join(prior_primary) or '-'} 중 {', '.join(primary_overlap)}가 직접 일치합니다."
            ),
            confidence="exact",
            designated_item=designated_item,
            strict_same_code=True,
            overlap_codes=dedupe_strings([*primary_overlap, *related_codes]),
            primary_overlap_codes=primary_overlap,
            related_overlap_codes=related_codes,
            retail_overlap_codes=retail_overlap,
        )

    if related_overlap:
        return _build_overlap_payload(
            bucket="same_code",
            scope_bucket="exact_scope_candidates",
            overlap_type="related_primary_overlap",
            overlap_basis="primary_related",
            score=58,
            penalty_weight=0.98,
            include=True,
            reason=(
                f"선택 코드 {', '.join(selected_primary)}와 prior item code {', '.join(prior_primary) or '-'} 사이에 "
                f"{', '.join(related_overlap)} 근접 유사군 관계가 확인됩니다."
            ),
            confidence="high",
            designated_item=designated_item,
            overlap_codes=related_overlap,
            related_overlap_codes=related_overlap,
            retail_overlap_codes=retail_overlap,
        )

    if retail_overlap:
        retail_eval = _evaluate_retail_overlap(
            [*selected_primary, *selected_retail],
            prior_codes,
        )
        if retail_eval["goods_overlap"]:
            related_codes = dedupe_strings(retail_eval.get("related_codes", []))
            return _build_overlap_payload(
                bucket="same_code",
                scope_bucket="exact_scope_candidates",
                overlap_type="related_primary_overlap",
                overlap_basis="retail_with_base_goods_overlap",
                score=48,
                penalty_weight=0.74,
                include=True,
                reason=retail_eval["reason"],
                confidence="medium",
                designated_item=designated_item,
                overlap_codes=dedupe_strings([*retail_overlap, *related_codes]),
                related_overlap_codes=related_codes,
                retail_overlap_codes=retail_overlap,
            )
        return _build_overlap_payload(
            bucket="same_class",
            scope_bucket="same_class_candidates",
            overlap_type="retail_overlap_only",
            overlap_basis="retail_only",
            score=18,
            penalty_weight=0.22,
            include=True,
            reason=retail_eval["reason"],
            confidence="low",
            designated_item=designated_item,
            overlap_codes=retail_overlap,
            retail_overlap_codes=retail_overlap,
        )

    if shared_classes:
        prior_token_source = " ".join(
            [designated_item.get("prior_item_label", ""), *prior_primary]
        )
        overlap_tokens = sorted(context["tokens"] & {token for token in _tokenize(prior_token_source) if len(token) >= 2})
        basis = "same_class_context" if overlap_tokens else "same_class_only"
        score = 24 if overlap_tokens else 12
        confidence = "medium" if overlap_tokens else "low"
        reason = (
            "같은 니스류이지만 direct/related 유사군코드 overlap은 없습니다. "
            + (
                f"문맥상 가까운 표현({', '.join(overlap_tokens[:3])})만 있어 보조 검토군으로 남겼습니다."
                if overlap_tokens
                else "금융/보험/부동산처럼 같은 36류라도 item-level SC가 다르면 direct conflict로 올리지 않습니다."
            )
        )
        return _build_overlap_payload(
            bucket="same_class",
            scope_bucket="same_class_candidates",
            overlap_type="same_class_only",
            overlap_basis=basis,
            score=score,
            penalty_weight=0.18,
            include=True,
            reason=reason,
            confidence=confidence,
        )

    return _build_overlap_payload(
        bucket="excluded",
        scope_bucket="irrelevant_candidates",
        overlap_type="no_material_overlap",
        overlap_basis="no_material_overlap",
        score=0,
        penalty_weight=0.0,
        include=False,
        reason="직접 코드, 근접 코드, 판매업-기초상품 연결, 동일 류 보조 요소가 모두 부족합니다.",
        confidence="none",
    )


def _candidate_rank(payload: dict) -> tuple[int, int, int, int]:
    type_rank = {
        "exact_primary_overlap": 5,
        "related_primary_overlap": 4,
        "retail_overlap_only": 2,
        "same_class_only": 1,
        "no_material_overlap": 0,
    }.get(payload.get("overlap_type", "no_material_overlap"), 0)
    return (
        type_rank,
        payload.get("primary_code_overlap_count", 0),
        payload.get("related_code_overlap_count", 0),
        _confidence_rank(payload.get("overlap_confidence", "none")),
    )


def classify_product_similarity(item: dict, context: dict) -> dict:
    designated_items = _prior_designated_items(item)
    if designated_items:
        candidates = [_evaluate_designated_item(item, context, designated_item) for designated_item in designated_items]
        strongest = max(
            candidates,
            key=lambda payload: (
                *_candidate_rank(payload),
                payload.get("overlap_score_raw", payload.get("score", 0)),
            ),
        )
        if strongest["overlap_type"] != "no_material_overlap":
            return strongest

    selected_classes = context["selected_nice_classes"]
    selected_codes = context["selected_similarity_codes"]
    selected_kind = context.get("selected_kind")
    item_classes = [int(value) for value in item.get("classes", []) if str(value).strip()]
    shared_classes = [value for value in item_classes if value in selected_classes]
    item_kind = infer_kind_from_classes(item_classes)
    item_explicit_code = str(item.get("similarityGroupCode", "") or "").strip().upper()
    selected_keywords = context["selected_keywords"]
    similarity_hint = int(item.get("similarity", 0))
    mark_identity = item.get("mark_identity", "similar")

    if shared_classes:
        item_tokens = _item_code_tokens(item_explicit_code)
        overlap_tokens = sorted(context["tokens"] & item_tokens)
        return _build_overlap_payload(
            bucket="same_class",
            scope_bucket="same_class_candidates",
            overlap_type="same_class_only",
            overlap_basis="same_class_context" if overlap_tokens else "same_class_only",
            score=24 if overlap_tokens else 12,
            penalty_weight=0.18,
            include=True,
            reason=(
                "같은 니스류이지만 item-level SC 정보가 없어 보조 검토군으로만 반영했습니다."
                if not overlap_tokens
                else f"같은 니스류이며 문맥상 표현 {', '.join(overlap_tokens[:3])}가 겹칩니다."
            ),
            confidence="low" if not overlap_tokens else "medium",
        )

    cross_kind = cross_kind_exception(
        selected_kind=selected_kind,
        item_kind=item_kind,
        selected_classes=selected_classes,
        item_classes=item_classes,
        selected_codes=selected_codes,
        item_code=item_explicit_code,
        selected_keywords=selected_keywords,
        similarity_hint=similarity_hint,
        mark_identity=mark_identity,
    )
    if cross_kind.get("applies"):
        return _build_overlap_payload(
            bucket="exception",
            scope_bucket="related_market_candidates",
            overlap_type="no_material_overlap",
            overlap_basis="cross_kind_exception",
            score=int(cross_kind["score"]),
            penalty_weight=float(cross_kind["penalty_weight"]),
            include=True,
            reason=cross_kind["reason"],
            confidence="low",
        )

    return _build_overlap_payload(
        bucket="excluded",
        scope_bucket="irrelevant_candidates",
        overlap_type="no_material_overlap",
        overlap_basis="no_material_overlap",
        score=0,
        penalty_weight=0.0,
        include=False,
        reason="직접 코드, 근접 코드, 판매업-기초상품 연결, 동일 류 보조 요소가 모두 부족합니다.",
        confidence="none",
    )
