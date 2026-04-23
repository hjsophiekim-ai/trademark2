import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.phonetic_eval_set import EVAL_PAIRS  # noqa: E402
from benchmarks.run_phonetic_eval import evaluate_pairs  # noqa: E402


def test_eval_dataset_has_100_plus_pairs() -> None:
    assert len(EVAL_PAIRS) >= 100
    assert any(int(p["label"]) == 1 for p in EVAL_PAIRS)
    assert any(int(p["label"]) == 0 for p in EVAL_PAIRS)


def test_eval_metrics_smoke() -> None:
    rows, summary = evaluate_pairs(EVAL_PAIRS[:25])
    assert len(rows) == 25
    assert "by_threshold" in summary
    assert "phonetic_by_threshold" in summary
    sample = rows[0]
    assert "appearance_similarity" in sample
    assert "phonetic_similarity" in sample
    assert "mark_similarity" in sample
    assert "query_hit_expanded" in sample


def test_full_benchmark_mode_generates_report(tmp_path: Path) -> None:
    if os.environ.get("TRADEMARK_BENCHMARK", "").strip() != "1":
        return
    from benchmarks.run_phonetic_eval import render_report  # noqa: E402

    rows, summary = evaluate_pairs(EVAL_PAIRS)
    report = render_report(rows, summary)
    assert "Phonetic 오프라인 평가 리포트" in report
    out = tmp_path / "report.md"
    out.write_text(report, encoding="utf-8")
    assert out.exists()

