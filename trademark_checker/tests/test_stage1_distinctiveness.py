import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import evaluate_registration  # noqa: E402


def _prior(name: str, class_no: int, status: str = "등록") -> dict:
    return {
        "applicationNumber": f"APP-{name}-{class_no}",
        "registrationNumber": f"REG-{name}-{class_no}",
        "trademarkName": name,
        "registerStatus": status,
        "classificationCode": str(class_no),
        "applicantName": "test",
    }


def test_stage1_does_not_auto_fail_when_live_exact_exists_any_class() -> None:
    report = evaluate_registration(
        trademark_name="꽃순이",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[25],
        selected_codes=[],
        prior_items=[_prior("꽃순이", 35, status="등록")],
        selected_fields=[],
        specific_product="의류",
    )
    assert "제33-1-7" not in (report.get("absolute_refusal_bases") or [])
    assert int(report.get("absolute_probability_cap", 0)) > 30


def test_stage1_does_not_auto_fail_for_non_obvious_word() -> None:
    report = evaluate_registration(
        trademark_name="유반하지",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[44],
        selected_codes=[],
        prior_items=[],
        selected_fields=[],
        specific_product="의료업",
    )
    assert report.get("absolute_risk_level") not in {"high", "fatal"}
    assert int(report.get("absolute_probability_cap", 0)) > 30
    assert "제33-1-7" not in (report.get("absolute_refusal_bases") or [])


def test_stage1_keeps_strong_refusal_for_geographic_and_service_term() -> None:
    report = evaluate_registration(
        trademark_name="서울병원",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[44],
        selected_codes=[],
        prior_items=[],
        selected_fields=[],
        specific_product="의료업",
    )
    assert report.get("absolute_risk_level") in {"high", "fatal"}
    assert int(report.get("absolute_probability_cap", 95)) <= 30
    bases = set(report.get("absolute_refusal_bases") or [])
    assert ("제33-1-4" in bases) or ("제33-1-3" in bases)


def test_stage1_keeps_strong_refusal_for_descriptive_quality_claim() -> None:
    report = evaluate_registration(
        trademark_name="유기농사과",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[29],
        selected_codes=[],
        prior_items=[],
        selected_fields=[],
        specific_product="식품",
    )
    assert report.get("absolute_risk_level") in {"high", "fatal"}
    assert int(report.get("absolute_probability_cap", 95)) <= 30
    assert "제33-1-3" in set(report.get("absolute_refusal_bases") or [])


def test_stage2_cross_class_exact_is_not_used_as_stage1_cap_reason() -> None:
    report = evaluate_registration(
        trademark_name="꽃순이",
        trademark_type="문자만",
        is_coined=False,
        selected_classes=[25],
        selected_codes=[],
        prior_items=[_prior("꽃순이", 35, status="출원")],
        selected_fields=[],
        specific_product="의류",
    )
    assert "제33-1-7" not in (report.get("absolute_refusal_bases") or [])
    assert int(report.get("absolute_probability_cap", 0)) > 30
