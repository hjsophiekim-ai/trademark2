from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _is_hangul(text: str) -> bool:
    for ch in str(text or ""):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return True
    return False


def _roman_key(text: str) -> str:
    import re

    raw = str(text or "").strip()
    compact = re.sub(r"[^0-9A-Za-z]+", "", raw).upper()
    return compact


def _term_key(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if _is_hangul(value):
        return "".join(ch for ch in value if _is_hangul(ch))
    return _roman_key(value)


def _confusion_counts(rows: list[dict], threshold: int, score_key: str) -> dict:
    tp = fp = tn = fn = 0
    for r in rows:
        y = int(r["label"])
        pred = 1 if int(r[score_key]) >= threshold else 0
        if y == 1 and pred == 1:
            tp += 1
        elif y == 0 and pred == 1:
            fp += 1
        elif y == 0 and pred == 0:
            tn += 1
        else:
            fn += 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": prec, "recall": rec, "f1": f1}


def evaluate_pairs(pairs: list[dict]) -> tuple[list[dict], dict]:
    try:
        from ..phonetic_rules import analyze_phonetic_similarity
        from ..scoring import similarity_percent, _concept_similarity_percent, _mark_similarity
        from ..kipris_api import build_phonetic_query_terms
    except Exception:
        from phonetic_rules import analyze_phonetic_similarity
        from scoring import similarity_percent, _concept_similarity_percent, _mark_similarity
        from kipris_api import build_phonetic_query_terms

    rows: list[dict] = []
    for p in pairs:
        a = str(p["a"])
        b = str(p["b"])
        appearance = int(similarity_percent(a, b))
        phon = analyze_phonetic_similarity(a, b, max_paths=12) or {}
        phonetic = int(phon.get("phonetic_similarity", 0) or 0)
        conceptual = int(_concept_similarity_percent(a, b))
        mark_similarity = int(_mark_similarity(appearance, phonetic, conceptual, "문자만"))

        terms = build_phonetic_query_terms(a)
        expanded_keys = {_term_key(t.get("term", "")) for t in (terms or []) if isinstance(t, dict)}
        baseline_keys = {_term_key(a)}
        target_key = _term_key(b)
        hit_baseline = bool(target_key and target_key in baseline_keys)
        hit_expanded = bool(target_key and target_key in expanded_keys)
        recall_gain = bool(hit_expanded and not hit_baseline)

        path_breakdown = phon.get("path_breakdown", []) or []
        best_path = phon.get("best_path", []) or []

        rows.append(
            {
                **p,
                "appearance_similarity": appearance,
                "phonetic_similarity": phonetic,
                "conceptual_similarity": conceptual,
                "mark_similarity": mark_similarity,
                "query_hit_baseline": hit_baseline,
                "query_hit_expanded": hit_expanded,
                "query_recall_gain": recall_gain,
                "best_path": best_path,
                "path_breakdown": path_breakdown,
            }
        )

    thresholds = [50, 60, 70, 75, 80, 85, 90]
    summary = {
        "count": len(rows),
        "pos": sum(1 for r in rows if int(r["label"]) == 1),
        "neg": sum(1 for r in rows if int(r["label"]) == 0),
        "thresholds": thresholds,
        "by_threshold": {t: _confusion_counts(rows, t, "mark_similarity") for t in thresholds},
        "phonetic_by_threshold": {t: _confusion_counts(rows, t, "phonetic_similarity") for t in thresholds},
    }
    return rows, summary


def analyze_errors(rows: list[dict], threshold: int) -> dict:
    fps: list[dict] = []
    fns: list[dict] = []
    for r in rows:
        y = int(r["label"])
        pred = 1 if int(r["mark_similarity"]) >= threshold else 0
        if y == 0 and pred == 1:
            fps.append(r)
        if y == 1 and pred == 0:
            fns.append(r)

    step_counts = Counter()
    for r in fps:
        for entry in (r.get("path_breakdown") or [])[:3]:
            for step in (entry.get("path") or []):
                step_counts[str(step)] += 1

    miss_counts = Counter()
    for r in fns:
        for entry in (r.get("path_breakdown") or [])[:3]:
            for step in (entry.get("path") or []):
                miss_counts[str(step)] += 1

    return {
        "threshold": threshold,
        "false_positives": fps,
        "false_negatives": fns,
        "fp_rule_steps": step_counts.most_common(12),
        "fn_rule_steps": miss_counts.most_common(12),
    }


def _best_threshold(summary: dict) -> int:
    best_t = 70
    best_f1 = -1.0
    for t, row in (summary.get("by_threshold") or {}).items():
        f1 = float(row.get("f1", 0.0))
        if f1 > best_f1:
            best_f1 = f1
            best_t = int(t)
    return best_t


def render_report(rows: list[dict], summary: dict) -> str:
    by_type = defaultdict(int)
    same_class_pos = same_class_neg = 0
    recall_gain_pos = recall_gain_neg = 0
    for r in rows:
        by_type[str(r.get("pair_type", "-"))] += 1
        if int(r["label"]) == 1 and bool(r.get("same_class")):
            same_class_pos += 1
        if int(r["label"]) == 0 and bool(r.get("same_class")):
            same_class_neg += 1
        if int(r["label"]) == 1 and bool(r.get("query_recall_gain")):
            recall_gain_pos += 1
        if int(r["label"]) == 0 and bool(r.get("query_recall_gain")):
            recall_gain_neg += 1

    best_t = _best_threshold(summary)
    err = analyze_errors(rows, best_t)

    lines: list[str] = []
    lines.append("# Phonetic 오프라인 평가 리포트")
    lines.append("")
    lines.append("## 데이터셋 요약")
    lines.append(f"- 전체: {summary.get('count', 0)}")
    lines.append(f"- positive(label=1): {summary.get('pos', 0)} (same_class {same_class_pos})")
    lines.append(f"- negative(label=0): {summary.get('neg', 0)} (same_class {same_class_neg})")
    lines.append(f"- pair_type 분포: {dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0])))}")
    lines.append("")

    pos = int(summary.get("pos", 0) or 0)
    neg = int(summary.get("neg", 0) or 0)
    lines.append("## Query expansion(오프라인 proxy) 효과")
    lines.append(f"- positive recall gain(확장으로만 hit): {recall_gain_pos}/{pos} ({(recall_gain_pos/pos*100.0) if pos else 0.0:.1f}%)")
    lines.append(f"- negative false hit gain(확장으로만 hit): {recall_gain_neg}/{neg} ({(recall_gain_neg/neg*100.0) if neg else 0.0:.1f}%)")
    lines.append("")

    lines.append("## Threshold별 confusion matrix 요약 (mark_similarity 기준)")
    lines.append("| threshold | TP | FP | TN | FN | precision | recall | f1 |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for t in summary.get("thresholds", []):
        row = summary["by_threshold"][t]
        lines.append(
            f"| {t} | {row['tp']} | {row['fp']} | {row['tn']} | {row['fn']} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |"
        )
    lines.append("")

    lines.append(f"## Best threshold(최대 F1): {best_t}")
    lines.append("")

    lines.append("## 오탐/누락 원인(규칙 경로 step 집계)")
    lines.append(f"- FP 주요 step: {err['fp_rule_steps']}")
    lines.append(f"- FN 주요 step: {err['fn_rule_steps']}")
    lines.append("")

    def render_examples(title: str, items: list[dict], limit: int = 12) -> None:
        lines.append(f"## {title}")
        for r in items[:limit]:
            lines.append(
                f"- {r['a']} ↔ {r['b']} | label={r['label']} | appearance={r['appearance_similarity']} phonetic={r['phonetic_similarity']} mark={r['mark_similarity']} | best_path={r.get('best_path', [])}"
            )
        lines.append("")

    render_examples("False Positive 예시(상위)", err["false_positives"], limit=15)
    render_examples("False Negative 예시(상위)", err["false_negatives"], limit=15)

    return "\n".join(lines).rstrip() + "\n"


def tune_config(rows: list[dict]) -> dict:
    try:
        from ..phonetic_config import set_phonetic_config_override
        from ..phonetic_rules import analyze_phonetic_similarity
        from ..scoring import similarity_percent, _concept_similarity_percent, _mark_similarity
        from ..kipris_api import build_phonetic_query_terms
    except Exception:
        from phonetic_config import set_phonetic_config_override
        from phonetic_rules import analyze_phonetic_similarity
        from scoring import similarity_percent, _concept_similarity_percent, _mark_similarity
        from kipris_api import build_phonetic_query_terms

    weak_grid = [0.28, 0.30, 0.32, 0.34, 0.36, 0.38]
    med_grid = [0.18, 0.20, 0.22, 0.24, 0.26]
    qmin_grid = [0.64, 0.66, 0.68, 0.70, 0.72]
    qclass_grid = [0.72, 0.74, 0.76, 0.78]

    base_pairs = [{"a": r["a"], "b": r["b"], "label": r["label"]} for r in rows]

    best = {"objective": -1.0, "f1": -1.0, "threshold": 70, "override": {}}
    thresholds = [60, 65, 70, 75, 80, 85]
    for w in weak_grid:
        for m in med_grid:
            for qmin in qmin_grid:
                for qc in qclass_grid:
                    if qc < qmin:
                        continue
                    override = {"rule_weights": {"sub_weak": w, "sub_medium": m}, "query": {"min_variant_weight": qmin, "min_class_variant_weight": qc}}
                    set_phonetic_config_override(override)

                    tuned_rows: list[dict] = []
                    gain_pos = gain_neg = 0
                    pos_total = neg_total = 0
                    for p in base_pairs:
                        a = str(p["a"])
                        b = str(p["b"])
                        appearance = int(similarity_percent(a, b))
                        phon = analyze_phonetic_similarity(a, b, max_paths=12) or {}
                        phonetic = int(phon.get("phonetic_similarity", 0) or 0)
                        conceptual = int(_concept_similarity_percent(a, b))
                        mark_similarity = int(_mark_similarity(appearance, phonetic, conceptual, "문자만"))
                        tuned_rows.append({"label": int(p["label"]), "mark_similarity": mark_similarity})

                        terms = build_phonetic_query_terms(a)
                        expanded = {_term_key(t.get("term", "")) for t in (terms or []) if isinstance(t, dict)}
                        baseline = {_term_key(a)}
                        target = _term_key(b)
                        gain = bool(target and target in expanded and target not in baseline)
                        if int(p["label"]) == 1:
                            pos_total += 1
                            if gain:
                                gain_pos += 1
                        else:
                            neg_total += 1
                            if gain:
                                gain_neg += 1

                    gain_pos_rate = (gain_pos / pos_total) if pos_total else 0.0
                    gain_neg_rate = (gain_neg / neg_total) if neg_total else 0.0

                    for t in thresholds:
                        cm = _confusion_counts(tuned_rows, t, "mark_similarity")
                        f1 = float(cm.get("f1", 0.0))
                        objective = f1 + gain_pos_rate * 0.04 - gain_neg_rate * 0.40
                        if objective > float(best["objective"]):
                            best = {
                                "objective": objective,
                                "f1": f1,
                                "threshold": t,
                                "override": override,
                                "cm": cm,
                                "query_recall_gain_pos_rate": gain_pos_rate,
                                "query_false_gain_neg_rate": gain_neg_rate,
                            }

    set_phonetic_config_override(None)
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="Markdown report output path")
    parser.add_argument("--json-out", default="", help="Optional JSON rows output path")
    parser.add_argument("--max-pairs", type=int, default=0, help="Evaluate only first N pairs")
    parser.add_argument("--tune", action="store_true", help="Run simple grid search tuner and print best override")
    args = parser.parse_args()

    try:
        from .phonetic_eval_set import EVAL_PAIRS
    except Exception:
        from phonetic_eval_set import EVAL_PAIRS

    pairs = list(EVAL_PAIRS)
    if args.max_pairs and args.max_pairs > 0:
        pairs = pairs[: int(args.max_pairs)]

    rows, summary = evaluate_pairs(pairs)

    out_path = Path(args.out) if args.out else (Path(__file__).resolve().parent / "phonetic_eval_report.md")
    out_path.write_text(render_report(rows, summary), encoding="utf-8")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.tune:
        best = tune_config(rows)
        print(json.dumps(best, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

