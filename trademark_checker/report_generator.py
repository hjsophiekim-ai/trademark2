"""PDF report generator."""

from __future__ import annotations

import datetime as dt
import os

from fpdf import FPDF

from nice_catalog import format_nice_classes


class KoreanPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.font_family_name = "Helvetica"
        regular_font = "C:/Windows/Fonts/malgun.ttf"
        bold_font = "C:/Windows/Fonts/malgunbd.ttf"
        try:
            if os.path.exists(regular_font):
                self.add_font("Malgun", "", regular_font)
                self.font_family_name = "Malgun"
            if os.path.exists(bold_font):
                self.add_font("Malgun", "B", bold_font)
        except Exception:
            self.font_family_name = "Helvetica"

    def kfont(self, size: int = 11, bold: bool = False) -> None:
        style = "B" if bold and self.font_family_name == "Malgun" else ""
        self.set_font(self.font_family_name, style, size)


def _safe_text(value: object) -> str:
    return str(value or "").replace("\n", " ").strip()


def _write_lines(pdf: KoreanPDF, width: float, lines: list[str]) -> None:
    for line in lines:
        if not line:
            continue
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(width, 7, _safe_text(line))


def _kind_label(kind: str | None) -> str:
    if kind == "goods":
        return "goods"
    if kind == "services":
        return "services"
    return "-"


def _overlap_line(item: dict) -> str:
    strongest_item = item.get("strongest_matching_prior_item") or "없음"
    strongest_codes = ", ".join(item.get("strongest_matching_prior_codes", []) or item.get("overlap_codes", [])) or "-"
    return (
        f"selected primary codes: {', '.join(item.get('selected_primary_codes', [])) or '-'} / "
        f"strongest prior item: {strongest_item} / "
        f"strongest prior codes: {strongest_codes} / "
        f"overlap_type: {item.get('overlap_type', '-')} / "
        f"confidence: {item.get('overlap_confidence', '-')}"
    )


def _render_top_priors(pdf: KoreanPDF, width: float, payload: dict, top_prior: list[dict]) -> None:
    if not top_prior:
        _write_lines(pdf, width, ["상품 유사성 필터를 통과한 주요 선행상표가 없습니다."])
        return

    selected_primary_codes = payload.get("selected_primary_codes", payload.get("overlap_type_analysis", {}).get("selected_primary_codes", []))
    for index, item in enumerate(top_prior, start=1):
        item = {**item, "selected_primary_codes": selected_primary_codes}
        lines = [
            (
                f"{index}. {item.get('trademarkName', '-')} | 상태 {item.get('status_normalized', item.get('registerStatus', '-'))} "
                f"| {item.get('survival_label', '-')} | 류 {item.get('classificationCode', '-')} "
                f"| 혼동위험 {item.get('confusion_score', 0)}%"
            ),
            (
                f"점수 반영 {item.get('score_reflection_label', '-')} | "
                f"상품 유사도 {item.get('product_similarity_score', 0)}% ({item.get('product_similarity_label', '-')}) | "
                f"표장 유사도 {item.get('mark_similarity', item.get('similarity', 0))}%"
            ),
            f"출원인 {item.get('applicantName', '-')}",
            _overlap_line(item),
            f"상품 범위 판단: {item.get('product_reason', '-')}",
        ]
        _write_lines(pdf, width, lines)
        refusal = item.get("refusal_analysis", {})
        if refusal.get("reason_summary"):
            _write_lines(
                pdf,
                width,
                [
                    f"거절이유 요약: {refusal.get('reason_summary')} "
                    f"(현재 상표 관련성: {refusal.get('current_mark_relevance_label', '-')})"
                ],
            )
        pdf.ln(1)


