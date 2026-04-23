import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.golden_benchmark_set import build_cases  # noqa: E402
from scoring import evaluate_registration  # noqa: E402


def test_golden_benchmark_case_count_is_50_or_more() -> None:
    cases = build_cases()
    assert len(cases) >= 50


def test_golden_benchmark_smoke_runs_with_and_without_exact_override() -> None:
    cases = build_cases()[:8]
    old_value = os.getenv("TRADEMARK_DISABLE_EXACT_OVERRIDE")
    try:
        os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"] = "1"
        for c in cases:
            report = evaluate_registration(
                trademark_name=c["trademark_name"],
                trademark_type=c.get("trademark_type", "문자만"),
                is_coined=bool(c.get("is_coined", True)),
                selected_classes=c.get("selected_classes", []),
                selected_codes=c.get("selected_codes", []),
                prior_items=c.get("prior_items", []),
                selected_fields=c.get("selected_fields", []),
                specific_product=c.get("specific_product", ""),
            )
            assert "score" in report
            assert "top_prior" in report
    finally:
        if old_value is None:
            if "TRADEMARK_DISABLE_EXACT_OVERRIDE" in os.environ:
                del os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"]
        else:
            os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"] = old_value

    for c in cases:
        report = evaluate_registration(
            trademark_name=c["trademark_name"],
            trademark_type=c.get("trademark_type", "문자만"),
            is_coined=bool(c.get("is_coined", True)),
            selected_classes=c.get("selected_classes", []),
            selected_codes=c.get("selected_codes", []),
            prior_items=c.get("prior_items", []),
            selected_fields=c.get("selected_fields", []),
            specific_product=c.get("specific_product", ""),
        )
        assert "score" in report
        assert "top_prior" in report

