import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phonetic_rules import analyze_phonetic_similarity, roman_mark_to_korean_pronunciation_candidates  # noqa: E402


def test_pookie_vs_pooky_high_phonetic_similarity() -> None:
    analysis = analyze_phonetic_similarity("POOKIE", "POOKY")
    assert analysis["phonetic_similarity"] >= 90
    assert analysis["best_path_score"] >= 85


def test_pookie_vs_fooky_higher_than_booky() -> None:
    fooky = analyze_phonetic_similarity("POOKIE", "FOOKY")["phonetic_similarity"]
    booky = analyze_phonetic_similarity("POOKIE", "BOOKY")["phonetic_similarity"]
    assert fooky >= booky


def test_weak_groups_not_overestimated() -> None:
    fooky = analyze_phonetic_similarity("POOKIE", "FOOKY")["phonetic_similarity"]
    gooky = analyze_phonetic_similarity("POOKIE", "GOOKY")["phonetic_similarity"]
    tooky = analyze_phonetic_similarity("POOKIE", "TOOKY")["phonetic_similarity"]
    assert gooky <= fooky
    assert tooky <= fooky


def test_rocky_vs_locky_medium_rl_similarity() -> None:
    analysis = analyze_phonetic_similarity("ROCKY", "LOCKY")
    assert analysis["phonetic_similarity"] >= 75


def test_cross_script_pronunciation_similarity() -> None:
    analysis = analyze_phonetic_similarity("POOKY", "푸키")
    assert analysis["phonetic_similarity"] >= 75
    assert analysis["hangul_pronunciation_similarity"] >= 60


def test_hangul_component_similarity_breakdown() -> None:
    analysis = analyze_phonetic_similarity("쿠키", "꾸키")
    assert analysis["hangul_pronunciation_similarity"] >= 70
    assert analysis["onset_similarity"] >= 70
    assert analysis["vowel_similarity"] >= 80
    assert analysis["coda_similarity"] >= 80
    assert analysis.get("hangul_best_path")
    assert analysis.get("hangul_path_breakdown")


def test_hangul_coda_weakening_path() -> None:
    analysis = analyze_phonetic_similarity("락", "라")
    assert analysis["hangul_pronunciation_similarity"] >= 60
    assert any("종성 약화" in str(step) for step in (analysis.get("hangul_best_path") or []))


def test_roman_to_korean_candidates_downweight_forced() -> None:
    rows = roman_mark_to_korean_pronunciation_candidates("FOOKY")
    weights = {str(r.get("pronunciation")): float(r.get("weight", 0.0) or 0.0) for r in rows}
    assert "푸키" in weights
    assert "후키" in weights
    assert weights["후키"] < weights["푸키"]

