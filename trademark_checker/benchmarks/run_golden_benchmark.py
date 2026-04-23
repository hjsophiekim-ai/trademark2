from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _eval_case(case: dict, disable_exact_override: bool) -> dict:
    from scoring import evaluate_registration

    old_value = os.getenv("TRADEMARK_DISABLE_EXACT_OVERRIDE")
    try:
        if disable_exact_override:
            os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"] = "1"
        else:
            if "TRADEMARK_DISABLE_EXACT_OVERRIDE" in os.environ:
                del os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"]

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
    finally:
        if old_value is None:
            if "TRADEMARK_DISABLE_EXACT_OVERRIDE" in os.environ:
                del os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"]
        else:
            os.environ["TRADEMARK_DISABLE_EXACT_OVERRIDE"] = old_value

    top = (report.get("top_prior") or [{}])[0] if report else {}
    exact_override = top.get("exact_override", {}) if isinstance(top.get("exact_override"), dict) else {}
    return {
        "score": int(report.get("score", 0) or 0),
        "overlap_type": str(top.get("overlap_type", "") or ""),
        "product_similarity_score": int(top.get("product_similarity_score", 0) or 0),
        "confusion_score": int(top.get("confusion_score", 0) or 0),
        "mark_similarity": int(top.get("mark_similarity", 0) or 0),
        "mark_identity": str(top.get("mark_identity", "") or ""),
        "exact_override": bool(exact_override.get("should_override")),
    }


def _predict_outcome(post: dict) -> str:
    overlap = str(post.get("overlap_type", "") or "")
    if overlap.startswith("exact_same_mark_") and int(post.get("confusion_score", 0)) >= 88:
        return "strong_blocker"
    if int(post.get("confusion_score", 0)) >= 75:
        return "medium_risk"
    if overlap == "same_class_only":
        return "same_class_only"
    return "low_risk"


def _is_expected_satisfied(expected: str, post: dict) -> bool:
    pred = _predict_outcome(post)
    if expected == "should_be_strong_blocker":
        return pred == "strong_blocker" and int(post.get("score", 100)) <= 40
    if expected == "should_be_medium_risk":
        return int(post.get("confusion_score", 0) or 0) >= 60
    if expected == "should_not_be_exact_override":
        return not bool(post.get("exact_override"))
    if expected == "should_remain_same_class_only":
        return str(post.get("overlap_type", "")) == "same_class_only"
    return True


def _md_table(rows: list[dict]) -> str:
    headers = [
        "id",
        "category",
        "expected",
        "pre_score",
        "post_score",
        "pre_overlap",
        "post_overlap",
        "pre_prod",
        "post_prod",
        "pre_conf",
        "post_conf",
        "post_exact_override",
        "pass",
    ]
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(r.get("id", "")),
                    str(r.get("category", "")),
                    str(r.get("expected", "")),
                    str(r.get("pre", {}).get("score", "")),
                    str(r.get("post", {}).get("score", "")),
                    str(r.get("pre", {}).get("overlap_type", "")),
                    str(r.get("post", {}).get("overlap_type", "")),
                    str(r.get("pre", {}).get("product_similarity_score", "")),
                    str(r.get("post", {}).get("product_similarity_score", "")),
                    str(r.get("pre", {}).get("confusion_score", "")),
                    str(r.get("post", {}).get("confusion_score", "")),
                    "Y" if r.get("post", {}).get("exact_override") else "",
                    "Y" if r.get("pass") else "",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="markdown output path")
    parser.add_argument("--max-cases", type=int, default=0)
    args = parser.parse_args()

    from golden_benchmark_set import build_cases

    cases = list(build_cases())
    if args.max_cases and args.max_cases > 0:
        cases = cases[: args.max_cases]

    rows = []
    failed = []
    false_pos = []
    false_neg = []
    for c in cases:
        pre = _eval_case(c, disable_exact_override=True)
        post = _eval_case(c, disable_exact_override=False)
        ok = _is_expected_satisfied(str(c.get("expected", "")), post)
        row = {"id": c["id"], "category": c["category"], "expected": c["expected"], "pre": pre, "post": post, "pass": ok}
        rows.append(row)
        if ok:
            continue
        failed.append(row)
        expected = str(c.get("expected", ""))
        if expected in {"should_not_be_exact_override", "should_remain_same_class_only"}:
            false_pos.append(row)
        else:
            false_neg.append(row)

    total = len(rows)
    passed = sum(1 for r in rows if r.get("pass"))

    lines = []
    lines.append("# Golden Benchmark (Exact Override + Product Fallback)")
    lines.append("")
    lines.append(f"- cases: {total}")
    lines.append(f"- passed: {passed}")
    lines.append(f"- failed: {len(failed)}")
    lines.append("")
    lines.append("## 비교표(수정 전/후)")
    lines.append(_md_table(rows))
    lines.append("")
    lines.append("## 실패 케이스 요약(FP/FN 후보)")
    if not failed:
        lines.append("- 없음")
    else:
        lines.append(f"- FN(과소평가) {len(false_neg)}건 / FP(과대평가) {len(false_pos)}건")
        lines.append("")
        lines.append("### FN 상위(과소평가)")
        if false_neg:
            for r in false_neg[:20]:
                lines.append(
                    f"- {r['id']} ({r['category']}, expected={r['expected']}): "
                    f"post overlap={r['post']['overlap_type']}, post score={r['post']['score']}, "
                    f"post prod={r['post']['product_similarity_score']}, post conf={r['post']['confusion_score']}"
                )
        else:
            lines.append("- 없음")
        lines.append("")
        lines.append("### FP 상위(과대평가)")
        if false_pos:
            for r in false_pos[:20]:
                lines.append(
                    f"- {r['id']} ({r['category']}, expected={r['expected']}): "
                    f"post overlap={r['post']['overlap_type']}, post score={r['post']['score']}, "
                    f"post prod={r['post']['product_similarity_score']}, post conf={r['post']['confusion_score']}"
                )
        else:
            lines.append("- 없음")

    output = "\n".join(lines).strip() + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

