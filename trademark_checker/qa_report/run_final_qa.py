from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class QaRow:
    case_id: str
    trademark_name: str
    prior_mark: str
    context: str
    expected_judgment: str
    actual_score: int
    overlap_type: str
    mark_similarity: int
    product_similarity_score: int
    confusion_score: int
    exact_override: bool
    phonetic_similarity: int
    passed: bool
    fail_reason: str


def _to_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def _safe_str(value: object) -> str:
    text = str(value or "").strip()
    return text


def _extract_top_fields(report: dict) -> dict:
    top_list = report.get("top_prior") or []
    excluded_list = report.get("excluded_priors") or []
    top = (top_list[0] if top_list else (excluded_list[0] if excluded_list else {})) if isinstance(report, dict) else {}
    exact_override = top.get("exact_override", {}) if isinstance(top.get("exact_override"), dict) else {}
    return {
        "top": top,
        "score": _to_int(report.get("score", 0)),
        "overlap_type": _safe_str(top.get("overlap_type", "")),
        "mark_similarity": _to_int(top.get("mark_similarity", 0)),
        "product_similarity_score": _to_int(top.get("product_similarity_score", 0)),
        "confusion_score": _to_int(top.get("confusion_score", 0)),
        "phonetic_similarity": _to_int(top.get("phonetic_similarity", 0)),
        "exact_override": bool(exact_override.get("should_override")),
        "exact_override_detail": exact_override,
        "absolute": report.get("absolute_refusal_analysis", report.get("distinctiveness_analysis", {})) or {},
        "signals": list(report.get("signals", []) or []),
    }


