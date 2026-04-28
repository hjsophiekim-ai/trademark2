"""Regression tests for item-level SC overlap and score caps."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trademark_checker"))

from goods_scope import classify_product_similarity, normalize_selected_input
from report_generator import _overlap_line
from scoring import evaluate_registration


FINANCE_PRIOR_ITEMS = [
    {
        "prior_item_label": "금융 또는 재무에 관한 정보제공업",
        "prior_class_no": "36",
        "prior_similarity_codes": ["S0201", "S120401"],
        "prior_item_type": "service",
        "prior_underlying_goods_codes": [],
        "source_page_or_source_field": "fixture",
        "parsing_confidence": "high",
    },
    {
        "prior_item_label": "금융 또는 재무에 관한 상담업",
        "prior_class_no": "36",
        "prior_similarity_codes": ["S0201", "S120401"],
        "prior_item_type": "service",
        "prior_underlying_goods_codes": [],
        "source_page_or_source_field": "fixture",
        "parsing_confidence": "high",
    },
    {
        "prior_item_label": "금융 및 투자 관련 정보제공업",
        "prior_class_no": "36",
        "prior_similarity_codes": ["S0201"],
        "prior_item_type": "service",
        "prior_underlying_goods_codes": [],
        "source_page_or_source_field": "fixture",
        "parsing_confidence": "high",
    },
]


def _context(classes: list[int], codes: list[str], label: str) -> dict:
    return normalize_selected_input(
        selected_kind="services" if all(value >= 35 for value in classes) else "goods",
        selected_classes=classes,
        selected_codes=codes,
        selected_fields=[],
        specific_product_text=label,
    )


def _prior(
    *,
    name: str = "오렌G트리",
    classes: list[str] | None = None,
    designated_items: list[dict] | None = None,
    status: str = "등록",
    similarity_code: str = "",
) -> dict:
    return {
        "trademarkName": name,
        "applicationNumber": f"40-{name}-1",
        "applicationDate": "2020-01-01",
        "registerStatus": status,
        "classificationCode": ",".join(classes or ["36", "38", "41"]),
        "classes": classes or ["36", "38", "41"],
        "prior_designated_items": designated_items or [],
        "similarityGroupCode": similarity_code,
        "applicantName": "테스트",
    }


def _field(label: str, classes: list[int], codes: list[str]) -> dict:
    return {
        "kind": "services" if all(value >= 35 for value in classes) else "goods",
        "group_id": "test",
        "group_label": "test",
        "field_id": label,
        "description": label,
        "example": label,
        "class_no": str(classes[0]),
        "nice_classes": classes,
        "keywords": [label],
        "similarity_codes": codes,
    }


def _eval(label: str, classes: list[int], codes: list[str], priors: list[dict]) -> dict:
    return evaluate_registration(
        trademark_name="G트리",
        trademark_type="문자",
        is_coined=True,
        selected_classes=classes,
        selected_codes=codes,
        prior_items=priors,
        selected_fields=[_field(label, classes, codes)],
        specific_product=label,
    )


def test_finance_exact_overlap_is_item_level_direct_hit() -> None:
    result = classify_product_similarity(
        _prior(designated_items=FINANCE_PRIOR_ITEMS),
        _context([36], ["S0201"], "금융, 통화 및 은행업"),
    )
    assert result["overlap_type"] == "exact_primary_overlap"
    assert result["strongest_matching_prior_item"] == "금융 또는 재무에 관한 정보제공업"
    assert result["strongest_matching_prior_codes"] == ["S0201", "S120401"]
    assert result["primary_code_overlap_count"] == 1


def test_insurance_without_direct_item_stays_same_class_only() -> None:
    result = classify_product_similarity(
        _prior(designated_items=FINANCE_PRIOR_ITEMS),
        _context([36], ["S0301"], "보험서비스업"),
    )
    assert result["overlap_type"] == "same_class_only"
    assert result["primary_code_overlap_count"] == 0
    assert result["related_code_overlap_count"] == 0


def test_real_estate_without_direct_item_stays_same_class_only() -> None:
    result = classify_product_similarity(
        _prior(designated_items=FINANCE_PRIOR_ITEMS),
        _context([36], ["S1212"], "부동산업"),
    )
    assert result["overlap_type"] == "same_class_only"
    assert result["primary_code_overlap_count"] == 0
    assert result["related_code_overlap_count"] == 0


def test_legal_service_against_finance_items_is_not_material_overlap() -> None:
    result = classify_product_similarity(
        _prior(designated_items=FINANCE_PRIOR_ITEMS),
        _context([45], ["S120402"], "법무서비스업"),
    )
    assert result["overlap_type"] == "no_material_overlap"
    assert result["include"] is False


def test_direct_overlap_case_never_falls_back_to_same_class_band() -> None:
    result = _eval("금융, 통화 및 은행업", [36], ["S0201"], [_prior(designated_items=FINANCE_PRIOR_ITEMS)])
    assert result["strongest_overlap_type"] == "exact_primary_overlap"
    assert result["score"] <= 45
    assert result["stage2_relative_cap_adjusted"] <= 45
    assert result["strongest_matching_prior_item"] == "금융 또는 재무에 관한 정보제공업"


def test_same_class_only_case_can_stay_in_60_to_75_band() -> None:
    result = _eval("부동산업", [36], ["S1212"], [_prior(designated_items=FINANCE_PRIOR_ITEMS)])
    assert result["strongest_overlap_type"] == "same_class_near_services"
    assert 50 <= result["score"] <= 68


def test_g_tree_priority_order_is_legal_then_insurance_real_estate_then_finance() -> None:
    prior = _prior(designated_items=FINANCE_PRIOR_ITEMS)
    finance = _eval("금융, 통화 및 은행업", [36], ["S0201"], [prior])
    insurance = _eval("보험서비스업", [36], ["S0301"], [prior])
    real_estate = _eval("부동산업", [36], ["S1212"], [prior])
    legal = _eval("법무서비스업", [45], ["S120402"], [prior])

    assert finance["strongest_overlap_type"] == "exact_primary_overlap"
    assert insurance["strongest_overlap_type"] == "same_class_near_services"
    assert real_estate["strongest_overlap_type"] == "same_class_near_services"
    assert legal["strongest_overlap_type"] == "no_material_overlap"

    assert finance["score"] <= 45
    assert finance["score"] < insurance["score"]
    assert finance["score"] < real_estate["score"]
    assert insurance["score"] <= legal["score"]
    assert real_estate["score"] <= legal["score"]


def test_item_level_overlap_analysis_exposes_cap_reason_and_codes() -> None:
    result = _eval("금융, 통화 및 은행업", [36], ["S0201"], [_prior(designated_items=FINANCE_PRIOR_ITEMS)])
    overlap = result["overlap_type_analysis"]
    score_explanation = result["score_explanation"]

    assert overlap["selected_primary_codes"] == ["S0201"]
    assert overlap["strongest_matching_prior_item"] == "금융 또는 재무에 관한 정보제공업"
    assert overlap["strongest_matching_prior_codes"] == ["S0201", "S120401"]
    assert overlap["strongest_overlap_type"] == "exact_primary_overlap"
    assert overlap["cap_reason"] == "registered prior + high mark similarity + direct code overlap"
    assert score_explanation["stage2_cap_upper"] <= 45


def test_report_line_prints_strongest_prior_item_and_codes() -> None:
    line = _overlap_line(
        {
            "selected_primary_codes": ["S0201"],
            "strongest_matching_prior_item": "금융 또는 재무에 관한 정보제공업",
            "strongest_matching_prior_codes": ["S0201", "S120401"],
            "overlap_type": "exact_primary_overlap",
            "overlap_confidence": "exact",
        }
    )
    assert "selected primary codes: S0201" in line
    assert "strongest prior item: 금융 또는 재무에 관한 정보제공업" in line
    assert "strongest prior codes: S0201, S120401" in line
    assert "overlap_type: exact_primary_overlap" in line


def test_query_only_sc_without_item_detail_does_not_create_false_direct_overlap() -> None:
    result = classify_product_similarity(
        _prior(designated_items=[], classes=["36"], similarity_code=""),
        _context([36], ["S0201"], "금융, 통화 및 은행업"),
    )
    assert result["overlap_type"] == "same_class_only"
