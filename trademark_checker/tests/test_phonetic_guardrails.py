import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phonetic_rules import analyze_phonetic_similarity  # noqa: E402
from scoring import _confusion_metrics  # noqa: E402


def test_common_suffix_only_not_high() -> None:
    analysis = analyze_phonetic_similarity("PONYTECH", "LIONTECH")
    assert analysis["phonetic_similarity"] <= 72
    assert "common_suffix_only" in (analysis.get("phonetic_guardrail_flags") or [])


def test_short_mark_one_char_diff_not_overhigh() -> None:
    analysis = analyze_phonetic_similarity("FOOK", "POOK")
    assert analysis["phonetic_similarity"] <= 84
    assert "short_mark_no_overhigh" in (analysis.get("phonetic_guardrail_flags") or [])


def test_prefix_mismatch_tail_only_not_overhigh() -> None:
    analysis = analyze_phonetic_similarity("SAMSUNG", "KAMSUNG")
    assert analysis["phonetic_similarity"] <= 78
    assert "prefix_mismatch_tail_only" in (analysis.get("phonetic_guardrail_flags") or [])


def test_weak_overlap_confusion_cap_applies() -> None:
    item = {
        "trademarkName": "ALPHATECH",
        "target_trademark_name": "OMEGATECH",
        "target_trademark_type": "문자만",
        "product_similarity_score": 35,
        "mark_similarity": 92,
        "phonetic_similarity": 92,
        "appearance_similarity": 40,
        "conceptual_similarity": 0,
        "counts_toward_final_score": True,
        "status_confusion_weight": 1.0,
        "mark_identity": "similar",
        "product_bucket": "no_material_overlap",
        "overlap_type": "no_material_overlap",
    }
    out = _confusion_metrics(item)
    assert out["confusion_score"] <= 60
    assert out.get("confusion_guardrail_reasons")