def _check_case(case_id: str, case: dict, extracted: dict, refs: dict) -> tuple[bool, str]:
    score = extracted["score"]
    overlap = extracted["overlap_type"]
    mark_similarity = extracted["mark_similarity"]
    prod = extracted["product_similarity_score"]
    conf = extracted["confusion_score"]
    exact_override = extracted["exact_override"]
    phon = extracted["phonetic_similarity"]
    absolute = extracted["absolute"]

    if case_id == "A1":
        if not exact_override:
            return False, "exact override가 발동되지 않음"
        if overlap == "same_class_only" or "same_class_only" in _safe_str(extracted["exact_override_detail"].get("original_overlap_type", "")):
            pass
        if overlap == "same_class_only":
            return False, "same_class_only가 남아있음"
        if mark_similarity != 100:
            return False, "완전 동일표장인데 mark_similarity가 100이 아님"
        if prod < 55:
            return False, f"상품 유사도 floor가 낮음({prod})"
        if score > 45:
            return False, f"등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "A2":
        if not exact_override:
            return False, "exact override가 발동되지 않음"
        if overlap == "same_class_only":
            return False, "same_class_only가 남아있음"
        if mark_similarity != 100:
            return False, "완전 동일표장인데 mark_similarity가 100이 아님"
        if prod < 55:
            return False, f"상품 유사도 floor가 낮음({prod})"
        if score > 50:
            return False, f"등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "A3":
        if not exact_override:
            return False, "exact override가 발동되지 않음"
        if overlap == "same_class_only":
            return False, "same_class_only가 남아있음"
        if mark_similarity != 100:
            return False, "완전 동일표장인데 mark_similarity가 100이 아님"
        if score > 55:
            return False, f"등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "B4":
        if overlap not in {"exact_same_mark_cross_class_trade_link", "exact_same_mark_related_goods"}:
            return False, f"관련류 exact 사건인데 overlap_type이 약함({overlap})"
        if conf < 80:
            return False, f"관련류 exact 사건인데 혼동위험이 낮음({conf})"
        if score > 60:
            return False, f"관련류 exact 사건인데 등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "B5":
        if exact_override:
            return False, "class35 사건인데 exact override가 발동됨(금지)"
        if overlap not in {"class35_direct_retail_link", "class35_strong_trade_link"}:
            return False, f"class35 연계가 약함({overlap})"
        if score > 65:
            return False, f"class35 직접 연계인데 등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "B6":
        if exact_override:
            return False, "class35 사건인데 exact override가 발동됨(금지)"
        if overlap not in {"class35_direct_retail_link", "class35_strong_trade_link"}:
            return False, f"class35 연계가 약함({overlap})"
        if score > 70:
            return False, f"class35 강 연계인데 등록가능성이 과도하게 높음({score})"
        return True, ""

    if case_id == "C7":
        if overlap in {"class35_direct_retail_link", "class35_strong_trade_link"}:
            return False, "광고업이 강한 판매/유통 연계로 과대평가됨"
        if score < 55:
            return False, f"광고업인데 등록가능성이 과도하게 낮음({score})"
        return True, ""

    if case_id == "C8":
        if overlap in {"class35_direct_retail_link", "class35_strong_trade_link"}:
            return False, "경영자문업이 강한 판매/유통 연계로 과대평가됨"
        if score < 60:
            return False, f"경영자문업인데 등록가능성이 과도하게 낮음({score})"
        return True, ""

    if case_id == "D9":
        refs["phonetic_pooky"] = phon
        refs["conf_pooky"] = conf
        if exact_override:
            return False, "발음 유사 사건인데 exact override가 발동됨(금지)"
        if phon < 85:
            return False, f"pookie/pooky 발음 유사도가 낮음({phon})"
        if conf < 60:
            return False, f"pookie/pooky 혼동위험이 낮음({conf})"
        return True, ""

    if case_id == "D10":
        refs["phonetic_fooky"] = phon
        refs["conf_fooky"] = conf
        if exact_override:
            return False, "발음 유사 사건인데 exact override가 발동됨(금지)"
        if phon < 70:
            return False, f"pookie/fooky 발음 유사도가 낮음({phon})"
        return True, ""

    if case_id == "D11":
        refs["phonetic_booky"] = phon
        refs["conf_booky"] = conf
        if exact_override:
            return False, "발음 유사 사건인데 exact override가 발동됨(금지)"
        if phon < 65:
            return False, f"pookie/booky 발음 유사도가 너무 낮음({phon})"
        return True, ""

    if case_id == "D12":
        if exact_override:
            return False, "발음 유사 사건인데 exact override가 발동됨(금지)"
        if phon < 70:
            return False, f"rocky/locky 발음 유사도가 낮음({phon})"
        return True, ""

    if case_id == "E13":
        risk = _safe_str(absolute.get("risk_level", absolute.get("absolute_risk_level", "")))
        cap = _to_int(absolute.get("probability_cap", absolute.get("absolute_probability_cap", 95)))
        if risk in {"high", "fatal"}:
            return False, f"유반하지가 Stage1에서 high/fatal로 과대판정됨({risk})"
        if cap < 80:
            return False, f"유반하지가 Stage1에서 과도 cap 적용됨({cap})"
        return True, ""

    if case_id == "E14":
        bases = list(absolute.get("refusal_bases", []) or [])
        if any("33-1-7" in str(b) for b in bases):
            return False, "타류 동일표장 존재 케이스에서 Stage1 33-1-7이 자동 포함됨"
        if score > 80:
            return False, f"동일표장+35류 판매연계 케이스인데 등록가능성이 너무 높음({score})"
        return True, ""

    if case_id == "E15":
        risk = _safe_str(absolute.get("risk_level", absolute.get("absolute_risk_level", "")))
        cap = _to_int(absolute.get("probability_cap", absolute.get("absolute_probability_cap", 95)))
        if risk not in {"high", "fatal"}:
            return False, f"서울병원이 Stage1 강한 거절로 유지되지 않음({risk})"
        if cap > 55:
            return False, f"서울병원 Stage1 cap이 약함({cap})"
        return True, ""

    return True, ""


def _risk_level_from_score(score: int) -> str:
    if score <= 40:
        return "high"
    if score <= 65:
        return "medium"
    return "low"


def _expected_level(text: str) -> str:
    t = str(text or "")
    if "강한" in t or "blocker" in t:
        return "high"
    if "medium" in t or "strong~medium" in t or "경고" in t:
        return "medium"
    return "low"


