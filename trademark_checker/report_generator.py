"""PDF 보고서를 생성한다."""

from __future__ import annotations

import datetime as dt
import os

from fpdf import FPDF


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


def _safe_text(value: str) -> str:
    return (
        value.replace("\n", " ")
        .replace("⛔", "불가")
        .replace("✅", "확인")
        .replace("⚠️", "주의")
        .replace("⚠", "주의")
        .replace("→", "->")
        .strip()
    )


def _write_lines(pdf: KoreanPDF, content_width: float, lines: list[str]) -> None:
    for line in lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(content_width, 7, _safe_text(line))


def _render_single_report(pdf: KoreanPDF, content_width: float, payload: dict, title: str | None = None) -> None:
    if title:
        pdf.kfont(13, bold=True)
        pdf.cell(0, 8, _safe_text(title), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    summary_rows = [
        ("구체 상품", payload.get("specific_product", "-") or "-"),
        ("상품군", ", ".join(payload.get("selected_classes", [])) or "-"),
        ("유사군 코드", ", ".join(payload.get("selected_codes", [])) or "-"),
        ("등록 가능성", f'{payload.get("score", 0)}% - {payload.get("score_label", "-")}'),
        ("식별력", payload.get("distinctiveness", "-")),
        (
            "검토 선행상표",
            f'{payload.get("prior_count", 0)}건 / 전체 {payload.get("total_prior_count", payload.get("prior_count", 0))}건',
        ),
    ]

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "검토 요약", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for label, value in summary_rows:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(content_width, 7, _safe_text(f"{label}: {value}"))
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "식별력 판단", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    distinctiveness = payload.get("distinctiveness_analysis", {})
    _write_lines(
        pdf,
        content_width,
        [distinctiveness.get("summary", payload.get("distinctiveness", "-"))]
        + [f"- {reason}" for reason in distinctiveness.get("reasons", [])],
    )
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "점수 산정 해설", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    score_explanation = payload.get("score_explanation", {})
    _write_lines(
        pdf,
        content_width,
        [
            (
                f"최종 점수 {payload.get('score', 0)}% "
                f"(원점수 {score_explanation.get('raw_score', payload.get('score', 0))}%)"
            ),
            score_explanation.get("summary", "상품 유사성 필터와 식별력 축을 분리해 점수를 산정했습니다."),
        ]
        + [f"- {note}" for note in score_explanation.get("notes", [])],
    )
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "상품 유사성 검토 결과", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    product_analysis = payload.get("product_similarity_analysis", {})
    bucket_counts = product_analysis.get("bucket_counts", {})
    _write_lines(
        pdf,
        content_width,
        [
            product_analysis.get("summary", "-"),
            (
                f"동일 유사군코드 {bucket_counts.get('same_code', 0)}건 / "
                f"동일 류 {bucket_counts.get('same_class', 0)}건 / "
                f"타 류 예외군 {bucket_counts.get('exception', 0)}건 / "
                f"검토 제외 {bucket_counts.get('excluded', 0)}건"
            ),
        ],
    )
    if product_analysis.get("exclusion_reason_summary"):
        _write_lines(pdf, content_width, [product_analysis["exclusion_reason_summary"]])
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "표장 유사성 검토 결과", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _write_lines(pdf, content_width, [payload.get("mark_similarity_analysis", {}).get("summary", "-")])
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "혼동 가능성 종합", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    _write_lines(pdf, content_width, [payload.get("confusion_analysis", {}).get("summary", "-")])
    pdf.ln(2)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "주요 선행상표", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    top_prior = payload.get("top_prior", [])
    if not top_prior:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(content_width, 7, "상품 유사성 필터를 통과한 주요 선행상표가 없습니다.")
    else:
        for index, item in enumerate(top_prior, start=1):
            _write_lines(
                pdf,
                content_width,
                [
                    (
                        f"{index}. {item.get('trademarkName', '-')}"
                        f" | {item.get('registerStatus', '-')}"
                        f" | 류 {item.get('classificationCode', '-')}"
                        f" | 혼동 위험 {item.get('confusion_score', 0)}%"
                    ),
                    (
                        f"상품군 판단: {item.get('product_similarity_label', '-')}"
                        f" | 표장 {item.get('mark_similarity', item.get('similarity', 0))}%"
                        f" | 외관 {item.get('appearance_similarity', item.get('similarity', 0))}%"
                        f" | 호칭 {item.get('phonetic_similarity', 0)}%"
                        f" | 관념 {item.get('conceptual_similarity', 0)}%"
                    ),
                    f"출원인: {item.get('applicantName', '-')}",
                ],
            )
            pdf.ln(1)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "개선 방안", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for option in payload.get("name_options", []):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(content_width, 7, _safe_text(f"상표명 대안: {option['name']} -> 예상 {option['expected_score']}%"))
    for option in payload.get("scope_options", []):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            content_width,
            7,
            _safe_text(f"{option['title']}: {option['description']} (예상 {option['expected_score']}%)"),
        )
    for option in payload.get("class_options", []):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            content_width,
            7,
            _safe_text(f"{option['title']}: {option['description']} (예상 {option['expected_score']}%)"),
        )
    pdf.ln(4)


def generate_report_pdf(payload: dict) -> bytes:
    pdf = KoreanPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    content_width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.kfont(18, bold=True)
    pdf.cell(0, 12, "상표등록 가능성 검토 서비스", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    pdf.cell(0, 8, f"작성일: {dt.date.today().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.kfont(12, bold=True)
    pdf.cell(0, 8, "기본 정보", new_x="LMARGIN", new_y="NEXT")
    pdf.kfont(10)
    for label, value in [
        ("상표명", payload.get("trademark_name", "-")),
        ("상표 유형", payload.get("trademark_type", "-")),
        ("선택 상품군", ", ".join(payload.get("selected_classes", [])) or "-"),
    ]:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(content_width, 7, _safe_text(f"{label}: {value}"))
    pdf.ln(2)

    field_reports = payload.get("field_reports")
    if field_reports:
        pdf.kfont(12, bold=True)
        pdf.cell(0, 8, f"상품군별 판단 결과: {len(field_reports)}건", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for index, report in enumerate(field_reports, start=1):
            _render_single_report(pdf, content_width, report, title=f"{index}. {report.get('field_label', '상품군')}")
            if index < len(field_reports):
                pdf.add_page()
    else:
        _render_single_report(pdf, content_width, payload)

    pdf.kfont(8)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(content_width, 5, "본 결과는 AI 분석 참고용이며 최종 판단은 변리사 상담을 권장합니다.")
    return bytes(pdf.output())