def _render_absolute_section(pdf: KoreanPDF, width: float, payload: dict) -> None:
    absolute = payload.get("absolute_refusal_analysis", {}) or payload.get("distinctiveness_analysis", {})
    bases = ", ".join(absolute.get("refusal_bases", payload.get("absolute_refusal_bases", []))) or "-"
    cap = absolute.get("probability_cap", payload.get("absolute_probability_cap", "-"))
    lines = [
        absolute.get("summary", payload.get("distinctiveness", "-")),
        (
            f"absolute_risk_level: {absolute.get('risk_level', payload.get('absolute_risk_level', 'none'))} | "
            f"absolute_probability_cap: {cap}% | "
            f"distinctiveness_score: {absolute.get('distinctiveness_score', payload.get('distinctiveness_score', 0))}"
        ),
        f"absolute_refusal_bases: {bases}",
        f"acquired_distinctiveness_needed: {absolute.get('acquired_distinctiveness_needed', payload.get('acquired_distinctiveness_needed', False))}",
    ]
    lines.extend(f"- {reason}" for reason in absolute.get("reasons", payload.get("distinctiveness_analysis", {}).get("reasons", [])))
    _write_lines(pdf, width, lines)


def _render_relative_section(pdf: KoreanPDF, width: float, payload: dict) -> None:
    product_analysis = payload.get("product_similarity_analysis", {})
    overlap_analysis = payload.get("overlap_type_analysis", {})
    score_explanation = payload.get("score_explanation", {})
    lines = [
        product_analysis.get("summary", "-"),
        f"selected primary codes: {', '.join(overlap_analysis.get('selected_primary_codes', [])) or '-'}",
        f"selected related codes: {', '.join(overlap_analysis.get('selected_related_codes', [])) or '-'}",
        f"selected retail codes: {', '.join(overlap_analysis.get('selected_retail_codes', [])) or '-'}",
        f"strongest prior item: {overlap_analysis.get('strongest_matching_prior_item') or '없음'}",
        f"strongest prior codes: {', '.join(overlap_analysis.get('strongest_matching_prior_codes', [])) or '-'}",
        f"overlap_type: {overlap_analysis.get('strongest_overlap_type', '-')}",
        f"overlap_confidence: {overlap_analysis.get('overlap_confidence', '-')}",
        f"cap_reason: {overlap_analysis.get('cap_reason', score_explanation.get('cap_reason', '')) or '-'}",
        f"stage2_cap_upper: {overlap_analysis.get('stage2_cap_upper', score_explanation.get('stage2_cap_upper', '-'))}%",
        overlap_analysis.get("summary", ""),
        *overlap_analysis.get("overlap_explanations", []),
    ]
    if product_analysis.get("exclusion_reason_summary"):
        lines.append(product_analysis["exclusion_reason_summary"])
    if product_analysis.get("reference_summary"):
        lines.append(product_analysis["reference_summary"])
    _write_lines(pdf, width, lines)


