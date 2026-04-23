import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import evaluate_registration  # noqa: E402


def _prior_class35(name: str, service_label: str, status: str = "등록") -> dict:
    return {
        "applicationNumber": f"APP-{name}-35",
        "registrationNumber": f"REG-{name}-35",
        "trademarkName": name,
        "registerStatus": status,
        "classificationCode": "35",
        "applicantName": "test",
        "prior_designated_items": [
            {
                "prior_item_label": service_label,
                "prior_class_no": "35",
                "prior_similarity_codes": [],
                "prior_item_type": "services",
                "prior_underlying_goods_codes": [],
                "source_page_or_source_field": "test",
                "parsing_confidence": "high",
            }
        ],
    }


def test_class35_direct_retail_link_caps_for_apparel_goods() -> None:
    report = evaluate_registration(
        trademark_name="꽃순이",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[25],
        selected_codes=[],
        prior_items=[_prior_class35("꽃순이", "의류 소매업")],
        selected_fields=[],
        specific_product="의류",
    )
    assert report.get("strongest_overlap_type") in {"class35_direct_retail_link", "class35_strong_trade_link"}
    cap_upper = int(report.get("score_explanation", {}).get("stage2_cap_upper", 100) or 100)
    assert cap_upper <= 80


def test_class35_direct_retail_link_for_software_goods() -> None:
    report = evaluate_registration(
        trademark_name="AIRIGHT",
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[9],
        selected_codes=[],
        prior_items=[_prior_class35("AIRIGHT", "컴퓨터 소프트웨어 온라인 판매업")],
        selected_fields=[],
        specific_product="소프트웨어",
    )
    assert report.get("strongest_overlap_type") in {"class35_direct_retail_link", "class35_strong_trade_link"}


def test_class35_general_market_is_warning_only() -> None:
    report = evaluate_registration(
        trademark_name="POOKIE",
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[9],
        selected_codes=[],
        prior_items=[_prior_class35("POOKIE", "온라인 종합 쇼핑몰업")],
        selected_fields=[],
        specific_product="전자기기",
    )
    assert report.get("strongest_overlap_type") in {"class35_general_market_link", "no_material_overlap"}


def test_class35_advertising_is_not_treated_as_direct_conflict() -> None:
    report = evaluate_registration(
        trademark_name="서울병원",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[44],
        selected_codes=[],
        prior_items=[_prior_class35("서울병원", "광고업")],
        selected_fields=[],
        specific_product="의료업",
    )
    assert int(report.get("filtered_prior_count", 0) or 0) == 0


def test_class35_business_consulting_is_not_material_link() -> None:
    report = evaluate_registration(
        trademark_name="케미칼원",
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[1],
        selected_codes=[],
        prior_items=[_prior_class35("케미칼원", "경영자문업")],
        selected_fields=[],
        specific_product="산업용 화학품",
    )
    assert int(report.get("filtered_prior_count", 0) or 0) == 0


def test_low_similarity_mark_does_not_over_penalize_class35_links() -> None:
    report = evaluate_registration(
        trademark_name="유반하지",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[25],
        selected_codes=[],
        prior_items=[_prior_class35("장미마켓", "의류 소매업")],
        selected_fields=[],
        specific_product="의류",
    )
    assert int(report.get("filtered_prior_count", 0) or 0) == 0

