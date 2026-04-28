import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import evaluate_registration


def _eval(class_no: str, specific_product: str, prior_items: list[dict]) -> dict:
    return evaluate_registration(
        trademark_name="G트리",
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[class_no],
        selected_codes=[],
        prior_items=prior_items,
        selected_fields=[],
        specific_product=specific_product,
    )


def test_strong_blocker_pressure_lowers_score_for_class36_finance() -> None:
    prior = {
        "applicationNumber": "1",
        "trademarkName": "오렌G트리",
        "applicantName": "A",
        "registerStatus": "등록",
        "classificationCode": "36",
        "prior_designated_items": [
            {"prior_item_label": "보험업", "prior_class_no": "36", "prior_similarity_codes": []}
        ],
    }
    result = _eval("36", "금융업", [prior])
    top = (result.get("top_prior") or [{}])[0]
    assert top.get("overlap_type") == "same_class_near_services"
    assert int(top.get("confusion_score", 0) or 0) >= 65
    assert int(result.get("score", 100) or 100) <= 50
    summary = (result.get("score_explanation") or {}).get("summary", "")
    assert "강한 선행상표" in summary
    assert "최강 장애물 우선 반영" in summary


def test_blocker_vs_clean_case_gap_is_large() -> None:
    prior = {
        "applicationNumber": "1",
        "trademarkName": "오렌G트리",
        "applicantName": "A",
        "registerStatus": "등록",
        "classificationCode": "36",
        "prior_designated_items": [
            {"prior_item_label": "보험업", "prior_class_no": "36", "prior_similarity_codes": []}
        ],
    }
    finance = _eval("36", "금융업", [prior])
    legal_clean = _eval("45", "법무서비스업", [])
    assert int(finance.get("score", 0) or 0) <= 50
    assert int(legal_clean.get("score", 0) or 0) >= 70
    assert int(legal_clean.get("score", 0) or 0) - int(finance.get("score", 0) or 0) >= 20


def test_clean_case_can_still_be_high() -> None:
    clean = _eval("45", "법무서비스업", [])
    assert int(clean.get("score", 0) or 0) >= 70