def _render_search_debug_section(pdf: KoreanPDF, width: float, payload: dict) -> None:
    if payload.get("search_failed"):
        _write_lines(pdf, width, [f"⚠️ SEARCH FAILED: {payload.get('search_error_msg', 'Unknown Error')}"])
        _write_lines(pdf, width, ["Note: Results may be incomplete or misleading due to engine failure."])
        pdf.ln(1)

    pcodes = ", ".join(payload.get("selected_primary_codes", [])) or "-"
    rcodes = ", ".join(payload.get("selected_related_codes", [])) or "-"
    etcodes = ", ".join(payload.get("selected_retail_codes", [])) or "-"
    _write_lines(pdf, width, [
        f"selected_primary_codes: {pcodes}",
        f"selected_related_codes: {rcodes}",
        f"selected_retail_codes: {etcodes}",
        f"merged_candidates: {payload.get('merged_candidates', 0)}",
        f"deduped_candidates: {payload.get('deduped_candidates', 0)}",
    ])

    executed_queries = payload.get("executed_queries", [])
    if executed_queries:
        _write_lines(pdf, width, ["search_queries_attempted / search_hits_per_query:"])
        for eq in executed_queries:
            hits = eq.get("result_count", 0)
            status = eq.get("search_status", "unknown")
            mark = "[HIT]" if status == "success_with_hits" else "[   ]"
            _write_lines(pdf, width, [
                f"  {mark} [{eq.get('query_mode', '-')}] [{eq.get('search_mode', 'mixed')}] {status.upper()} | "
                f"class={eq.get('class_no', '-')} code={eq.get('code', '') or '(없음)'} -> {hits}건 "
                f"(extracted={eq.get('extracted_total_count', 0)}, detail_parse={eq.get('detail_parse_count', 0)}) | "
                f"{eq.get('search_formula', '')}"
            ])
            if eq.get("request_payload_summary"):
                _write_lines(pdf, width, [f"    payload: {eq.get('request_payload_summary')}"])
    else:
        _write_lines(pdf, width, ["search_queries_attempted: (정보 없음)"])

    ota = payload.get("overlap_type_analysis", {})
    detail_parse_count = payload.get("detail_parse_count", len(payload.get("top_prior", [])))
    _write_lines(pdf, width, [
        f"detail_parse_count: {detail_parse_count}",
        f"strongest_overlap_type: {ota.get('strongest_overlap_type', '-')}",
        f"strongest_prior_item: {ota.get('strongest_matching_prior_item') or '없음'}",
        f"strongest_prior_codes: {', '.join(ota.get('strongest_matching_prior_codes', [])) or '-'}",
        f"overlap_confidence: {ota.get('overlap_confidence', '-')}",
        f"mapping_failed_reason: {payload.get('mapping_failed_reason', '') or '-'}",
    ])