def _md_table(rows: list[QaRow]) -> str:
    headers = [
        "case",
        "trademark_name",
        "prior",
        "context",
        "expected",
        "actual_score",
        "overlap_type",
        "mark_similarity",
        "product_similarity_score",
        "confusion_score",
        "exact_override",
        "phonetic_similarity",
        "pass",
        "fail_reason",
    ]
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    r.case_id,
                    r.trademark_name,
                    r.prior_mark,
                    r.context,
                    r.expected_judgment,
                    str(r.actual_score),
                    r.overlap_type,
                    str(r.mark_similarity),
                    str(r.product_similarity_score),
                    str(r.confusion_score),
                    "Y" if r.exact_override else "",
                    str(r.phonetic_similarity),
                    "Y" if r.passed else "",
                    r.fail_reason or "",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="trademark_checker/qa_report/qa_final_report.md")
    args = parser.parse_args()

    try:
        from ..scoring import evaluate_registration
        from .qa_cases import build_final_qa_cases
    except Exception:
        from scoring import evaluate_registration
        from qa_report.qa_cases import build_final_qa_cases

    cases = build_final_qa_cases()
    refs: dict = {}
    rows: list[QaRow] = []

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
        extracted = _extract_top_fields(report)
        top = extracted["top"]
        context = f"{','.join([str(x) for x in case.get('selected_classes', [])])}류/{case.get('selected_kind','')}: {case.get('specific_product','')}"
        prior_mark = _safe_str(top.get("trademarkName", "-")) if (case.get("prior_items") or []) else "-"
        ok, reason = _check_case(case["id"], case, extracted, refs)
        rows.append(
            QaRow(
                case_id=case["id"],
                trademark_name=_safe_str(case.get("trademark_name", "")),
                prior_mark=prior_mark,
                context=context,
                expected_judgment=_safe_str(case.get("expected_judgment", "")),
                actual_score=int(extracted["score"]),
                overlap_type=_safe_str(extracted["overlap_type"]),
                mark_similarity=int(extracted["mark_similarity"]),
                product_similarity_score=int(extracted["product_similarity_score"]),
                confusion_score=int(extracted["confusion_score"]),
                exact_override=bool(extracted["exact_override"]),
                phonetic_similarity=int(extracted["phonetic_similarity"]),
                passed=bool(ok),
                fail_reason=reason,
            )
        )

    if "phonetic_pooky" in refs and "phonetic_fooky" in refs and "phonetic_booky" in refs:
        for i, row in enumerate(list(rows)):
            if row.case_id == "D10" and refs["phonetic_fooky"] > refs["phonetic_pooky"]:
                rows[i] = replace(row, passed=False, fail_reason="fooky가 pooky보다 과대평가됨")
            if row.case_id == "D11" and refs["phonetic_booky"] > refs["phonetic_fooky"]:
                rows[i] = replace(row, passed=False, fail_reason="booky가 fooky보다 과대평가됨")

    passed = sum(1 for r in rows if r.passed)
    failed = [r for r in rows if not r.passed]

    deltas = []
    for r in rows:
        expected_level = _expected_level(r.expected_judgment)
        actual_level = _risk_level_from_score(r.actual_score)
        order = {"low": 0, "medium": 1, "high": 2}
        delta = order.get(actual_level, 0) - order.get(expected_level, 0)
        deltas.append((delta, 100 - r.actual_score, r))

    false_pos = [t for t in deltas if t[0] >= 1]
    false_neg = [t for t in deltas if t[0] <= -1]
    false_pos.sort(key=lambda x: (-x[0], -x[1]))
    false_neg.sort(key=lambda x: (x[0], -x[1]))

    lines = []
    lines.append("# 최종 QA 리포트(15개 대표 케이스)")
    lines.append("")
    lines.append(f"- 총 케이스: {len(rows)}")
    lines.append(f"- 통과: {passed}")
    lines.append(f"- 실패: {len(failed)}")
    lines.append("")
    lines.append("## 케이스 결과표")
    lines.append(_md_table(rows))
    lines.append("")
    lines.append("## 요약")
    lines.append(f"- 전체 통과율: {passed}/{len(rows)} ({int(round(passed/len(rows)*100))}%)")
    lines.append("")
    lines.append("### 가장 위험한 오탐 3개(과대평가)")
    if false_pos:
        for _, _, r in false_pos[:3]:
            lines.append(f"- {r.case_id}: expected={r.expected_judgment} / actual score={r.actual_score} / overlap={r.overlap_type}")
    else:
        lines.append("- 없음")
    lines.append("")
    lines.append("### 가장 위험한 과소탐지 3개(과소평가)")
    if false_neg:
        for _, _, r in false_neg[:3]:
            lines.append(f"- {r.case_id}: expected={r.expected_judgment} / actual score={r.actual_score} / overlap={r.overlap_type}")
    else:
        lines.append("- 없음")

    lines.append("")
    lines.append("## 마지막 미세조정이 필요한 규칙 3개(제안)")
    lines.append("- exact override floor 정책(류별 near/strong 구간)을 케이스별 오버슈트/언더슈트에 맞춰 재조정")
    lines.append("- class35_general_market_link의 cap/penalty 정책을 업종별로 더 분리(광고/자문은 더 약하게)")
    lines.append("- same_class_only 구간에서 phonetic>=92 조건의 confusion 하한/상한을 업종(상품/서비스)별로 분리")

    if failed:
        lines.append("")
        lines.append("## 실패 케이스(상세)")
        for r in failed:
            lines.append(f"- {r.case_id}: {r.fail_reason}")

    output = "\n".join(lines).strip() + "\n"
    Path(args.out).write_text(output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

