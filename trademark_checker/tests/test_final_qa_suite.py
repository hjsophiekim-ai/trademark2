import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_report.qa_cases import build_final_qa_cases  # noqa: E402
from scoring import evaluate_registration  # noqa: E402


def _extract_top(report: dict) -> dict:
    top_list = report.get("top_prior") or []
    excluded_list = report.get("excluded_priors") or []
    top = (top_list[0] if top_list else (excluded_list[0] if excluded_list else {})) if report else {}
    exact_override = top.get("exact_override", {}) if isinstance(top.get("exact_override"), dict) else {}
    absolute = report.get("absolute_refusal_analysis", report.get("distinctiveness_analysis", {})) or {}
    return {
        "score": int(report.get("score", 0) or 0),
        "overlap_type": str(top.get("overlap_type", "") or ""),
        "mark_similarity": int(top.get("mark_similarity", 0) or 0),
        "product_similarity_score": int(top.get("product_similarity_score", 0) or 0),
        "confusion_score": int(top.get("confusion_score", 0) or 0),
        "phonetic_similarity": int(top.get("phonetic_similarity", 0) or 0),
        "exact_override": bool(exact_override.get("should_override")),
        "absolute": absolute,
    }


def test_final_qa_suite_15_cases() -> None:
    cases = build_final_qa_cases()
    assert len(cases) == 15


def test_final_qa_suite_passes_all_cases() -> None:
    cases = build_final_qa_cases()
    refs = {}
    results = {}
    for case in cases:
        report = evaluate_registration(
            trademark_name=case["trademark_name"],
            trademark_type=case.get("trademark_type", "문자만"),
            is_coined=bool(case.get("is_coined", True)),
            selected_classes=case.get("selected_classes", []),
            selected_codes=case.get("selected_codes", []),
            prior_items=case.get("prior_items", []),
            selected_fields=case.get("selected_fields", []),
            specific_product=case.get("specific_product", ""),
        )
        extracted = _extract_top(report)
        results[case["id"]] = extracted

    a1 = results["A1"]
    assert a1["exact_override"] is True
    assert a1["overlap_type"] != "same_class_only"
    assert a1["mark_similarity"] == 100
    assert a1["product_similarity_score"] >= 55
    assert a1["score"] <= 45

    a2 = results["A2"]
    assert a2["exact_override"] is True
    assert a2["overlap_type"] != "same_class_only"
    assert a2["mark_similarity"] == 100
    assert a2["product_similarity_score"] >= 55
    assert a2["score"] <= 50

    a3 = results["A3"]
    assert a3["exact_override"] is True
    assert a3["overlap_type"] != "same_class_only"
    assert a3["mark_similarity"] == 100
    assert a3["score"] <= 55

    b4 = results["B4"]
    assert b4["overlap_type"] in {"exact_same_mark_cross_class_trade_link", "exact_same_mark_related_goods"}
    assert b4["confusion_score"] >= 80
    assert b4["score"] <= 60

    b5 = results["B5"]
    assert b5["exact_override"] is False
    assert b5["overlap_type"] in {"class35_direct_retail_link", "class35_strong_trade_link"}
    assert b5["score"] <= 65

    b6 = results["B6"]
    assert b6["exact_override"] is False
    assert b6["overlap_type"] in {"class35_direct_retail_link", "class35_strong_trade_link"}
    assert b6["score"] <= 70

    c7 = results["C7"]
    assert c7["overlap_type"] not in {"class35_direct_retail_link", "class35_strong_trade_link"}
    assert c7["score"] >= 55

    c8 = results["C8"]
    assert c8["overlap_type"] not in {"class35_direct_retail_link", "class35_strong_trade_link"}
    assert c8["score"] >= 60

    d9 = results["D9"]
    refs["phonetic_pooky"] = d9["phonetic_similarity"]
    assert d9["exact_override"] is False
    assert d9["phonetic_similarity"] >= 85
    assert d9["confusion_score"] >= 60

    d10 = results["D10"]
    refs["phonetic_fooky"] = d10["phonetic_similarity"]
    assert d10["exact_override"] is False
    assert d10["phonetic_similarity"] >= 70

    d11 = results["D11"]
    refs["phonetic_booky"] = d11["phonetic_similarity"]
    assert d11["exact_override"] is False
    assert d11["phonetic_similarity"] >= 65

    d12 = results["D12"]
    assert d12["exact_override"] is False
    assert d12["phonetic_similarity"] >= 70

    assert refs["phonetic_pooky"] >= refs["phonetic_fooky"] >= refs["phonetic_booky"]

    e13 = results["E13"]
    abs13 = e13["absolute"]
    risk13 = str(abs13.get("risk_level", abs13.get("absolute_risk_level", "")) or "")
    cap13 = int(abs13.get("probability_cap", abs13.get("absolute_probability_cap", 95)) or 95)
    assert risk13 not in {"high", "fatal"}
    assert cap13 >= 80

    e14 = results["E14"]
    abs14 = e14["absolute"]
    bases14 = list(abs14.get("refusal_bases", []) or [])
    assert not any("33-1-7" in str(b) for b in bases14)
    assert e14["score"] <= 80

    e15 = results["E15"]
    abs15 = e15["absolute"]
    risk15 = str(abs15.get("risk_level", abs15.get("absolute_risk_level", "")) or "")
    cap15 = int(abs15.get("probability_cap", abs15.get("absolute_probability_cap", 95)) or 95)
    assert risk15 in {"high", "fatal"}
    assert cap15 <= 55