def _render_single_report(pdf: KoreanPDF, width: float, payload: dict, title: str | None = None) -> None:
    if title:
        pdf.kfont(13, bold=True)
        pdf.cell(0, 8, _safe_text(title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    score_explanation = payload.get("score_explanation", {})
    score = payload.get("score", 0)
    stage1_cap = payload.get("absolute_probability_cap", 95)
    stage2_score = payload.get("stage2_relative_cap_adjusted", score)
    
    # 주된 거절 사유 판단
    is_stage1_main = stage1_cap < stage2_score and stage1_cap < 60
    is_stage2_main = stage2_score <= stage1_cap and stage2_score < 60
    
    if is_stage1_main:
        pdf.kfont(11, bold=True)
        pdf.set_text_color(200, 0, 0)
        _write_lines(pdf, width, [f"⚠️ 주요 거절 사유: 단어 자체의 식별력 부족 (Stage 1)"])
        pdf.set_text_color(0, 0, 0)
        pdf.kfont(10)
        _write_lines(pdf, width, [f"선행상표와 상관없이, 상표법 제33조에 의거하여 단어 자체가 공익상 특정인에게 독점시킬 수 없는 성질을 가지고 있습니다. (상한선: {stage1_cap}%)"])
        pdf.ln(1)
    elif is_stage2_main:
        pdf.kfont(11, bold=True)
        pdf.set_text_color(200, 0, 0)
        _write_lines(pdf, width, [f"⚠️ 주요 거절 사유: 선행상표와의 충돌 위험 (Stage 2)"])
        pdf.set_text_color(0, 0, 0)
        pdf.kfont(10)
        _write_lines(pdf, width, [f"유사한 선행상표가 이미 등록되어 있어 혼동의 우려가 있습니다. (상대적 점수: {stage2_score}%)"])
        pdf.ln(1)

    summary_rows = [
        ("specific_product", payload.get("specific_product", "-") or "-"),
        ("kind", _kind_label(payload.get("selected_kind"))),
        ("groups", ", ".join(payload.get("selected_groups", [])) or "-"),
        ("subgroups", ", ".join(payload.get("selected_subgroups", [])) or "-"),
        ("nice_classes", format_nice_classes(payload.get("selected_nice_classes", [])) or "-"),
        ("selected_primary_codes", ", ".join(payload.get("selected_primary_codes", [])) or "-"),
        ("selected_related_codes", ", ".join(payload.get("selected_related_codes", [])) or "-"),
        ("selected_retail_codes", ", ".join(payload.get("selected_retail_codes", [])) or "-"),
        ("registration_probability", f"{payload.get('score', 0)}% - {payload.get('score_label', '-')}"),
        ("cap_reason", score_explanation.get("cap_reason", "-") or "-"),
        ("stage2_cap_upper", f"{score_explanation.get('stage2_cap_upper', '-') }%"),
    ]

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for label, value in summary_rows:
        _write_lines(pdf, width, [f"{label}: {value}"])
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Stage 1", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _render_absolute_section(pdf, width, payload)
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Score Explanation", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _write_lines(
        pdf,
        width,
        [
            f"final score {payload.get('score', 0)}% (raw Stage 2 {score_explanation.get('raw_score', payload.get('score', 0))}%)",
            score_explanation.get("summary", "Stage 1 upper cap and Stage 2 score were combined."),
        ]
        + [f"- {note}" for note in score_explanation.get("notes", [])],
    )
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Stage 2", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _render_relative_section(pdf, width, payload)
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Confusion Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _write_lines(
        pdf,
        width,
        [
            payload.get("confusion_analysis", {}).get("summary", "-"),
            (
                f"live blockers {payload.get('direct_score_prior_count', 0)} / "
                f"historical references {payload.get('historical_reference_count', 0)}"
            ),
        ],
    )
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Search Debug", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _render_search_debug_section(pdf, width, payload)
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Top Prior Marks", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _render_top_priors(pdf, width, payload, payload.get("top_prior", []))
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Improvements", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for option in payload.get("name_options", []):
        _write_lines(pdf, width, [f"name option {option['name']} -> expected {option['expected_score']}%"])
    for option in payload.get("scope_options", []):
        _write_lines(pdf, width, [f"{option['title']}: {option['description']} (expected {option['expected_score']}%)"])
    for option in payload.get("class_options", []):
        _write_lines(pdf, width, [f"{option['title']}: {option['description']} (expected {option['expected_score']}%)"])
    pdf.ln(4)


def generate_report_pdf(payload: dict) -> bytes:
    pdf = KoreanPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.kfont(18, bold=True)
    pdf.cell(0, 12, "Trademark Review Report", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    pdf.cell(0, 8, f"Generated: {dt.date.today().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "Basic Info", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for label, value in [
        ("trademark_name", payload.get("trademark_name", "-")),
        ("trademark_type", payload.get("trademark_type", "-")),
        ("selected_kind", _kind_label(payload.get("selected_kind"))),
        ("selected_groups", ", ".join(payload.get("selected_groups", [])) or "-"),
        ("selected_subgroups", ", ".join(payload.get("selected_subgroups", [])) or "-"),
        ("selected_nice_classes", format_nice_classes(payload.get("selected_nice_classes", [])) or "-"),
        ("selected_primary_codes", ", ".join(payload.get("selected_primary_codes", [])) or "-"),
    ]:
        _write_lines(pdf, width, [f"{label}: {value}"])
    pdf.ln(2)

    field_reports = payload.get("field_reports")
    if field_reports:
        pdf.kfont(12, bold=True)
        pdf.cell(0, 8, f"Field reports: {len(field_reports)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for index, report in enumerate(field_reports, start=1):
            _render_single_report(pdf, width, report, title=f"{index}. {report.get('field_label', 'field')}")
            if index < len(field_reports):
                pdf.add_page()
    else:
        _render_single_report(pdf, width, payload)

    pdf.kfont(8)
    _write_lines(pdf, width, ["This report is an AI-assisted reference and final legal judgment still requires expert review."])
    return bytes(pdf.output())
