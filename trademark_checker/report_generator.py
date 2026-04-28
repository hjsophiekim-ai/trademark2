"""PDF report generator."""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path
from urllib.request import urlopen

from fpdf import FPDF

from nice_catalog import format_nice_classes


class KoreanPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.font_family_name = "Helvetica"
        self._load_unicode_font()

    def kfont(self, size: int = 11, bold: bool = False) -> None:
        style = "B" if bold else ""
        self.set_font(self.font_family_name, style, size)

    def _bundled_root(self) -> Path:
        root = getattr(sys, "_MEIPASS", "")
        if root:
            return Path(root)
        return Path(__file__).resolve().parent

    def _fonts_dir(self) -> Path:
        root = getattr(sys, "_MEIPASS", "")
        if root:
            return Path(root) / "trademark_checker" / "fonts"
        return Path(__file__).resolve().parent / "fonts"

    def _download_font(self, url: str, dest: Path) -> bool:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(url, timeout=20) as resp:
                payload = resp.read()
            if not payload:
                return False
            dest.write_bytes(payload)
            return True
        except Exception:
            return False

    def _load_unicode_font(self) -> None:
        fonts_dir = self._fonts_dir()
        regular_path = fonts_dir / "NanumGothic-Regular.ttf"
        bold_path = fonts_dir / "NanumGothic-Bold.ttf"

        if not regular_path.exists():
            self._download_font(
                "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf",
                regular_path,
            )
        if not bold_path.exists():
            self._download_font(
                "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf",
                bold_path,
            )

        try:
            if regular_path.exists():
                self.add_font("NanumGothic", "", str(regular_path), uni=True)
                self.font_family_name = "NanumGothic"
                if bold_path.exists():
                    self.add_font("NanumGothic", "B", str(bold_path), uni=True)
                else:
                    self.add_font("NanumGothic", "B", str(regular_path), uni=True)
                return
        except Exception:
            self.font_family_name = "Helvetica"

        regular_font = "C:/Windows/Fonts/malgun.ttf"
        bold_font = "C:/Windows/Fonts/malgunbd.ttf"
        try:
            if os.path.exists(regular_font):
                self.add_font("Malgun", "", regular_font, uni=True)
                self.font_family_name = "Malgun"
                if os.path.exists(bold_font):
                    self.add_font("Malgun", "B", bold_font, uni=True)
                else:
                    self.add_font("Malgun", "B", regular_font, uni=True)
        except Exception:
            self.font_family_name = "Helvetica"


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

        def hit_source_type(hit: dict) -> str:
            mode = str(hit.get("query_mode", "") or "").strip()
            reason = str(hit.get("query_reason", "") or "").strip()
            if "korean_pronunciation" in reason:
                return "korean_pronunciation_variant" if "variant" in reason else "korean_pronunciation"
            if reason.startswith("consonant_swap") or "consonant" in reason:
                return "consonant_group_variant"
            if reason in {"vowel_group", "vowel_ending", "silent_e"} or "vowel" in reason:
                return "vowel_group_variant"
            if mode.startswith("phonetic_") or reason:
                return "phonetic_variant"
            return "exact_text"

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
        prox = item.get("same_class_proximity_override", {}) if isinstance(item.get("same_class_proximity_override"), dict) else {}
        if prox:
            final_type = str(prox.get("final_overlap_type", "") or "").strip()
            prox_level = str(prox.get("proximity_level", "") or "").strip()
            if final_type in {"same_class_near_services", "same_class_core_service_link", "same_class_core_goods_link"}:
                lines.append(
                    "설명: 직접 SC 일치는 없으나 동일 류 내부 업종/서비스 근접성이 있어 stronger overlap으로 반영했습니다."
                )
                if prox_level:
                    lines.append(f"설명: 동일 류 근접도 레벨={prox_level}, 최종 overlap_type={final_type}")
            elif final_type == "same_class_only_weak":
                lines.append("설명: 동일 류이지만 근접 업종 근거가 약해 약한 보조 검토군으로만 반영했습니다.")

        dominant = item.get("dominant_mark_overlap", {}) if isinstance(item.get("dominant_mark_overlap"), dict) else {}
        if dominant.get("shared_dominant_term") and dominant.get("has_prefix_or_suffix_only_difference"):
            strength = str(dominant.get("dominant_overlap_strength", "") or "").strip()
            dominant_term = str(dominant.get("dominant_term", "") or "").strip()
            extra = str(dominant.get("extra_affix", "") or "").strip()
            if dominant_term:
                lines.append(f"설명: 요부 '{dominant_term}'가 공통이며 선행표장에 보조적 요소('{extra}' 등)가 추가된 형태입니다.")
                if strength:
                    lines.append(f"설명: 요부 공통 판단 강도={strength}")
        hit_sources = [src for src in (item.get("hit_sources", []) or []) if isinstance(src, dict)]
        if hit_sources:
            hit_sources.sort(key=lambda r: (-float(r.get("query_weight", 0.0) or 0.0), len(str(r.get("term", "")))))
            top_hits = hit_sources[:3]
            lines.append("검색 경로(발견 근거):")
            for hit in top_hits:
                term = str(hit.get("term", "") or "").strip() or "-"
                q_weight = float(hit.get("query_weight", 0.0) or 0.0)
                q_mode = str(hit.get("query_mode", "") or "").strip() or "-"
                q_path = " / ".join([str(x) for x in (hit.get("query_path", []) or []) if str(x or "").strip()][:6]) or "-"
                lines.append(
                    f"- {hit_source_type(hit)} | term {term} | w {q_weight:.2f} | mode {q_mode} | path {q_path}"
                )
        risk = item.get("risk_path_analysis", {}) or {}
        phonetic = risk.get("phonetic_analysis", {}) or item.get("phonetic_analysis", {}) or {}
        exact_override = item.get("exact_override", {}) if isinstance(item.get("exact_override"), dict) else {}
        if exact_override.get("should_override"):
            lines.append("배지: 완전 동일표장 | 정규화 기준 완전 일치 | exact override 적용")
            lines.append("완전 동일표장입니다(대소문자/공백/기호 정규화 기준).")
            original_type = str(exact_override.get("original_overlap_type", item.get("overlap_type_original", "")) or "").strip()
            final_type = str(exact_override.get("final_overlap_type", item.get("overlap_type", "")) or "").strip()
            original_score = int(exact_override.get("original_product_similarity_score", item.get("product_similarity_score_original", 0)) or 0)
            adjusted_score = int(exact_override.get("adjusted_product_similarity_score", item.get("product_similarity_score", 0)) or 0)
            if original_type and final_type:
                lines.append(f"설명: item-level 정보 부족으로 {original_type}였으나, 동일표장 우선 원칙으로 {final_type}로 상향했습니다.")
            if original_score or adjusted_score:
                lines.append(f"설명: 지정상품/서비스 텍스트 근접도 기반으로 상품점수 {original_score} → {adjusted_score}로 보정했습니다.")
            lines.append("발음 분석은 보조 설명이며 최종 위험도를 낮추는 근거로 사용하지 않습니다.")
        if phonetic:
            best_score = phonetic.get("best_path_score", phonetic.get("phonetic_similarity", 0))
            best_label = phonetic.get("best_path_label", "")
            hangul = phonetic.get("hangul_pronunciation_similarity", 0)
            breakdown = risk.get("risk_paths", []) or []
            if exact_override.get("should_override"):
                lines.append(
                    f"참고(발음): 유사도 {phonetic.get('phonetic_similarity', 0)}% | 최고 경로 {best_score}% {best_label} | 한글 호칭 {hangul}%"
                )
            else:
                lines.append(
                    f"발음 유사도 {phonetic.get('phonetic_similarity', 0)}% | 최고 경로 {best_score}% {best_label} | 한글 호칭 {hangul}%"
                )
            hangul_onset = int(phonetic.get("onset_similarity", 0) or 0)
            hangul_vowel = int(phonetic.get("vowel_similarity", 0) or 0)
            hangul_coda = int(phonetic.get("coda_similarity", 0) or 0)
            hangul_best_path = phonetic.get("hangul_best_path", []) or []
            hangul_pair = phonetic.get("hangul_best_pair", {}) or {}
            if int(hangul or 0) >= 70 and hangul_best_path and hangul_pair:
                lines.append(f"한글 호칭 근거: {', '.join([str(x) for x in hangul_best_path[:3]])}")
            if hangul_onset >= 80 and hangul_vowel < 70:
                lines.append("설명: 초성은 유사하나 중성이 달라 호칭이 완전히 동일하다고 보긴 어렵습니다.")
            elif hangul_vowel >= 85 and hangul_coda < 70:
                lines.append("설명: 중성까지 유사하고 종성에서 약화/차이가 발생합니다.")
            elif int(hangul or 0) >= 85 and (hangul_pair.get("source_origin") == "roman" or hangul_pair.get("target_origin") == "roman"):
                sp = hangul_pair.get("source_pronunciation", "")
                tp = hangul_pair.get("target_pronunciation", "")
                if sp and tp:
                    lines.append(f"설명: 영문 음역 시 한국어 호칭이 거의 동일합니다({sp} ↔ {tp}).")
            for row in breakdown[:3]:
                lines.append(
                    f"- {row.get('path_label', '-')}: 발음 {row.get('path_score', 0)}% / 혼동 {row.get('path_confusion', 0)}% ({row.get('registration_outlook', '-')})"
                )
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
        _write_lines(pdf, width, [f"[WARN] SEARCH FAILED: {payload.get('search_error_msg', 'Unknown Error')}"])
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
        _write_lines(pdf, width, ["[WARN] 주요 거절 사유: 단어 자체의 식별력 부족 (Stage 1)"])
        pdf.set_text_color(0, 0, 0)
        pdf.kfont(10)
        _write_lines(pdf, width, [f"선행상표와 상관없이, 상표법 제33조에 의거하여 단어 자체가 공익상 특정인에게 독점시킬 수 없는 성질을 가지고 있습니다. (상한선: {stage1_cap}%)"])
        pdf.ln(1)
    elif is_stage2_main:
        pdf.kfont(11, bold=True)
        pdf.set_text_color(200, 0, 0)
        _write_lines(pdf, width, ["[WARN] 주요 거절 사유: 선행상표와의 충돌 위험 (Stage 2)"])
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
    _write_lines(
        pdf,
        width,
        [
            "본 결과는 AI 자동 분석 참고용이며, 최종 판단은 반드시 변리사와 상담 하세요.",
        ],
    )
    return bytes(pdf.output())
