import base64
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st
try:
    from resource_paths import docs_dir as _docs_dir
except ImportError:
    from .resource_paths import docs_dir as _docs_dir

from improvement import get_improvements
from kipris_api import (
    build_kipris_search_plan,
    dedupe_search_candidates,
    enrich_search_results_with_item_details,
    search_all_pages,
)
from search_health import classify_query, summarize_health
from nice_catalog import (
    build_selection_summary,
    build_scope_session_state,
    can_continue_to_code_selection,
    can_enter_subgroup_stage,
    can_run_review,
    derive_selected_scope,
    find_group,
    format_nice_classes,
    get_group_cards,
    get_groups,
    is_subgroup_selection_complete,
    should_render_subgroup_stage,
    subgroup_to_field,
    validate_catalog_coverage,
)
from goods_scope import normalize_selected_input
from report_generator import generate_report_pdf
from scoring import evaluate_registration, get_score_band, similarity_percent, strip_html
from search_mapper import get_category_suggestions
from similarity_code_db import get_all_codes_by_class, get_similarity_codes


MAX_SELECTED_SUBGROUPS = 5
AURI_IMAGE_PATH = _docs_dir() / "아우리.jpg"


@st.cache_data(show_spinner=False)
def _load_image_b64(path: str) -> tuple[str, str] | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    suffix = file_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".png":
        mime = "image/png"
    else:
        return None
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return mime, encoded


def render_auri(size_px: int = 220) -> None:
    payload = _load_image_b64(str(AURI_IMAGE_PATH))
    if not payload:
        return
    mime, encoded = payload
    st.markdown(
        f"""
        <div style="width:100%; display:flex; justify-content:center; margin:12px 0 18px 0;">
            <div style="background:#FFFFFF; border-radius:18px; padding:12px 16px; box-shadow:0 2px 10px rgba(33,150,243,0.12);">
                <img src="data:{mime};base64,{encoded}" style="width:{int(size_px)}px; height:auto; display:block;" />
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reset_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def get_result_style(score: int) -> tuple[str, str, str]:
    if score >= 90:
        return "result-90", "", "등록 가능성 매우 높음"
    if score >= 70:
        return "result-70", "", "등록 가능성 높음"
    if score >= 50:
        return "result-50", "", "주의 필요 - 전문가 상담 권장"
    if score >= 30:
        return "result-30", "", "등록 어려움 - 변리사 상담 필요"
    return "result-0", "⛔", "등록 불가 가능성 높음"


def normalize_result(item: dict, trademark_name: str) -> dict:
    name = strip_html(item.get("trademarkName", item.get("trademark_name", "알 수 없음")))
    similarity = similarity_percent(trademark_name, name)
    return {
        "trademarkName": name,
        "applicationNumber": item.get("applicationNumber", item.get("application_number", "-")),
        "applicationDate": item.get("applicationDate", item.get("application_date", "-")),
        "registerStatus": item.get("registerStatus", item.get("registrationStatus", item.get("status", "-"))),
        "applicantName": strip_html(item.get("applicantName", item.get("applicant", "-"))),
        "classificationCode": item.get("classificationCode", item.get("class", "-")),
        "similarity": similarity,
    }


def deduplicate_results(items: list[dict], trademark_name: str) -> list[dict]:
    seen = set()
    results = []
    for item in items:
        normalized = normalize_result(item, trademark_name)
        key = (normalized["applicationNumber"], normalized["trademarkName"])
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    results.sort(key=lambda row: row["similarity"], reverse=True)
    return results


def _hit_source_type(hit: dict) -> str:
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


def _safe_inline_text(value: object) -> str:
    text = strip_html(str(value or ""))
    return text.replace("<", " ").replace(">", " ").replace("\n", " ").strip()


def _format_hit_sources_brief(hit_sources: list[dict], limit: int = 3) -> str:
    rows = []
    for hit in (hit_sources or []):
        if not isinstance(hit, dict):
            continue
        term = _safe_inline_text(hit.get("term", ""))
        if not term:
            continue
        rows.append(
            {
                "type": _hit_source_type(hit),
                "term": term,
                "w": float(hit.get("query_weight", 0.0) or 0.0),
                "path": [str(x) for x in (hit.get("query_path", []) or []) if str(x or "").strip()],
            }
        )
    if not rows:
        return "-"
    rows.sort(key=lambda r: (-r["w"], len(r["term"])))
    parts = []
    for r in rows[:limit]:
        path = " / ".join(r["path"][:3]) if r["path"] else "-"
        parts.append(f'{r["type"]} | {r["term"]} | w={r["w"]:.2f} | path={path}')
    return " ; ".join(parts)


def _format_exact_override_badges(item: dict) -> str:
    exact_override = item.get("exact_override", {}) if isinstance(item.get("exact_override"), dict) else {}
    if not exact_override.get("should_override"):
        return ""
    return "완전 동일표장 | 정규화 기준 완전 일치 | exact override 적용"


def _format_exact_override_details(item: dict) -> str:
    exact_override = item.get("exact_override", {}) if isinstance(item.get("exact_override"), dict) else {}
    if not exact_override.get("should_override"):
        return ""
    original_type = _safe_inline_text(exact_override.get("original_overlap_type", item.get("overlap_type_original", "")))
    final_type = _safe_inline_text(exact_override.get("final_overlap_type", item.get("overlap_type", "")))
    original_score = float(exact_override.get("original_product_similarity_score", item.get("product_similarity_score_original", 0)) or 0)
    adjusted_score = float(exact_override.get("adjusted_product_similarity_score", item.get("product_similarity_score", 0)) or 0)
    reason = _safe_inline_text(exact_override.get("override_reason", ""))
    extra = f"overlap {original_type} → {final_type} | 상품점수 {int(original_score)} → {int(adjusted_score)}"
    if reason:
        extra = extra + f" | 사유: {reason}"
    return extra


def _build_hit_source_rows(item: dict) -> list[dict]:
    rows = []
    for hit in (item.get("hit_sources", []) or []):
        if not isinstance(hit, dict):
            continue
        rows.append(
            {
                "상표명": strip_html(item.get("trademarkName", "")),
                "출원번호": str(item.get("applicationNumber", "")),
                "hit_source": _hit_source_type(hit),
                "term": _safe_inline_text(hit.get("term", "")),
                "query_weight": float(hit.get("query_weight", 0.0) or 0.0),
                "query_mode": str(hit.get("query_mode", "")),
                "query_reason": str(hit.get("query_reason", "")),
                "query_path": " / ".join([str(x) for x in (hit.get("query_path", []) or []) if str(x or "").strip()][:6]) or "-",
                "class_no": str(hit.get("query_class_no", "")),
                "code": str(hit.get("query_code", "")),
            }
        )
    rows.sort(key=lambda r: (-float(r.get("query_weight", 0.0) or 0.0), r.get("hit_source", ""), r.get("term", "")))
    return rows


def field_key(field: dict) -> str:
    return field.get("field_id", f'{field.get("class_no", "")}|{field.get("description", "")}')


def field_widget_key(field: dict) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", field_key(field))


def field_label(field: dict) -> str:
    return f'{field.get("description", "")} ({field.get("class_no", "")})'


def current_selected_fields() -> list[dict]:
    return st.session_state.get("selected_fields", [])


def reset_analysis_state() -> None:
    st.session_state.search_results = None
    st.session_state.score = None
    st.session_state.analysis = None
    st.session_state.search_source = ""


def get_field_inputs() -> dict:
    return st.session_state.setdefault("field_inputs", {})


def ensure_field_input(field: dict) -> dict:
    inputs = get_field_inputs()
    key = field_key(field)
    if key not in inputs:
        inputs[key] = {"specific_product": ""}
    return inputs[key]


def get_field_input(field: dict) -> dict:
    return ensure_field_input(field)


def add_selected_field(field: dict) -> bool:
    selected_fields = current_selected_fields()
    key = field_key(field)
    if any(field_key(item) == key for item in selected_fields):
        return True
    if len(selected_fields) >= 3:
        st.session_state.selection_error = "상품군은 최대 3개까지 선택할 수 있습니다."
        return False
    selected_fields.append(
        {
            "class_no": field.get("class_no", field.get("류", "")),
            "description": field.get("description", field.get("설명", "")),
            "example": field.get("example", field.get("예시", "")),
        }
    )
    ensure_field_input(selected_fields[-1])
    st.session_state.selection_error = ""
    reset_analysis_state()
    return True


def remove_selected_field(target_key: str) -> None:
    st.session_state.selected_fields = [
        field for field in current_selected_fields() if field_key(field) != target_key
    ]
    inputs = get_field_inputs()
    inputs.pop(target_key, None)
    reset_analysis_state()


def update_field_product(field: dict, product: str) -> None:
    config = ensure_field_input(field)
    if config["specific_product"] != product:
        config["specific_product"] = product
        sync_nice_selection_state()
        reset_analysis_state()


def toggle_field_code(field: dict, code: str) -> None:
    config = ensure_field_input(field)
    selected_codes = list(config.get("selected_codes", []))
    if code in selected_codes:
        selected_codes.remove(code)
    else:
        selected_codes.append(code)
    config["selected_codes"] = selected_codes
    reset_analysis_state()


def field_ready(field: dict) -> bool:
    return bool(field)


def all_fields_ready() -> bool:
    selected_fields = current_selected_fields()
    return bool(selected_fields) and all(field_ready(field) for field in selected_fields)


# build_report_payload is defined below (single active definition)


def field_widget_key(field: dict) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_]+", "_", field_key(field))


def field_label(field: dict) -> str:
    class_summary = format_nice_classes(field.get("nice_classes", [])) or field.get("class_no", "")
    return f'{field.get("description", "")} ({class_summary})'


def sync_nice_selection_state() -> None:
    selected_fields = current_selected_fields()
    specific_products = {
        field_key(field): get_field_input(field).get("specific_product", "")
        for field in selected_fields
    }
    scope_state = build_scope_session_state(
        selected_kind=st.session_state.get("selected_kind"),
        selected_group_id=st.session_state.get("selected_group_id", st.session_state.get("selected_group")),
        selected_group_label=st.session_state.get("selected_group_label"),
        selected_fields=selected_fields,
        specific_products=specific_products,
        code_lookup=get_similarity_codes,
        current_substep=st.session_state.get("step_scope_sub", st.session_state.get("step2_substep", "group")),
    )
    st.session_state.selected_groups = scope_state["selected_groups"]
    st.session_state.selected_subgroups = scope_state["selected_subgroups"]
    st.session_state.selected_subgroup_ids = scope_state["selected_subgroup_ids"]
    st.session_state.selected_subgroup_labels = scope_state["selected_subgroup_labels"]
    st.session_state.derived_nice_classes = scope_state["derived_nice_classes"]
    st.session_state.derived_similarity_codes = scope_state["derived_similarity_codes"]
    st.session_state.candidate_similarity_codes = scope_state.get("candidate_similarity_codes", [])
    st.session_state.similarity_match_details = scope_state.get("similarity_match_details", [])
    st.session_state.subgroup_keywords = scope_state["subgroup_keywords"]
    st.session_state.search_terms_for_prior_marks = scope_state["search_terms_for_prior_marks"]
    st.session_state.selected_scope_summary = scope_state["selected_scope_summary"]
    st.session_state.selected_nice_classes = scope_state["derived_nice_classes"]
    st.session_state.recommended_similarity_codes = scope_state["derived_similarity_codes"]
    st.session_state.selected_similarity_codes = scope_state["derived_similarity_codes"]
    st.session_state.selected_keywords = scope_state["subgroup_keywords"]
    st.session_state.selected_group_id = scope_state["selected_group_id"]
    st.session_state.selected_group_label = scope_state["selected_group_label"]
    st.session_state.selected_group = scope_state["selected_group_id"]
    st.session_state.step_scope_sub = scope_state["step_scope_sub"]
    st.session_state.step2_substep = (
        "subgroup" if scope_state["step_scope_sub"] in {"subgroup", "review_ready"} else "group"
    )
    if selected_fields:
        st.session_state.selected_kind = selected_fields[0].get("kind", st.session_state.get("selected_kind"))


def current_specific_products(fields: list[dict] | None = None) -> dict[str, str]:
    selected_fields = fields or current_selected_fields()
    return {
        field_key(field): get_field_input(field).get("specific_product", "")
        for field in selected_fields
    }


def derive_scope_state(fields: list[dict] | None = None) -> dict:
    selected_fields = fields or current_selected_fields()
    return build_scope_session_state(
        selected_kind=st.session_state.get("selected_kind"),
        selected_group_id=st.session_state.get("selected_group_id", st.session_state.get("selected_group")),
        selected_group_label=st.session_state.get("selected_group_label"),
        selected_fields=selected_fields,
        specific_products=current_specific_products(selected_fields),
        code_lookup=get_similarity_codes,
        current_substep=st.session_state.get("step_scope_sub", st.session_state.get("step2_substep", "group")),
    )


def derive_field_scope(field: dict) -> dict:
    return derive_selected_scope(
        selected_kind=field.get("kind", st.session_state.get("selected_kind")),
        selected_fields=[field],
        specific_products={field_key(field): get_field_input(field).get("specific_product", "")},
        code_lookup=get_similarity_codes,
    )


def set_selected_kind(kind: str) -> None:
    selected_fields = current_selected_fields()
    if selected_fields and any(field.get("kind") != kind for field in selected_fields):
        st.session_state.selection_error = "제품과 서비스는 한 번에 섞어서 분석할 수 없습니다. 기존 선택을 해제한 뒤 전환하세요."
        return
    st.session_state.selected_kind = kind
    st.session_state.step_scope_sub = "group"
    st.session_state.step2_substep = "group"
    if st.session_state.get("selected_group_id", st.session_state.get("selected_group")):
        available_groups = {group["group_id"] for group in get_groups(kind)}
        selected_group_id = st.session_state.get("selected_group_id", st.session_state.get("selected_group"))
        if selected_group_id not in available_groups:
            st.session_state.selected_group_id = None
            st.session_state.selected_group_label = ""
            st.session_state.selected_group = None
    st.session_state.selection_error = ""
    reset_analysis_state()


def clear_selected_fields() -> None:
    st.session_state.selected_fields = []
    st.session_state.field_inputs = {}
    sync_nice_selection_state()
    reset_analysis_state()


def set_selected_group(group_id: str) -> None:
    active_group = find_group(st.session_state.get("selected_kind"), group_id)
    if st.session_state.get("selected_group_id", st.session_state.get("selected_group")) != group_id:
        st.session_state.selected_group_id = group_id
        st.session_state.selected_group_label = active_group.get("group_label", "") if active_group else ""
        st.session_state.selected_group = group_id
        st.session_state.step_scope_sub = "group"
        st.session_state.step2_substep = "group"
        clear_selected_fields()
    else:
        st.session_state.selected_group_label = active_group.get("group_label", "") if active_group else ""
        st.session_state.step_scope_sub = "group"
        st.session_state.step2_substep = "group"
    st.session_state.selection_error = ""


def add_selected_field(field: dict) -> bool:
    field = subgroup_to_field(field) if field.get("subgroup_id") else field
    selected_fields = current_selected_fields()
    key = field_key(field)
    if any(field_key(item) == key for item in selected_fields):
        return True
    if selected_fields and any(item.get("kind") != field.get("kind") for item in selected_fields):
        st.session_state.selection_error = "제품과 서비스는 한 번에 섞어서 선택할 수 없습니다."
        return False
    if len(selected_fields) >= MAX_SELECTED_SUBGROUPS:
        st.session_state.selection_error = f"상품군은 최대 {MAX_SELECTED_SUBGROUPS}개까지 선택할 수 있습니다."
        return False
    selected_fields.append(field)
    ensure_field_input(field)
    st.session_state.selected_kind = field.get("kind", st.session_state.get("selected_kind"))
    st.session_state.selection_error = ""
    sync_nice_selection_state()
    reset_analysis_state()
    return True


def remove_selected_field(target_key: str) -> None:
    st.session_state.selected_fields = [
        field for field in current_selected_fields() if field_key(field) != target_key
    ]
    inputs = get_field_inputs()
    inputs.pop(target_key, None)
    sync_nice_selection_state()
    reset_analysis_state()


def build_report_payload() -> dict:
    analysis = st.session_state.get("analysis") or {}
    field_reports = []
    for report in analysis.get("field_reports", []):
        field = report.get("field", {})
        field_reports.append(
            {
                "field_label": field_label(field),
                "specific_product": report.get("specific_product", ""),
                "selected_kind": report.get("selected_kind", field.get("kind")),
                "selected_group_id": report.get("selected_group_id", field.get("group_id")),
                "selected_groups": report.get("selected_groups", [field.get("group_label", "")]),
                "selected_subgroup_ids": report.get("selected_subgroup_ids", [field.get("field_id", "")]),
                "selected_subgroups": report.get("selected_subgroups", [field.get("description", "")]),
                "selected_nice_classes": report.get("selected_nice_classes", field.get("nice_classes", [])),
                "derived_nice_classes": report.get("selected_nice_classes", field.get("nice_classes", [])),
                "selected_similarity_codes": report.get("selected_similarity_codes", report.get("selected_codes", [])),
                "derived_similarity_codes": report.get("selected_similarity_codes", report.get("selected_codes", [])),
                "selected_keywords": report.get("selected_keywords", field.get("keywords", [])),
                "subgroup_keywords": report.get("selected_keywords", field.get("keywords", [])),
                "selected_classes": [format_nice_classes(field.get("nice_classes", [])) or field_label(field)],
                "selected_codes": report.get("selected_codes", []),
                # ── 핵심 유사군코드 3종 (보고서 디버그용) ──────────────────────────
                "selected_primary_codes": report.get("selected_primary_codes", []),
                "selected_related_codes": report.get("selected_related_codes", []),
                "selected_retail_codes": report.get("selected_retail_codes", []),
                # ── 검색 파이프라인 디버그 ──────────────────────────────────────
                "executed_queries": report.get("executed_queries", []),
                "search_plan": report.get("search_plan", []),
                "overlap_type_analysis": report.get("overlap_type_analysis", {}),
                "score": report.get("score", 0),
                "score_label": report.get("band", {}).get("label", "-"),
                "distinctiveness": report.get("distinctiveness", "-"),
                "absolute_risk_level": report.get("absolute_risk_level", "none"),
                "absolute_refusal_bases": report.get("absolute_refusal_bases", []),
                "distinctiveness_score": report.get("distinctiveness_score", 0),
                "absolute_probability_cap": report.get("absolute_probability_cap", 95),
                "acquired_distinctiveness_needed": report.get("acquired_distinctiveness_needed", False),
                "prior_count": report.get("prior_count", 0),
                "total_prior_count": report.get("total_prior_count", 0),
                "top_prior": report.get("top_prior", []),
                "distinctiveness_analysis": report.get("distinctiveness_analysis", {}),
                "absolute_refusal_analysis": report.get("absolute_refusal_analysis", {}),
                "product_similarity_analysis": report.get("product_similarity_analysis", {}),
                "mark_similarity_analysis": report.get("mark_similarity_analysis", {}),
                "confusion_analysis": report.get("confusion_analysis", {}),
                "score_explanation": report.get("score_explanation", {}),
                "stage1_absolute_cap": report.get("stage1_absolute_cap", 95),
                "stage2_relative_cap_adjusted": report.get("stage2_relative_cap_adjusted", report.get("score", 0)),
                "filtered_prior_count": report.get("filtered_prior_count", 0),
                "excluded_prior_count": report.get("excluded_prior_count", 0),
                "actual_risk_prior_count": report.get("actual_risk_prior_count", 0),
                "direct_score_prior_count": report.get("direct_score_prior_count", 0),
                "historical_reference_count": report.get("historical_reference_count", 0),
                "reference_summary": report.get("reference_summary", ""),
                "name_options": [
                    {"name": item["name"], "expected_score": item["score"]}
                    for item in report.get("improvements", {}).get("name_suggestions", [])
                ],
                "scope_options": [
                    {
                        "title": item["description"],
                        "description": item["reason"],
                        "expected_score": item["expected_score"],
                    }
                    for item in report.get("improvements", {}).get("code_suggestions", [])
                ],
                "class_options": [
                    {
                        "title": item["description"],
                        "description": item["reason"],
                        "expected_score": item["expected_score"],
                    }
                    for item in report.get("improvements", {}).get("class_suggestions", [])
                ],
            }
        )
    return {
        "trademark_name": st.session_state.get("trademark_name", ""),
        "trademark_type": st.session_state.get("trademark_type", ""),
        "selected_kind": st.session_state.get("selected_kind"),
        "selected_group_id": st.session_state.get("selected_group_id"),
        "selected_group_label": st.session_state.get("selected_group_label", ""),
        "selected_groups": st.session_state.get("selected_groups", []),
        "selected_subgroup_ids": st.session_state.get("selected_subgroup_ids", []),
        "selected_subgroup_labels": st.session_state.get("selected_subgroup_labels", []),
        "selected_subgroups": [
            field.get("description", "")
            for field in current_selected_fields()
            if field.get("description")
        ],
        "selected_nice_classes": st.session_state.get("selected_nice_classes", []),
        "derived_nice_classes": st.session_state.get("derived_nice_classes", []),
        "selected_similarity_codes": st.session_state.get("selected_similarity_codes", []),
        "derived_similarity_codes": st.session_state.get("derived_similarity_codes", []),
        "selected_keywords": st.session_state.get("selected_keywords", []),
        "subgroup_keywords": st.session_state.get("subgroup_keywords", []),
        "search_terms_for_prior_marks": st.session_state.get("search_terms_for_prior_marks", []),
        "selected_classes": [format_nice_classes(st.session_state.get("selected_nice_classes", []))],
        # 전체 필드 선택 코드 집계 (PDF Basic Info 섹션용)
        "selected_primary_codes": list({
            code
            for r in analysis.get("field_reports", [])
            for code in r.get("selected_primary_codes", [])
        }),
        "selected_related_codes": list({
            code
            for r in analysis.get("field_reports", [])
            for code in r.get("selected_related_codes", [])
        }),
        "selected_retail_codes": list({
            code
            for r in analysis.get("field_reports", [])
            for code in r.get("selected_retail_codes", [])
        }),
        "field_reports": field_reports,
    }


def render_step2() -> None:
    coverage = validate_catalog_coverage()
    selected_kind = st.session_state.get("selected_kind")
    selected_group = st.session_state.get("selected_group")
    step2_substep = st.session_state.get("step2_substep", "group")

    st.markdown(f"## '{st.session_state.trademark_name}' 상표의 지정상품 범위를 선택하세요")
    st.markdown("### 분류 1 -> 분류 2 -> 구체상품군 순서로 단계별로 선택합니다")
    st.markdown(
        """
    <div class="tip-box">
    <b>모바일형 단계 선택</b><br>
    분류 2에서는 짧은 카테고리만 보여주고,<br>
    구체상품군은 다음 단계에서만 선택하게 구성합니다.
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"엑셀 기준 확인: goods {coverage['goods_class_count']}개 / services {coverage['services_class_count']}개"
    )

    st.markdown("### 1. 분류 1 선택")
    kind_col1, kind_col2 = st.columns(2)
    with kind_col1:
        if st.button("제품\n(제품, 브랜드)", use_container_width=True, key="nice_kind_goods"):
            set_selected_kind("goods")
            st.rerun()
    with kind_col2:
        if st.button("서비스\n(상호, 서비스)", use_container_width=True, key="nice_kind_services"):
            set_selected_kind("services")
            st.rerun()

    if selected_kind:
        st.markdown(f"현재 선택: **{'제품' if selected_kind == 'goods' else '서비스'}**")
        st.markdown("### 2. 분류 2 선택")
        st.caption("긴 니스류 설명은 숨기고, 짧은 카테고리명만 보여줍니다")

        group_cards = get_group_cards(selected_kind)
        group_cols = st.columns(3)
        for index, group_card in enumerate(group_cards):
            with group_cols[index % 3]:
                active = selected_group == group_card["group_id"]
                st.markdown(
                    f"""
                    <div class="category-card">
                        <b>{group_card['group_label']}</b><br>
                        <small style="color:#546E7A;">{group_card.get('group_hint', '')}</small><br>
                        <small style="color:#546E7A;">연결 니스류: {group_card['nice_class_summary']}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "선택 중" if active else "카테고리 선택",
                    key=f"nice_group_{group_card['group_id']}",
                    use_container_width=True,
                ):
                    set_selected_group(group_card["group_id"])
                    st.session_state.step2_substep = "group"
                    st.rerun()
    else:
        st.info("먼저 제품 또는 서비스를 선택하세요.")

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if step2_substep == "subgroup" and can_enter_subgroup_stage(selected_kind, selected_group):
        active_group = find_group(selected_kind, selected_group)
        if active_group:
            st.markdown("---")
            st.markdown("### 3. 구체상품군 선택")
            st.caption("선택한 카테고리에 해당하는 상품군을 선택하세요")
            st.markdown(f"선택 카테고리: **{active_group['group_label']}**")
            st.caption(
                f"{active_group.get('group_hint', '')} | 연결 니스류: {format_nice_classes(active_group.get('classes', []))}"
            )

            subgroup_cols = st.columns(2)
            for index, subgroup in enumerate(active_group.get("subgroups", [])):
                subgroup_payload = subgroup_to_field(
                    {
                        "kind": selected_kind,
                        "group_id": active_group["group_id"],
                        "group_label": active_group["group_label"],
                        "group_hint": active_group.get("group_hint", ""),
                        **subgroup,
                    }
                )
                already_selected = any(
                    field_key(field) == field_key(subgroup_payload)
                    for field in current_selected_fields()
                )
                with subgroup_cols[index % 2]:
                    st.markdown(
                        f"""
                        <div class="category-card">
                            <b>{subgroup['subgroup_label']}</b><br>
                            <small style="color:#546E7A;">연결 니스류: {format_nice_classes(subgroup.get('nice_classes', []))}</small><br>
                            <small style="color:#546E7A;">추천 유사군코드: {', '.join(subgroup.get('similarity_codes', [])) or '-'}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "선택 해제" if already_selected else "상품군 선택",
                        key=f"nice_subgroup_{subgroup['subgroup_id']}",
                    ):
                        if already_selected:
                            remove_selected_field(field_key(subgroup_payload))
                        else:
                            add_selected_field(subgroup_payload)
                        st.rerun()

    if current_selected_fields():
        summary = build_selection_summary(
            selected_kind=st.session_state.get("selected_kind"),
            selected_fields=current_selected_fields(),
        )
        st.markdown("---")
        st.markdown("### 선택 결과 요약")
        st.markdown(f"선택 분류 1: **{summary['selected_kind_label']}**")
        st.markdown(f"선택 분류 2: **{', '.join(summary['selected_groups'])}**")
        st.markdown(f"선택 상품군: **{', '.join(summary['selected_subgroups'])}**")
        st.markdown(f"연결 니스류: **{summary['selected_nice_classes_text']}**")
        if st.session_state.get("recommended_similarity_codes"):
            st.markdown(
                f"연결 추천 유사군코드: **{', '.join(st.session_state['recommended_similarity_codes'])}**"
            )

    prev_col, next_col = st.columns(2)
    with prev_col:
        if step2_substep == "subgroup":
            if st.button("이전 단계: 카테고리 선택", use_container_width=True, key="nice_back_to_group"):
                st.session_state.step2_substep = "group"
                st.rerun()
        else:
            if st.button("이전 단계", use_container_width=True, key="nice_back_step1"):
                st.session_state.step = 1
                st.rerun()
    with next_col:
        if step2_substep == "subgroup":
            if st.button(
                "다음 단계: 구체 상품/서비스의 유사군코드 선택",
                use_container_width=True,
                type="primary",
                disabled=not can_continue_to_code_selection(current_selected_fields()),
                key="nice_next_step3_clean",
            ):
                st.session_state.step = 3
                st.rerun()
        else:
            if st.button(
                "구체상품군 선택 단계로 이동",
                use_container_width=True,
                type="primary",
                disabled=not can_enter_subgroup_stage(selected_kind, selected_group),
                key="nice_go_subgroups_clean",
            ):
                st.session_state.step2_substep = "subgroup"
                st.rerun()


def render_scope_step() -> None:
    coverage = validate_catalog_coverage()
    selected_kind = st.session_state.get("selected_kind")
    selected_group = st.session_state.get("selected_group")
    step2_substep = st.session_state.get("step2_substep", "group")

    st.markdown(f"## '{st.session_state.trademark_name}' 상표의 상품범위를 선택하세요")
    st.markdown("### 분류 1 → 분류 2 → 구체상품군 순서로 선택합니다")
    st.caption(
        f"엑셀 기준 확인: goods {coverage['goods_class_count']}개 / services {coverage['services_class_count']}개"
    )

    st.markdown("### 1. 분류 1 선택")
    kind_col1, kind_col2 = st.columns(2)
    with kind_col1:
        if st.button("제품\n(제품, 브랜드)", use_container_width=True, key="scope_kind_goods"):
            set_selected_kind("goods")
            st.rerun()
    with kind_col2:
        if st.button("서비스\n(상호, 서비스)", use_container_width=True, key="scope_kind_services"):
            set_selected_kind("services")
            st.rerun()

    if selected_kind:
        st.markdown(f"선택 분류 1: **{'제품' if selected_kind == 'goods' else '서비스'}**")
        st.markdown("### 2. 분류 2 선택")
        st.caption("이 단계에서는 짧은 카테고리명만 보여줍니다.")

        group_cards = get_group_cards(selected_kind)
        group_cols = st.columns(3)
        for index, group_card in enumerate(group_cards):
            with group_cols[index % 3]:
                active = selected_group == group_card["group_id"]
                st.markdown(
                    f"""
                    <div class="category-card">
                        <b>{group_card['group_label']}</b><br>
                        <small style="color:#546E7A;">{group_card.get('group_hint', '')}</small><br>
                        <small style="color:#546E7A;">연결 니스류 {group_card['nice_class_summary']}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "선택 중" if active else "카테고리 선택",
                    key=f"scope_group_{group_card['group_id']}",
                    use_container_width=True,
                ):
                    set_selected_group(group_card["group_id"])
                    st.session_state.step2_substep = "group"
                    st.rerun()
    else:
        st.info("먼저 제품 또는 서비스를 선택하세요.")

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if step2_substep == "subgroup" and can_enter_subgroup_stage(selected_kind, selected_group):
        active_group = find_group(selected_kind, selected_group)
        if active_group:
            st.markdown("---")
            st.markdown("### 3. 구체상품군 선택")
            st.caption("선택한 카테고리에 해당하는 상품군을 1개 이상 선택하세요")
            st.markdown(f"선택 카테고리: **{active_group['group_label']}**")
            st.caption(
                f"{active_group.get('group_hint', '')} | 연결 니스류 {format_nice_classes(active_group.get('classes', []))}"
            )

            subgroup_cols = st.columns(2)
            for index, subgroup in enumerate(active_group.get("subgroups", [])):
                subgroup_payload = subgroup_to_field(
                    {
                        "kind": selected_kind,
                        "group_id": active_group["group_id"],
                        "group_label": active_group["group_label"],
                        "group_hint": active_group.get("group_hint", ""),
                        **subgroup,
                    }
                )
                already_selected = any(
                    field_key(field) == field_key(subgroup_payload)
                    for field in current_selected_fields()
                )
                with subgroup_cols[index % 2]:
                    st.markdown(
                        f"""
                        <div class="category-card">
                            <b>{subgroup['subgroup_label']}</b><br>
                            <small style="color:#546E7A;">연결 니스류 {format_nice_classes(subgroup.get('nice_classes', []))}</small><br>
                            <small style="color:#546E7A;">추천 유사군코드 {', '.join(subgroup.get('similarity_codes', [])) or '-'}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "선택 해제" if already_selected else "상품군 선택",
                        key=f"scope_subgroup_{subgroup['subgroup_id']}",
                    ):
                        if already_selected:
                            remove_selected_field(field_key(subgroup_payload))
                        else:
                            add_selected_field(subgroup_payload)
                        st.rerun()

    if current_selected_fields():
        derived_scope = derive_scope_state()
        st.markdown("---")
        st.markdown("### 선택 결과 요약")
        st.markdown(f"선택 분류 1: **{derived_scope['selected_scope_summary']['selected_kind_label']}**")
        st.markdown(f"선택 분류 2: **{', '.join(derived_scope['selected_groups'])}**")
        st.markdown(f"선택 상품군: **{', '.join(derived_scope['selected_subgroups'])}**")
        st.markdown(
            f"연결 니스류: **{derived_scope['selected_scope_summary']['selected_nice_classes_text']}**"
        )
        if derived_scope["derived_similarity_codes"]:
            st.caption(
                f"내부 도출 유사군코드: {', '.join(derived_scope['derived_similarity_codes'])}"
            )

    prev_col, next_col = st.columns(2)
    with prev_col:
        if step2_substep == "subgroup":
            if st.button("이전 단계: 카테고리 선택", use_container_width=True, key="scope_back_group"):
                st.session_state.step2_substep = "group"
                st.rerun()
        else:
            if st.button("이전 단계", use_container_width=True, key="scope_back_name"):
                st.session_state.step = 1
                st.rerun()
    with next_col:
        if step2_substep == "subgroup":
            if st.button(
                "다음 단계: 검토",
                use_container_width=True,
                type="primary",
                disabled=not can_continue_to_code_selection(current_selected_fields()),
                key="scope_next_review",
            ):
                sync_nice_selection_state()
                st.session_state.step = 3
                st.rerun()
        else:
            if st.button(
                "구체상품군 선택 단계로 이동",
                use_container_width=True,
                type="primary",
                disabled=not can_enter_subgroup_stage(selected_kind, selected_group),
                key="scope_go_subgroups",
            ):
                st.session_state.step2_substep = "subgroup"
                st.rerun()


def render_scope_step() -> None:
    coverage = validate_catalog_coverage()
    scope_state = derive_scope_state()
    selected_kind = scope_state.get("selected_kind")
    selected_group_id = scope_state.get("selected_group_id")
    selected_group_label = scope_state.get("selected_group_label")
    step_scope_sub = scope_state.get("step_scope_sub", "group")

    st.markdown(f"## '{st.session_state.trademark_name}' 상표의 상품범위를 선택하세요")
    st.markdown("### 분류 1 -> 분류 2 -> 구체상품군 순서로 단계별로 선택합니다")
    st.caption(
        f"카탈로그 기준 확인: goods {coverage['goods_class_count']}개 / services {coverage['services_class_count']}개"
    )

    st.markdown("### 1. 분류 1 선택")
    kind_col1, kind_col2 = st.columns(2)
    with kind_col1:
        if st.button("제품", use_container_width=True, key="scope_kind_goods"):
            set_selected_kind("goods")
            st.rerun()
    with kind_col2:
        if st.button("서비스", use_container_width=True, key="scope_kind_services"):
            set_selected_kind("services")
            st.rerun()

    if selected_kind:
        selected_kind_label = "제품" if selected_kind == "goods" else "서비스"
        st.markdown("### 2. 분류 2 선택")
        st.caption("분류 2 카테고리를 먼저 고른 뒤, 다음 단계에서 해당 구체상품군을 선택합니다.")

        group_cards = get_group_cards(selected_kind)
        group_cols = st.columns(3)
        for index, group_card in enumerate(group_cards):
            active = selected_group_id == group_card["group_id"]
            card_style = (
                "background:#E8F5E9; border:2px solid #2E7D32;"
                if active
                else "background:#F8FBFF; border:2px solid #90CAF9;"
            )
            with group_cols[index % 3]:
                st.markdown(
                    f"""
                    <div style="{card_style} border-radius:12px; padding:16px; margin:8px 0;">
                        <b>{group_card['group_label']}</b><br>
                        <small style="color:#546E7A;">{group_card.get('group_hint', '')}</small><br>
                        <small style="color:#546E7A;">연결 니스류 {group_card['nice_class_summary']}</small><br>
                        <small style="color:{'#2E7D32' if active else '#546E7A'};">{'선택됨' if active else '선택 가능'}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "선택됨" if active else "카테고리 선택",
                    key=f"scope_group_{group_card['group_id']}",
                    use_container_width=True,
                ):
                    set_selected_group(group_card["group_id"])
                    st.rerun()

        st.markdown("---")
        st.markdown("### 현재 선택 요약")
        st.markdown(f"- 현재 선택한 분류 1: **{selected_kind_label}**")
        st.markdown(f"- 현재 선택한 분류 2: **{selected_group_label or '-'}**")
    else:
        st.info("먼저 제품 또는 서비스를 선택하세요.")

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if should_render_subgroup_stage(step_scope_sub, selected_kind, selected_group_id):
        active_group = find_group(selected_kind, selected_group_id)
        if active_group:
            st.markdown("---")
            st.markdown("### 3. 구체상품군 선택")
            st.caption("선택한 카테고리에 해당하는 상품군을 1개 이상 선택하세요")
            st.markdown(f"선택한 카테고리: **{active_group['group_label']}**")
            st.caption(
                f"{active_group.get('group_hint', '')} | 연결 니스류 {format_nice_classes(active_group.get('classes', []))}"
            )

            subgroup_cols = st.columns(2)
            for index, subgroup in enumerate(active_group.get("subgroups", [])):
                subgroup_payload = subgroup_to_field(
                    {
                        "kind": selected_kind,
                        "group_id": active_group["group_id"],
                        "group_label": active_group["group_label"],
                        "group_hint": active_group.get("group_hint", ""),
                        **subgroup,
                    }
                )
                already_selected = any(
                    field_key(field) == field_key(subgroup_payload)
                    for field in current_selected_fields()
                )
                card_style = (
                    "background:#FFF8E1; border:2px solid #FB8C00;"
                    if already_selected
                    else "background:#FFFFFF; border:1px solid #CFD8DC;"
                )
                with subgroup_cols[index % 2]:
                    st.markdown(
                        f"""
                        <div style="{card_style} border-radius:12px; padding:16px; margin:8px 0;">
                            <b>{subgroup['subgroup_label']}</b><br>
                            <small style="color:#546E7A;">연결 니스류 {format_nice_classes(subgroup.get('nice_classes', []))}</small><br>
                            <small style="color:#546E7A;">내부 유사군코드 {', '.join(subgroup.get('similarity_codes', [])) or '-'}</small><br>
                            <small style="color:{'#E65100' if already_selected else '#607D8B'};">{'선택됨' if already_selected else '선택 가능'}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "선택 해제" if already_selected else "상품군 선택",
                        key=f"scope_subgroup_{subgroup['subgroup_id']}",
                        use_container_width=True,
                    ):
                        if already_selected:
                            remove_selected_field(field_key(subgroup_payload))
                        else:
                            add_selected_field(subgroup_payload)
                        st.rerun()

    scope_state = derive_scope_state()
    if scope_state["selected_subgroup_ids"]:
        selected_kind_label = "제품" if selected_kind == "goods" else "서비스"
        st.markdown("---")
        st.markdown("### 선택 결과 요약")
        st.markdown(f"- 현재 선택한 분류 1: **{selected_kind_label}**")
        st.markdown(f"- 현재 선택한 분류 2: **{scope_state['selected_group_label'] or '-'}**")
        st.markdown(f"- 선택한 구체상품군: **{', '.join(scope_state['selected_subgroup_labels'])}**")
        st.markdown(
            f"- 도출 니스류: **{format_nice_classes(scope_state['derived_nice_classes']) or '-'}**"
        )
        st.markdown(
            f"- 내부 도출 유사군코드: **{', '.join(scope_state['derived_similarity_codes']) or '-'}**"
        )
        st.caption("선택한 구체상품군을 기준으로 상품유사군코드.xlsx의 예규상 가장 근접한 유사군코드를 자동 도출했습니다.")

    prev_col, next_col = st.columns(2)
    with prev_col:
        if should_render_subgroup_stage(step_scope_sub, selected_kind, selected_group_id):
            if st.button("이전 단계: 분류 2 선택", use_container_width=True, key="scope_back_group"):
                st.session_state.step_scope_sub = "group"
                st.session_state.step2_substep = "group"
                st.rerun()
        else:
            if st.button("이전 단계", use_container_width=True, key="scope_back_name"):
                st.session_state.step = 1
                st.rerun()
    with next_col:
        if should_render_subgroup_stage(step_scope_sub, selected_kind, selected_group_id):
            if st.button(
                "검토 실행 단계로 이동",
                use_container_width=True,
                type="primary",
                disabled=not can_run_review(scope_state["selected_subgroup_ids"]),
                key="scope_next_review",
            ):
                sync_nice_selection_state()
                st.session_state.step = 3
                st.rerun()
        else:
            if st.button(
                "구체상품군 선택 단계로 이동",
                use_container_width=True,
                type="primary",
                disabled=not can_enter_subgroup_stage(selected_kind, selected_group_id),
                key="scope_go_subgroups",
            ):
                st.session_state.step_scope_sub = "subgroup"
                st.session_state.step2_substep = "subgroup"
                st.rerun()

def render_review_step() -> None:
    selected_fields = current_selected_fields()
    derived_scope = derive_scope_state(selected_fields)

    st.markdown("## 검토 실행")
    st.markdown("### 선택한 구체상품군을 기준으로 관련 니스류와 유사군코드를 시스템이 자동 도출합니다")

    if not selected_fields:
        st.warning("먼저 구체상품군을 선택하세요.")
        if st.button("상품범위 선택으로 돌아가기", use_container_width=True):
            st.session_state.step = 2
            st.session_state.step2_substep = "subgroup"
            st.rerun()
        return

    st.markdown(
        f"""
        <div class="card">
            <b>선택 분류 1</b>: {derived_scope['selected_scope_summary']['selected_kind_label']} |
            <b>선택 분류 2</b>: {', '.join(derived_scope['selected_groups']) or '-'} |
            <b>선택 상품군</b>: {', '.join(derived_scope['selected_subgroups']) or '-'}<br>
            <small style="color:#546E7A;">
            연결 니스류 {derived_scope['selected_scope_summary']['selected_nice_classes_text']} |
            내부 도출 유사군코드 {', '.join(derived_scope['derived_similarity_codes']) or '-'}
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("구체 상품명/서비스명을 추가 입력하면 선택한 상품군 범위 안에서만 내부 매핑을 보강합니다.")
    for index, field in enumerate(selected_fields, start=1):
        config = get_field_input(field)
        specific_product = st.text_input(
            f"{index}. {field.get('group_label', '-') } > {field_label(field)}",
            placeholder=field.get("example", ""),
            value=config.get("specific_product", ""),
            key=f"review_specific_{field_widget_key(field)}",
        )
        if specific_product != config.get("specific_product", ""):
            update_field_product(field, specific_product)
            st.rerun()

    derived_scope = derive_scope_state(selected_fields)
    st.markdown("### 내부 검토 입력")
    st.markdown(f"- 구체상품군: {', '.join(derived_scope['selected_subgroups'])}")
    st.markdown(f"- 연결 니스류: {format_nice_classes(derived_scope['derived_nice_classes'])}")
    st.markdown(f"- 내부 유사군코드: {', '.join(derived_scope['derived_similarity_codes']) or '-'}")
    st.markdown(
        f"- 검색 보조 키워드: {', '.join(derived_scope['search_terms_for_prior_marks'][:8]) or '-'}"
    )

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("이전 단계: 상품범위", use_container_width=True, key="review_back_scope"):
            st.session_state.step = 2
            st.session_state.step2_substep = "subgroup"
            st.rerun()
    with next_col:
        if st.button(
            "검토 실행",
            use_container_width=True,
            type="primary",
            disabled=not all_fields_ready(),
            key="review_run_analysis",
        ):
            sync_nice_selection_state()
            reset_analysis_state()
            st.session_state.step = 4
            st.rerun()


def render_review_step() -> None:
    selected_fields = current_selected_fields()
    scope_state = derive_scope_state(selected_fields)

    st.markdown("## 검토 실행")
    st.markdown("### 선택한 구체상품군을 기준으로 니스류와 유사군코드를 내부 계산한 뒤 검토합니다")
    st.caption("선택한 구체상품군을 기준으로 상품유사군코드.xlsx의 예규상 가장 근접한 유사군코드를 자동 도출했습니다.")

    if not can_run_review(scope_state["selected_subgroup_ids"]):
        st.warning("먼저 구체상품군을 1개 이상 선택하세요.")
        if st.button("상품범위 선택으로 돌아가기", use_container_width=True):
            st.session_state.step = 2
            st.session_state.step_scope_sub = "subgroup"
            st.session_state.step2_substep = "subgroup"
            st.rerun()
        return

    selected_kind_label = "제품" if scope_state["selected_kind"] == "goods" else "서비스"
    st.markdown(
        f"""
        <div class="card">
            <b>선택 분류 1</b>: {selected_kind_label} |
            <b>선택 분류 2</b>: {scope_state['selected_group_label'] or '-'} |
            <b>선택 상품군</b>: {', '.join(scope_state['selected_subgroup_labels']) or '-'}<br>
            <small style="color:#546E7A;">
            도출 니스류 {format_nice_classes(scope_state['derived_nice_classes']) or '-'} |
            내부 유사군코드 {', '.join(scope_state['derived_similarity_codes']) or '-'}
            </small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("구체 상품명이나 서비스명을 추가 입력하면 선택한 상품군 범위 안에서만 내부 매핑을 보정합니다.")
    for index, field in enumerate(selected_fields, start=1):
        config = get_field_input(field)
        specific_product = st.text_input(
            f"{index}. {field.get('group_label', '-') } > {field_label(field)}",
            placeholder=field.get("example", ""),
            value=config.get("specific_product", ""),
            key=f"review_specific_{field_widget_key(field)}",
        )
        if specific_product != config.get("specific_product", ""):
            update_field_product(field, specific_product)
            st.rerun()

    scope_state = derive_scope_state(selected_fields)
    st.markdown("### 내부 검토 입력")
    st.markdown(f"- 구체상품군: {', '.join(scope_state['selected_subgroup_labels'])}")
    st.markdown(f"- 연결 니스류: {format_nice_classes(scope_state['derived_nice_classes']) or '-'}")
    st.markdown(f"- 내부 유사군코드: {', '.join(scope_state['derived_similarity_codes']) or '-'}")
    st.markdown(
        f"- 검색 보조 키워드: {', '.join(scope_state['search_terms_for_prior_marks'][:8]) or '-'}"
    )

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("이전 단계: 상품범위", use_container_width=True, key="review_back_scope"):
            st.session_state.step = 2
            st.session_state.step_scope_sub = "subgroup"
            st.session_state.step2_substep = "subgroup"
            st.rerun()
    with next_col:
        if st.button(
            "검토 실행",
            use_container_width=True,
            type="primary",
            disabled=not can_run_review(scope_state["selected_subgroup_ids"]),
            key="review_run_analysis",
        ):
            sync_nice_selection_state()
            reset_analysis_state()
            st.session_state.step = 4
            st.rerun()


def similarity_cell_style(value) -> str:
    try:
        numeric = int(str(value).replace("%", ""))
    except ValueError:
        return ""
    if numeric >= 70:
        return "background-color: #FFEBEE; color: #B71C1C; font-weight: bold;"
    if numeric >= 50:
        return "background-color: #FFF3E0; color: #E65100; font-weight: bold;"
    return "background-color: #E8F5E9; color: #2E7D32;"


st.set_page_config(
    page_title="상표등록 가능성 검토",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .stApp { background-color: #F0F8FF; }
    .main-header {
        background: linear-gradient(135deg, #1565C0, #2196F3);
        padding: 20px 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 24px;
    }
    .step-bar {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin: 16px 0;
        flex-wrap: wrap;
    }
    .step-active {
        background: #2196F3;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
    }
    .step-done {
        background: #4CAF50;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 14px;
    }
    .step-todo {
        background: #B0BEC5;
        color: white;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 14px;
    }
    .card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(33,150,243,0.1);
        border-left: 4px solid #2196F3;
        margin-bottom: 16px;
    }
    .category-card {
        background: #E3F2FD;
        border: 2px solid #90CAF9;
        border-radius: 10px;
        padding: 16px;
        margin: 8px 0;
    }
    .code-card {
        background: #F8FBFF;
        border: 1px solid #90CAF9;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
    }
    .code-recommended {
        border-color: #2196F3;
        border-width: 2px;
        background: #E3F2FD;
    }
    .code-sales {
        border-color: #66BB6A;
        background: #F1F8E9;
    }
    .result-90 { background:#E8F5E9; border:3px solid #4CAF50; border-radius:12px; padding:20px; text-align:center; }
    .result-70 { background:#E3F2FD; border:3px solid #2196F3; border-radius:12px; padding:20px; text-align:center; }
    .result-50 { background:#FFF3E0; border:3px solid #FF9800; border-radius:12px; padding:20px; text-align:center; }
    .result-30 { background:#FFEBEE; border:3px solid #F44336; border-radius:12px; padding:20px; text-align:center; }
    .result-0  { background:#B71C1C; border:3px solid #7F0000; border-radius:12px; padding:20px; text-align:center; color:white; }
    .trademark-high { background:#FFEBEE; border-left:4px solid #F44336; border-radius:8px; padding:14px; margin:8px 0; }
    .trademark-medium { background:#FFF3E0; border-left:4px solid #FF9800; border-radius:8px; padding:14px; margin:8px 0; }
    .trademark-low { background:#E8F5E9; border-left:4px solid #4CAF50; border-radius:8px; padding:14px; margin:8px 0; }
    .stButton>button {
        background: linear-gradient(135deg, #1976D2, #2196F3);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 16px;
        font-weight: bold;
        white-space: pre-wrap;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #1565C0, #1976D2);
        color: white;
    }
    .tip-box {
        background: #E8F4FD;
        border: 1px solid #90CAF9;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 13px;
        color: #1565C0;
        margin: 8px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

if "step" not in st.session_state:
    st.session_state.step = 1
if "trademark_name" not in st.session_state:
    st.session_state.trademark_name = ""
if "trademark_type" not in st.session_state:
    st.session_state.trademark_type = "문자만"
if "is_coined" not in st.session_state:
    st.session_state.is_coined = False
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "specific_keyword" not in st.session_state:
    st.session_state.specific_keyword = ""
if "specific_product" not in st.session_state:
    st.session_state.specific_product = ""
if "selected_fields" not in st.session_state:
    st.session_state.selected_fields = []
if "selected_kind" not in st.session_state:
    st.session_state.selected_kind = None
if "selected_group_id" not in st.session_state:
    st.session_state.selected_group_id = None
if "selected_group_label" not in st.session_state:
    st.session_state.selected_group_label = ""
if "selected_group" not in st.session_state:
    st.session_state.selected_group = None
if "step_scope_sub" not in st.session_state:
    st.session_state.step_scope_sub = "group"
if "step2_substep" not in st.session_state:
    st.session_state.step2_substep = "group"
if "selected_groups" not in st.session_state:
    st.session_state.selected_groups = []
if "selected_subgroups" not in st.session_state:
    st.session_state.selected_subgroups = []
if "selected_subgroup_ids" not in st.session_state:
    st.session_state.selected_subgroup_ids = []
if "selected_subgroup_labels" not in st.session_state:
    st.session_state.selected_subgroup_labels = []
if "selected_nice_classes" not in st.session_state:
    st.session_state.selected_nice_classes = []
if "selected_similarity_codes" not in st.session_state:
    st.session_state.selected_similarity_codes = []
if "recommended_similarity_codes" not in st.session_state:
    st.session_state.recommended_similarity_codes = []
if "derived_nice_classes" not in st.session_state:
    st.session_state.derived_nice_classes = []
if "derived_similarity_codes" not in st.session_state:
    st.session_state.derived_similarity_codes = []
if "candidate_similarity_codes" not in st.session_state:
    st.session_state.candidate_similarity_codes = []
if "similarity_match_details" not in st.session_state:
    st.session_state.similarity_match_details = []
if "subgroup_keywords" not in st.session_state:
    st.session_state.subgroup_keywords = []
if "search_terms_for_prior_marks" not in st.session_state:
    st.session_state.search_terms_for_prior_marks = []
if "selected_scope_summary" not in st.session_state:
    st.session_state.selected_scope_summary = {}
if "selected_keywords" not in st.session_state:
    st.session_state.selected_keywords = []
if "field_inputs" not in st.session_state:
    st.session_state.field_inputs = {}
if "selected_codes" not in st.session_state:
    st.session_state.selected_codes = []
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "score" not in st.session_state:
    st.session_state.score = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None
if "search_source" not in st.session_state:
    st.session_state.search_source = ""
if "selection_error" not in st.session_state:
    st.session_state.selection_error = ""

sync_nice_selection_state()

st.markdown(
    """
<div class="main-header">
    <h1 style="margin:0; font-size:28px;">상표등록 가능성 검토</h1>
    <p style="margin:4px 0 0 0; opacity:0.9;">내 브랜드를 법적으로 보호하세요</p>
</div>
""",
    unsafe_allow_html=True,
)


def render_steps(current: int) -> None:
    steps = ["① 상표명", "② 상품선택", "③ 유사군코드", "④ 검토결과", "⑤ 개선방안"]
    html = '<div class="step-bar">'
    for index, label in enumerate(steps, 1):
        if index < current:
            html += f'<span class="step-done">✓ {label}</span>'
        elif index == current:
            html += f'<span class="step-active">{label}</span>'
        else:
            html += f'<span class="step-todo">{label}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_user_steps(current: int) -> None:
    steps = ["① 상표명", "② 상품범위", "③ 검토", "④ 결과", "⑤ 개선방안"]
    html = '<div class="step-bar">'
    for index, label in enumerate(steps, 1):
        if index < current:
            html += f'<span class="step-done">✓ {label}</span>'
        elif index == current:
            html += f'<span class="step-active">{label}</span>'
        else:
            html += f'<span class="step-todo">{label}</span>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


render_user_steps(st.session_state.step)
st.markdown("---")


if st.session_state.step == 1:
    st.markdown("## 안녕하세요!")
    st.markdown("### 등록하고 싶은 상표명을 알려주세요")
    render_auri(260)

    st.markdown("#### 상표 유형을 선택해주세요")
    type_options = ["문자만", "문자+로고", "로고만"]
    current_type = st.session_state.get("trademark_type", "문자만")
    type_index = type_options.index(current_type) if current_type in type_options else 0

    with st.form("step1_form"):
        name = st.text_input(
            "상표명 입력",
            placeholder="예) POOKIE, 사랑해, BRAND ONE, 달빛커피...",
            value=st.session_state.get("trademark_name", ""),
            label_visibility="collapsed",
        )
        selected_type = st.radio(
            "상표 유형",
            type_options,
            index=type_index,
            horizontal=True,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "다음 단계로 → 상품 선택",
            use_container_width=True,
            type="primary",
        )

    st.markdown(f"선택됨: **{selected_type}**")

    if submitted:
        cleaned = name.strip()
        if cleaned:
            st.session_state.trademark_name = cleaned
            st.session_state.trademark_type = selected_type
            st.session_state.is_coined = False
            st.session_state.step = 2
            st.rerun()
        else:
            st.error("상표명을 입력해주세요!")

elif st.session_state.step == 2:
    render_scope_step()

elif False and st.session_state.step == 2:
    coverage = validate_catalog_coverage()
    st.markdown(f"## '{st.session_state.trademark_name}' 상표의 사용 영역을 선택하세요")
    st.markdown("### 제품/서비스 → 대분류 → 상품군 순서로 선택합니다.")

    st.markdown(
        """
    <div class="tip-box">
    <b>니스분류 기준 입력</b><br>
    상품은 제1류~제34류, 서비스는 제35류~제45류를 기준으로 저장하고 판단합니다.<br>
    화면의 분류 1 / 분류 2 / 상품군은 UX 레이어이고, 실제 분석은 선택된 니스류 번호와 유사군코드로 시작합니다.
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"니스류 데이터 확인: goods {coverage['goods_class_count']}개 / services {coverage['services_class_count']}개"
    )

    st.markdown("### 1. 분류 1 선택")
    kind_col1, kind_col2 = st.columns(2)
    with kind_col1:
        if st.button("제품(제품, 브랜드)", use_container_width=True, key="nice_kind_goods"):
            set_selected_kind("goods")
            st.rerun()
    with kind_col2:
        if st.button("서비스(상호, 서비스)", use_container_width=True, key="nice_kind_services"):
            set_selected_kind("services")
            st.rerun()

    selected_kind = st.session_state.get("selected_kind")
    if selected_kind:
        st.markdown(
            f"현재 선택: **{'제품(goods)' if selected_kind == 'goods' else '서비스(services)'}**"
        )
        st.markdown("### 2. 분류 2 선택")

        groups = get_groups(selected_kind)
        group_cols = st.columns(3)
        for index, group in enumerate(groups):
            with group_cols[index % 3]:
                active = st.session_state.get("selected_group") == group["group_id"]
                st.markdown(
                    f"""
                    <div class="category-card">
                        <b>{group.get('nice_class_label', group['group_label'])}</b><br>
                        <small style="color:#546E7A;">{group.get('class_heading', group['group_label'])}</small><br>
                        <small style="color:#546E7A;">하위 상품군 {len(group.get('subgroups', []))}개</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    "선택됨" if active else "분류 2 선택",
                    key=f"nice_group_{group['group_id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_group = group["group_id"]
                    st.session_state.selection_error = ""
                    st.rerun()

        if st.session_state.get("selected_group"):
            active_group = next(
                (group for group in groups if group["group_id"] == st.session_state.selected_group),
                None,
            )
            if active_group:
                st.markdown("---")
                st.markdown("### 3. 구체상품군 선택")
                st.caption("선택한 니스분류에 해당하는 상품군을 1개 이상 선택하세요")
                st.markdown(
                    f"현재 선택한 분류 2: **{active_group.get('nice_class_label', active_group['group_label'])}**"
                )
                st.caption(active_group.get("class_heading", active_group["group_label"]))

                quick_query = st.text_input(
                    "상품군 빠른 찾기",
                    key="nice_quick_search",
                    placeholder="예: 화장품, 소프트웨어, 카페, 가구",
                )
                if quick_query.strip():
                    suggestions = get_category_suggestions(quick_query, kind=selected_kind, limit=6)
                    if suggestions:
                        st.markdown("#### 빠른 추천")
                        for suggestion in suggestions:
                            suggestion_payload = subgroup_to_field(
                                {
                                    "kind": suggestion["kind"],
                                    "group_id": suggestion["group_id"],
                                    "group_label": suggestion["group_label"],
                                    "group_heading": suggestion.get("group_heading", ""),
                                    "subgroup_id": suggestion["subgroup_id"],
                                    "subgroup_label": suggestion["subgroup_label"],
                                    "nice_classes": suggestion["nice_classes"],
                                    "keywords": suggestion["keywords"],
                                    "similarity_codes": suggestion["similarity_codes"],
                                }
                            )
                            already_selected = any(
                                field_key(field) == field_key(suggestion_payload)
                                for field in current_selected_fields()
                            )
                            col1, col2 = st.columns([5, 1])
                            with col1:
                                st.markdown(
                                    f"""
                                    <div class="category-card">
                                        <b>{suggestion.get('group_icon', '')} {suggestion['group_label']} &gt; {suggestion['subgroup_label']}</b><br>
                                        <small style="color:#546E7A;">연결 니스류: {suggestion['nice_class_summary']}</small><br>
                                        <small style="color:#546E7A;">키워드: {', '.join(suggestion['keywords'][:4])}</small>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            with col2:
                                if st.button(
                                    "해제" if already_selected else "추가",
                                    key=f"nice_suggest_{suggestion['subgroup_id']}",
                                ):
                                    if already_selected:
                                        remove_selected_field(field_key(suggestion_payload))
                                    else:
                                        add_selected_field(suggestion_payload)
                                    st.rerun()

                subgroup_cols = st.columns(2)
                for index, subgroup in enumerate(active_group.get("subgroups", [])):
                    subgroup_payload = subgroup_to_field(
                        {
                            "kind": selected_kind,
                            "group_id": active_group["group_id"],
                            "group_label": active_group["group_label"],
                            "group_heading": active_group.get("class_heading", ""),
                            **subgroup,
                        }
                    )
                    already_selected = any(
                        field_key(field) == field_key(subgroup_payload)
                        for field in current_selected_fields()
                    )
                    with subgroup_cols[index % 2]:
                        st.markdown(
                            f"""
                            <div class="category-card">
                                <b>{subgroup['subgroup_label']}</b><br>
                                <small style="color:#546E7A;">연결 니스류: {format_nice_classes(subgroup.get('nice_classes', []))}</small><br>
                                <small style="color:#546E7A;">키워드: {', '.join(subgroup.get('keywords', [])[:4])}</small><br>
                                <small style="color:#546E7A;">추천 유사군코드: {', '.join(subgroup.get('similarity_codes', [])) or '-'}</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "선택 해제" if already_selected else "상품군 선택",
                            key=f"nice_subgroup_{subgroup['subgroup_id']}",
                        ):
                            if already_selected:
                                remove_selected_field(field_key(subgroup_payload))
                            else:
                                add_selected_field(subgroup_payload)
                            st.rerun()
    else:
        st.info("먼저 제품 또는 서비스를 선택하세요.")

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if current_selected_fields():
        summary = build_selection_summary(
            selected_kind=st.session_state.get("selected_kind"),
            selected_fields=current_selected_fields(),
        )
        st.markdown("---")
        st.markdown("### 선택 결과 요약")
        st.markdown(f"선택 분류 1: **{summary['selected_kind_label']}**")
        st.markdown(f"선택 분류 2: **{', '.join(summary['selected_groups'])}**")
        st.markdown(f"선택 상품군: **{', '.join(summary['selected_subgroups'])}**")
        st.markdown(f"연결 니스류: **{summary['selected_nice_classes_text']}**")
        if st.session_state.get("recommended_similarity_codes"):
            st.markdown(
                f"연결 추천 유사군코드: **{', '.join(st.session_state['recommended_similarity_codes'])}**"
            )

        for index, field in enumerate(current_selected_fields(), start=1):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(
                    f"""
                    <div class="card">
                        <b>{index}. {field.get('group_label', '-')} &gt; {field_label(field)}</b><br>
                        <small style="color:#546E7A;">키워드: {', '.join(field.get('keywords', [])[:4]) or '-'}</small><br>
                        <small style="color:#546E7A;">추천 유사군코드: {', '.join(field.get('similarity_codes', [])) or '-'}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("제거", key=f"nice_remove_{field_widget_key(field)}"):
                    remove_selected_field(field_key(field))
                    st.rerun()

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("이전 단계", use_container_width=True, key="nice_back_step1"):
            st.session_state.step = 1
            st.rerun()
    with next_col:
        if st.button(
            "다음 단계: 구체 상품/서비스와 유사군코드 선택",
            use_container_width=True,
            type="primary",
            disabled=not is_subgroup_selection_complete(current_selected_fields()),
            key="nice_next_step3",
        ):
            st.session_state.step = 3
            st.rerun()

elif st.session_state.step == 2 and False:
    st.markdown(f"## '{st.session_state.trademark_name}' 상표를")
    st.markdown("### 어떤 분야에 사용하실 예정인가요? 최대 3개까지 선택할 수 있어요.")

    st.markdown(
        """
    <div class="tip-box">
    상표는 반드시 <b>사용할 상품/서비스 분야</b>를 지정해서 등록해야 해요.<br>
    아래에서 업종을 검색하거나 직접 선택해주세요.
    </div>
    """,
        unsafe_allow_html=True,
    )

    search_keyword = st.text_input(
        "업종/상품 검색",
        placeholder="예) 가구, 커피, 옷, 화장품, 앱개발, 음식점...",
        label_visibility="collapsed",
    )

    if search_keyword:
        suggestions = get_category_suggestions(search_keyword, limit=6)
        if suggestions:
            st.markdown("#### 추천 상품/서비스 분야")
            for index, sug in enumerate(suggestions):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{sug['아이콘']} {sug['설명']} ({sug['류']})</b><br>
                        <small style="color:#546E7A">예시: {sug['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    already_selected = any(
                        field_key(field) == field_key({"class_no": sug["류"], "description": sug["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"sel_{index}_{sug['류']}"):
                        add_selected_field(
                            {"class_no": sug["류"], "description": sug["설명"], "example": sug["예시"]}
                        )
                        st.rerun()
        else:
            st.warning("검색 결과가 없어요. 아래 전체 목록에서 선택해주세요.")

    st.markdown("---")
    st.markdown("#### 전체 목록에서 직접 선택")

    all_categories = {
        "상품": [
            {"류": "3류", "설명": "화장품/향수/세제", "예시": "스킨케어, 향수, 샴푸", "아이콘": "💄"},
            {"류": "5류", "설명": "의약품/건강기능식품", "예시": "영양제, 건강식품", "아이콘": "💊"},
            {"류": "9류", "설명": "전자기기/소프트웨어", "예시": "스마트폰, 앱, 컴퓨터", "아이콘": "📱"},
            {"류": "14류", "설명": "귀금속/시계/보석", "예시": "반지, 목걸이, 시계", "아이콘": "⌚"},
            {"류": "16류", "설명": "종이/문구/출판물", "예시": "노트, 책, 달력", "아이콘": "📚"},
            {"류": "18류", "설명": "가방/지갑/가죽제품", "예시": "핸드백, 백팩, 지갑", "아이콘": "👜"},
            {"류": "20류", "설명": "가구/인테리어", "예시": "소파, 침대, 책상", "아이콘": "🪑"},
            {"류": "21류", "설명": "주방용품/생활용품", "예시": "컵, 냄비, 칫솔", "아이콘": "🍽️"},
            {"류": "25류", "설명": "의류/신발/모자", "예시": "티셔츠, 운동화, 모자", "아이콘": "👕"},
            {"류": "28류", "설명": "완구/스포츠용품", "예시": "장난감, 게임기, 운동용품", "아이콘": "🎮"},
            {"류": "29류", "설명": "가공식품", "예시": "육류, 유제품, 김치", "아이콘": "🥩"},
            {"류": "30류", "설명": "커피/빵/과자/음료", "예시": "커피, 빵, 과자, 라면", "아이콘": "☕"},
            {"류": "32류", "설명": "음료/맥주", "예시": "탄산음료, 주스, 맥주", "아이콘": "🥤"},
            {"류": "33류", "설명": "주류(소주/와인)", "예시": "소주, 와인, 위스키", "아이콘": "🍷"},
        ],
        "서비스": [
            {"류": "35류", "설명": "광고/소매업/쇼핑몰", "예시": "온라인쇼핑몰, 편의점", "아이콘": "🛍️"},
            {"류": "36류", "설명": "금융/보험/부동산", "예시": "은행, 보험, 증권", "아이콘": "🏢"},
            {"류": "37류", "설명": "건설/수리/인테리어", "예시": "건설, 인테리어, 수리", "아이콘": "🏠"},
            {"류": "38류", "설명": "통신/인터넷/방송", "예시": "통신서비스, SNS", "아이콘": "📡"},
            {"류": "39류", "설명": "운송/여행/물류", "예시": "택배, 여행사, 항공", "아이콘": "✈️"},
            {"류": "41류", "설명": "교육/엔터테인먼트", "예시": "학원, 게임, 공연", "아이콘": "📘"},
            {"류": "42류", "설명": "IT/개발/디자인", "예시": "앱개발, 클라우드", "아이콘": "💻"},
            {"류": "43류", "설명": "음식점/카페/숙박", "예시": "식당, 카페, 호텔", "아이콘": "🍽️"},
            {"류": "44류", "설명": "의료/미용/헬스케어", "예시": "병원, 미용실", "아이콘": "🩺"},
            {"류": "45류", "설명": "법률/보안/개인서비스", "예시": "법률, 변리사", "아이콘": "⚖️"},
        ],
    }

    tab1, tab2 = st.tabs(["상품류 (1~34류)", "서비스류 (35~45류)"])
    with tab1:
        cols = st.columns(2)
        for index, cat in enumerate(all_categories["상품"]):
            with cols[index % 2]:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{cat['아이콘']} {cat['설명']}</b> <small>({cat['류']})</small><br>
                        <small style="color:#546E7A">{cat['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    already_selected = any(
                        field_key(field) == field_key({"class_no": cat["류"], "description": cat["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"goods_{cat['류']}"):
                        add_selected_field(
                            {"class_no": cat["류"], "description": cat["설명"], "example": cat["예시"]}
                        )
                        st.rerun()

    with tab2:
        cols = st.columns(2)
        for index, cat in enumerate(all_categories["서비스"]):
            with cols[index % 2]:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f"""
                    <div class="category-card">
                        <b>{cat['아이콘']} {cat['설명']}</b> <small>({cat['류']})</small><br>
                        <small style="color:#546E7A">{cat['예시']}</small>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown("<br>", unsafe_allow_html=True)
                    already_selected = any(
                        field_key(field) == field_key({"class_no": cat["류"], "description": cat["설명"]})
                        for field in current_selected_fields()
                    )
                    if st.button("선택됨" if already_selected else "추가", key=f"service_{cat['류']}"):
                        add_selected_field(
                            {"class_no": cat["류"], "description": cat["설명"], "example": cat["예시"]}
                        )
                        st.rerun()

    if st.session_state.selection_error:
        st.warning(st.session_state.selection_error)

    if current_selected_fields():
        st.markdown("#### 선택된 상품군")
        for index, field in enumerate(current_selected_fields(), start=1):
            col1, col2 = st.columns([6, 1])
            with col1:
                st.markdown(
                    f"""
                    <div class="card">
                        <b>{index}. {field_label(field)}</b><br>
                        <small style="color:#546E7A;">예시: {field.get('example', '-')}</small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("삭제", key=f"remove_field_{field_widget_key(field)}"):
                    remove_selected_field(field_key(field))
                    st.rerun()

    if st.button("← 이전 단계로"):
        st.session_state.step = 1
        st.rerun()

    if st.button(
        "다음 단계로 → 유사군코드 선택",
        use_container_width=True,
        type="primary",
        disabled=not current_selected_fields(),
    ):
        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 3:
    render_review_step()

elif st.session_state.step == 3 and False:
    selected_fields = current_selected_fields()
    st.markdown("## 선택한 상품군별로 구체 상품/서비스와 유사군코드를 정하세요")
    st.markdown(
        f"### 현재 연결 니스류: **{format_nice_classes(st.session_state.get('selected_nice_classes', []))}**"
    )

    st.markdown(
        """
    <div class="tip-box">
    <b>유사군코드 추천 우선순위</b><br>
    1. 사용자가 Step 2에서 고른 니스류/상품군<br>
    2. 선택 상품군의 키워드와 기본 추천 유사군코드<br>
    3. 사용자가 입력한 구체 상품/서비스명<br>
    4. 기존 자유검색/별칭 매핑
    </div>
    """,
        unsafe_allow_html=True,
    )

    for index, field in enumerate(selected_fields, start=1):
        config = get_field_input(field)
        widget_key = field_widget_key(field)
        st.markdown("---")
        st.markdown(f"### {index}. {field.get('group_label', '-')} > {field_label(field)}")
        st.caption(
            f"키워드: {', '.join(field.get('keywords', [])[:5]) or '-'} | "
            f"기본 추천 코드: {', '.join(field.get('similarity_codes', [])) or '-'}"
        )

        specific_product = st.text_input(
            f"{field_label(field)}의 구체 상품/서비스명",
            placeholder=f"예: {field.get('keywords', [''])[0] or field.get('description', '')}",
            value=config.get("specific_product", ""),
            key=f"nice_product_{widget_key}",
        )
        update_field_product(field, specific_product)
        config = get_field_input(field)

        recommendation_query = specific_product.strip() or field.get("description", "")
        code_rows = get_similarity_codes(
            recommendation_query,
            limit=10,
            seed_classes=field.get("nice_classes", []),
            seed_keywords=field.get("keywords", []),
            seed_codes=field.get("similarity_codes", []),
        )

        if code_rows:
            st.markdown("#### 추천 유사군코드")
            for row in code_rows:
                col1, col2 = st.columns([5, 1])
                badge_parts = []
                if row.get("seed_source") == "selected_subgroup":
                    badge_parts.append("상품군 기본 추천")
                elif row.get("seed_source") == "selected_keywords":
                    badge_parts.append("상품군 키워드 추천")
                if row.get("recommended"):
                    badge_parts.append("우선 추천")
                if row.get("is_sales"):
                    badge_parts.append("판매/유통")
                badge = " · ".join(badge_parts) or "추천"

                with col1:
                    st.markdown(
                        f"""
                        <div class="code-card">
                            <b>{badge} | {row['code']}</b> - {row['name']}<br>
                            <small style="color:#546E7A;">{row.get('description', '-')}</small><br>
                            <small style="color:#546E7A;">연결 류: {row.get('class_no', '-')}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    selected = row["code"] in config.get("selected_codes", [])
                    if st.button(
                        "해제" if selected else "선택",
                        key=f"nice_code_{widget_key}_{row['code']}",
                    ):
                        toggle_field_code(field, row["code"])
                        st.rerun()
        else:
            st.info("추천 결과가 없어 선택 니스류 전체 코드 목록을 보여줍니다.")

        if not code_rows:
            fallback_rows = []
            seen_codes = set()
            for class_no in field.get("nice_classes", []):
                for row in get_all_codes_by_class(class_no):
                    if row["code"] in seen_codes:
                        continue
                    seen_codes.add(row["code"])
                    fallback_rows.append(row)
            for row in fallback_rows:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(
                        f"""
                        <div class="code-card">
                            <b>{row['code']}</b> - {row['name']}<br>
                            <small style="color:#546E7A;">{row.get('description', '-')}</small><br>
                            <small style="color:#546E7A;">연결 류: {row.get('class_no', '-')}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    selected = row["code"] in config.get("selected_codes", [])
                    if st.button(
                        "해제" if selected else "선택",
                        key=f"nice_all_code_{widget_key}_{row['code']}",
                    ):
                        toggle_field_code(field, row["code"])
                        st.rerun()

        selected_codes = config.get("selected_codes", [])
        if selected_codes:
            st.markdown(f"선택된 유사군코드: **{', '.join(selected_codes)}**")
        else:
            st.caption("각 상품군마다 유사군코드를 최소 1개 선택해야 다음 분석 단계로 이동할 수 있습니다.")

    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("이전 단계", use_container_width=True, key="nice_back_step2"):
            st.session_state.step = 2
            st.rerun()
    with next_col:
        if st.button(
            "검색 시작",
            use_container_width=True,
            type="primary",
            disabled=not all_fields_ready(),
            key="nice_run_analysis",
        ):
            reset_analysis_state()
            st.session_state.step = 4
            st.rerun()

elif st.session_state.step == 3 and False:
    selected_fields = current_selected_fields()
    st.markdown("## 선택한 상품군별 구체 상품/서비스와 유사군코드를 정해주세요")

    st.markdown(
        """
    <div class="tip-box">
    <b>유사군코드란?</b> 비슷한 상품끼리 묶은 분류 코드예요.<br>
    코드가 같은 상표끼리 서로 충돌할 수 있어요. 정확히 선택할수록 검토가 정확해져요!
    </div>
    """,
        unsafe_allow_html=True,
    )

    for index, field in enumerate(selected_fields, start=1):
        config = get_field_input(field)
        widget_key = field_widget_key(field)
        st.markdown("---")
        st.markdown(f"### {index}. {field_label(field)}")
        specific_product = st.text_input(
            f"{field_label(field)} 구체 상품명 입력",
            placeholder=f"예) {field.get('example', '').split(',')[0].strip()}...",
            value=config.get("specific_product", ""),
            key=f"product_{widget_key}",
        )
        update_field_product(field, specific_product)
        config = get_field_input(field)

        if specific_product.strip():
            codes = get_similarity_codes(specific_product, field["class_no"])
            if codes:
                st.markdown("#### 추천 유사군코드")
                for code_info in codes:
                    col1, col2 = st.columns([5, 1])
                    badge = ""
                    card_class = "code-card"
                    if code_info.get("추천"):
                        badge = "⭐ 추천"
                        card_class = "code-card code-recommended"
                    if code_info.get("판매업"):
                        badge = "판매업 코드"
                        card_class = "code-card code-sales"

                    with col1:
                        st.markdown(
                            f"""
                        <div class="{card_class}">
                            <b>{badge} {code_info['code']}</b> - {code_info['name']}<br>
                            <small style="color:#546E7A">{code_info['설명']}</small>
                            {"<br><small style='color:#2E7D32'>판매업도 함께 보호받으려면 이 코드도 선택하세요!</small>" if code_info.get("판매업") else ""}
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    with col2:
                        is_selected = code_info["code"] in config.get("selected_codes", [])
                        label = "✓ 선택됨" if is_selected else "선택"
                        if st.button(label, key=f"code_{widget_key}_{code_info['code']}"):
                            toggle_field_code(field, code_info["code"])
                            st.rerun()
            else:
                st.info("추천 결과가 없어 전체 유사군코드 목록을 보여드립니다.")

            if not codes:
                all_codes = get_all_codes_by_class(field["class_no"])
                for code_info in all_codes:
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(
                            f"""
                        <div class="code-card">
                            <b>{code_info['code']}</b> - {code_info['name']}<br>
                            <small>{code_info['설명']}</small>
                        </div>
                        """,
                            unsafe_allow_html=True,
                        )
                    with col2:
                        is_selected = code_info["code"] in config.get("selected_codes", [])
                        label = "✓ 선택됨" if is_selected else "선택"
                        if st.button(label, key=f"all_code_{widget_key}_{code_info['code']}"):
                            toggle_field_code(field, code_info["code"])
                            st.rerun()

        selected_codes = config.get("selected_codes", [])
        if selected_codes:
            st.markdown("#### 선택된 유사군코드")
            st.markdown(" ".join([f"**{code}**" for code in selected_codes]))
        else:
            st.caption("이 상품군에 대한 유사군코드를 최소 1개 선택해주세요.")

    if st.button("← 이전 단계로"):
        st.session_state.step = 2
        st.rerun()

    if st.button(
        "검토 시작하기!",
        use_container_width=True,
        type="primary",
        disabled=not all_fields_ready(),
    ):
        reset_analysis_state()
        st.session_state.step = 4
        st.rerun()

elif st.session_state.step == 4:
    if st.session_state.analysis is None:
        st.markdown("## 검토 중입니다...")
        progress = st.progress(0)
        status = st.empty()
        field_reports = []
        selected_fields = current_selected_fields()
        total_fields = max(1, len(selected_fields))

        for index, field in enumerate(selected_fields, start=1):
            config = get_field_input(field)
            field_scope = derive_field_scope(field)
            derived_codes = field_scope.get("derived_similarity_codes", [])
            derived_classes = field_scope.get("derived_nice_classes", field.get("nice_classes", [field["class_no"]]))
            selected_kind = field.get("kind", st.session_state.get("selected_kind"))
            effective_classes = list(derived_classes or [])
            if selected_kind == "services":
                normalized = []
                for value in effective_classes:
                    try:
                        normalized.append(int(str(value).strip()))
                    except ValueError:
                        continue
                if 35 not in normalized:
                    effective_classes.append(35)
            overlap_context = normalize_selected_input(
                selected_kind=selected_kind,
                selected_classes=effective_classes,
                selected_codes=derived_codes,
                selected_fields=[field],
                specific_product_text=config.get("specific_product", ""),
            )
            primary_codes = overlap_context.get("selected_primary_codes", [])
            related_codes = overlap_context.get("selected_related_codes", [])
            retail_codes = overlap_context.get("selected_retail_codes", [])
            status.markdown(f"🔎 {field_label(field)} KIPRIS 선행상표 검색 및 분석 중... ({index}/{total_fields})")
            all_results = []
            used_real_search = False

            search_plan = build_kipris_search_plan(
                st.session_state.trademark_name,
                effective_classes,
                primary_codes,
                related_codes=related_codes,
                retail_codes=retail_codes,
            )
            executed_queries = []
            
            # 검색 실패 여부 트래킹
            total_queries = 0
            success_queries = 0
            hard_fail_queries = 0
            soft_fail_queries = 0
            last_error_msg = ""

            for step in search_plan:
                query_word = step.get("word") or st.session_state.trademark_name
                codes = step.get("codes") or [""]
                for code in codes:
                    result = search_all_pages(
                        query_word,
                        similar_goods_code=code,
                        class_no=step.get("class_no"),
                        max_pages=step.get("max_pages", 3),
                        rows_per_page=20,
                        query_mode=step.get("query_mode", ""),
                        query_reason=step.get("query_reason", ""),
                        query_weight=step.get("query_weight", 1.0),
                        query_path=step.get("query_path", []) or [],
                    )
                    
                    search_status = result.get("search_status", "unknown")
                    is_success = result.get("success", False)
                    total_queries += 1
                    bucket = classify_query(is_success, search_status)
                    if bucket == "success":
                        success_queries += 1
                    elif bucket == "soft_success":
                        success_queries += 1
                        soft_fail_queries += 1
                        last_error_msg = result.get("result_msg", last_error_msg) or last_error_msg
                    else:
                        hard_fail_queries += 1
                        last_error_msg = result.get("result_msg", last_error_msg) or last_error_msg
                    
                    any_search_failed = (hard_fail_queries + soft_fail_queries) > 0

                    executed_queries.append(
                        {
                            "query_mode": step.get("query_mode", ""),
                            "search_mode": step.get("search_mode", result.get("search_mode", "mixed")),
                            "query_reason": step.get("query_reason", ""),
                            "query_weight": step.get("query_weight", 1.0),
                            "query_path": step.get("query_path", []) or [],
                            "word": query_word,
                            "class_no": step.get("class_no", ""),
                            "code": code,
                            "search_formula": step.get("search_formula", ""),
                            "result_count": len(result.get("items", [])) if result else 0,
                            "search_status": search_status,
                            "request_payload_summary": result.get("request_payload_summary", {}),
                            "extracted_total_count": result.get("extracted_total_count", 0),
                            "detail_parse_count": result.get("detail_parse_count", 0),
                            "http_status": result.get("http_status", 200),
                            "response_preview": result.get("response_text_preview", "")[:200],
                        }
                    )
                    if result and result.get("items"):
                        all_results.extend(result["items"])
                    if result and result.get("success") and not result.get("mock", False):
                        used_real_search = True

            # class search + SC search 결과를 union / dedup
            merged_count = len(all_results)
            all_results = dedupe_search_candidates(all_results)
            deduped_count = len(all_results)

            enrich_payload = enrich_search_results_with_item_details(all_results)
            all_results = dedupe_search_candidates(enrich_payload.get("items", []))
            detail_parse_count = int(enrich_payload.get("detail_parse_count", 0))
            detail_parse_error_count = int(enrich_payload.get("detail_parse_error_count", 0))

            field_analysis = evaluate_registration(
                trademark_name=st.session_state.trademark_name,
                trademark_type=st.session_state.trademark_type,
                is_coined=st.session_state.is_coined,
                selected_classes=effective_classes,
                selected_codes=derived_codes,
                prior_items=all_results,
                selected_fields=[field],
                specific_product=config.get("specific_product", ""),
            )
            
            search_health = summarize_health(
                total_queries=total_queries,
                success_queries=success_queries,
                hard_fail_queries=hard_fail_queries,
                soft_fail_queries=soft_fail_queries,
                last_error_msg=last_error_msg,
            )

            if search_health.should_cap_score:
                field_analysis["search_failed"] = True
                field_analysis["search_partial_failure"] = False
                field_analysis["search_error_msg"] = search_health.last_error_msg
                field_analysis["score_explanation"]["notes"].append(
                    "⚠️ KIPRIS 검색이 정상 완료되지 않아 결과를 확신할 수 없습니다. "
                    f"(성공 쿼리 0/{search_health.total_queries})"
                )
                if field_analysis.get("score", 0) > 50:
                    field_analysis["score"] = 50
                    field_analysis["band"] = get_score_band(50)
            elif search_health.any_fail:
                field_analysis["search_failed"] = False
                field_analysis["search_partial_failure"] = True
                field_analysis["search_error_msg"] = search_health.last_error_msg
                field_analysis["score_explanation"]["notes"].append(
                    "⚠️ KIPRIS 검색이 일부 실패/제한되어 결과 신뢰도가 낮을 수 있습니다. "
                    f"(성공 {search_health.success_queries}/{search_health.total_queries}, "
                    f"하드실패 {search_health.hard_fail_queries}, 소프트실패 {search_health.soft_fail_queries})"
                )
            else:
                field_analysis["search_failed"] = False
                field_analysis["search_partial_failure"] = False
                field_analysis["search_error_msg"] = ""

            field_reports.append(
                {
                    **field_analysis,
                    "field": field,
                    "specific_product": config.get("specific_product", ""),
                    "selected_group_id": field.get("group_id"),
                    "selected_subgroup_ids": [field.get("field_id", "")],
                    "selected_codes": list(derived_codes),
                    "selected_similarity_codes": list(derived_codes),
                    "selected_nice_classes": field_scope.get("derived_nice_classes", field.get("nice_classes", [])),
                    "selected_keywords": field_scope.get("subgroup_keywords", field.get("keywords", [])),
                    "selected_primary_codes": list(primary_codes),
                    "selected_related_codes": list(related_codes),
                    "selected_retail_codes": list(retail_codes),
                    "search_terms_for_prior_marks": field_scope.get("search_terms_for_prior_marks", []),
                    "search_plan": search_plan,
                    "executed_queries": executed_queries,
                    "merged_candidates": merged_count,
                    "deduped_candidates": deduped_count,
                    "detail_parse_count": detail_parse_count,
                    "detail_parse_error_count": detail_parse_error_count,
                    "search_source": "실제 KIPRIS 데이터" if used_real_search else "Mock 데이터 또는 제한 조회",
                    "search_health": {
                        "total_queries": search_health.total_queries,
                        "success_queries": search_health.success_queries,
                        "hard_fail_queries": search_health.hard_fail_queries,
                        "soft_fail_queries": search_health.soft_fail_queries,
                    },
                    "search_failed": field_analysis.get("search_failed", False),
                    "search_partial_failure": field_analysis.get("search_partial_failure", False),
                    "search_error_msg": field_analysis.get("search_error_msg", ""),
                    "improvements": get_improvements(
                        st.session_state.trademark_name,
                        derived_codes,
                        field_analysis.get("included_priors", []),
                        field_analysis.get("score", 0),
                    ),
                }
            )
            progress.progress(int(index / total_fields * 100))

        st.session_state.analysis = {"field_reports": field_reports}
        st.session_state.search_results = field_reports
        st.session_state.score = None
        st.session_state.search_source = "상품군별 개별 분석"

        status.markdown("✅ 상품군별 검토 완료!")
        time.sleep(0.5)
        st.rerun()

    analysis = st.session_state.analysis or {}
    field_reports = analysis.get("field_reports", [])
    st.markdown(f"## **'{st.session_state.trademark_name}'** 등록 가능성 검토 결과")
    st.markdown("### 검토결과입니다.")
    st.markdown("### 선택한 상품군별로 따로 판단한 결과입니다.")
    st.caption("유사군코드는 상품유사군코드.xlsx를 기준으로 자동 도출한 실제 예규 코드만 표시합니다.")
    st.markdown(
        """
        <div class="tip-box">
        본 결과는 AI 자동 분석 참고용이며, 최종 판단은 반드시 변리사와 상담 하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_auri(220)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("검토 상품군", f"{len(field_reports)}개")
    with col2:
        high_risk_fields = sum(1 for report in field_reports if report.get("actual_risk_prior_count", 0) > 0)
        st.metric("실제 충돌 위험 상품군", f"{high_risk_fields}개")
    with col3:
        st.metric("조어상표 여부", "예" if st.session_state.is_coined else "아니오")
    with col4:
        total_code_count = sum(len(report.get("selected_codes", [])) for report in field_reports)
        st.metric("선택 유사군코드", f"{total_code_count}개")

    for field_index, report in enumerate(field_reports, start=1):
        field = report.get("field", {})
        score = report.get("score", 0)
        results = report.get("included_priors", [])
        excluded_results = report.get("excluded_priors", [])
        total_results = report.get("total_prior_count", len(results) + len(excluded_results))
        css_class, emoji, label = get_result_style(score)
        color = "#FFFFFF" if score < 30 else "#2E7D32" if score >= 90 else "#1565C0" if score >= 70 else "#E65100" if score >= 50 else "#B71C1C"

        st.markdown("---")
        st.markdown(f"## {field_index}. {field_label(field)}")
        st.markdown(
            f"""
            <div class="card">
                <b>분류 1</b>: {report.get('selected_kind', field.get('kind', '-'))} |
                <b>분류 2</b>: {', '.join(report.get('selected_groups', [field.get('group_label', '-')]))} |
                <b>상품군</b>: {', '.join(report.get('selected_subgroups', [field.get('description', '-')]))}<br>
                <small style="color:#546E7A;">
                연결 니스류: {format_nice_classes(report.get('selected_nice_classes', field.get('nice_classes', [])))} |
                연결 유사군코드: {', '.join(report.get('selected_similarity_codes', report.get('selected_codes', []))) or '-'}
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="{css_class}">
                <h1 style="font-size:56px; margin:0; color:{color};">{score}%</h1>
                <h2 style="margin:8px 0; color:{color};">{emoji} {label}</h2>
                <p style="color:{color}; margin:0;">구체 상품: <b>{report.get('specific_product', '-')}</b> |
                코드: <b>{', '.join(report.get('selected_codes', []))}</b> |
                검색 출처: <b>{report.get('search_source', '-')}</b></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if report.get("search_failed"):
            st.warning("KIPRIS 검색이 실패하여 결과가 불확실합니다. (안전장치로 점수가 보수적으로 표시될 수 있습니다.)")
        elif report.get("search_partial_failure"):
            st.warning("KIPRIS 검색이 일부 실패/제한되어 결과 신뢰도가 낮을 수 있습니다.")

        sub1, sub2, sub3, sub4, sub5 = st.columns(5)
        with sub1:
            st.metric("전체 검색 건수", f"{total_results}건")
        with sub2:
            st.metric("필터 통과 건수", f"{report.get('filtered_prior_count', report.get('prior_count', 0))}건")
        with sub3:
            st.metric("실질 장애물", f"{report.get('direct_score_prior_count', 0)}건")
        with sub4:
            st.metric("역사적 참고자료", f"{report.get('historical_reference_count', 0)}건")
        with sub5:
            st.metric("제외된 후보 건수", f"{report.get('excluded_prior_count', len(excluded_results))}건")

        st.markdown("### 📊 점수 산정 및 등록 가능성 분석")
        score_explanation = report.get("score_explanation", {})
        stage1_cap = report.get("absolute_probability_cap", 95)
        stage2_score = report.get("stage2_relative_cap_adjusted", score)
        
        # 주된 거절 사유 판단
        is_stage1_main = stage1_cap < stage2_score and stage1_cap < 60
        is_stage2_main = stage2_score <= stage1_cap and stage2_score < 60
        
        if is_stage1_main:
            st.error(f"⚠️ **주요 거절 사유: 단어 자체의 식별력 부족 (Stage 1)**")
            st.markdown(f"선행상표와 상관없이, 상표법 제33조에 의거하여 단어 자체가 공익상 특정인에게 독점시킬 수 없는 성질을 가지고 있습니다. (상한선: {stage1_cap}%)")
        elif is_stage2_main:
            st.error(f"⚠️ **주요 거절 사유: 선행상표와의 충돌 위험 (Stage 2)**")
            st.markdown(f"유사한 선행상표가 이미 등록되어 있어 혼동의 우려가 있습니다. (상대적 점수: {stage2_score}%)")
        
        st.markdown(
            f"""
            <div class="card">
                <b>최종 점수 {report.get('score', 0)}% (원점수 {score_explanation.get('raw_score', report.get('score', 0))}%)</b><br>
                <small style="color:#546E7A;">{score_explanation.get('summary', '-')}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for note in score_explanation.get("notes", []):
            st.markdown(f"- {note}")
        if report.get("direct_score_prior_count", 0) == 0:
            st.markdown("- 상품 유사성 필터 통과 후보가 있어도 현재 살아있는 장애물이 없으면 최종 점수는 직접 감점하지 않습니다.")
        if report.get("absolute_risk_level") in {"high", "fatal"}:
            st.markdown(
                f"- Stage 1 절대적 거절사유 상한 {report.get('absolute_probability_cap', 95)}%가 먼저 적용되어 "
                "Stage 2 점수가 더 높아도 최종 점수는 다시 올라가지 않습니다."
            )
        st.markdown(
            """
            <div class="tip-box">
            완전 동일한 선행상표가 있으나 현재 상태가 거절/취하/포기/소멸인 경우, 원칙적으로 직접 장애물로 보지 않고 참고자료로만 봅니다.<br>
            등록 또는 출원 상태의 동일/유사 상표는 실질 장애물로 평가합니다.<br>
            거절 상표는 거절이유의 핵심이 현재 상표와 직접 관련되는 경우에만 보조 경고로 반영합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Stage 1 절대적 거절사유 / 식별력")
        distinctiveness = report.get("absolute_refusal_analysis", report.get("distinctiveness_analysis", {}))
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('distinctiveness', '-')}</b><br>
                <small style="color:#546E7A;">{distinctiveness.get('summary', '-')}</small><br>
                <small style="color:#546E7A;">risk {report.get('absolute_risk_level', 'none')} / cap {report.get('absolute_probability_cap', 95)}% / 식별력 점수 {report.get('distinctiveness_score', 0)}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if report.get("absolute_refusal_bases"):
            st.markdown(f"- 절대적 거절사유 근거: {', '.join(report.get('absolute_refusal_bases', []))}")
        if report.get("acquired_distinctiveness_needed"):
            st.markdown("- 사용에 의한 식별력 취득 보완 검토가 필요한 유형으로 분류했습니다.")
        for reason in distinctiveness.get("reasons", []):
            st.markdown(f"- {reason}")

        st.markdown("### Stage 2 상대적 거절사유 / 상품 유사성")
        product_analysis = report.get("product_similarity_analysis", {})
        bucket_counts = product_analysis.get("bucket_counts", {})
        st.markdown(
            f"""
            <div class="card">
                <b>{product_analysis.get('summary', '-')}</b><br>
                <small style="color:#546E7A;">
                동일 유사군코드 {bucket_counts.get('same_code', 0)}건 /
                동일 류 {bucket_counts.get('same_class', 0)}건 /
                타 류 예외군 {bucket_counts.get('exception', 0)}건 /
                제외 {bucket_counts.get('excluded', 0)}건
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"- {product_analysis.get('exclusion_reason_summary', report.get('exclusion_reason_summary', '-'))}")

        st.markdown("### 표장 유사성 검토 결과")
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('mark_similarity_analysis', {}).get('summary', '-')}</b><br>
                <small style="color:#546E7A;">기존 문자열 유사도와 발음 유사 보조 로직은 유지하되, 상품 유사성 필터 통과 후보에만 적용했습니다.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if results:
            for item in results[:3]:
                st.markdown(
                    f"- `{item['trademarkName']}`: 외관 {item.get('appearance_similarity', 0)}%, "
                    f"호칭 {item.get('phonetic_similarity', 0)}%, "
                    f"관념 {item.get('conceptual_similarity', 0)}%, "
                    f"표장 유사도 {item.get('mark_similarity', 0)}%"
                )
        else:
            st.markdown("- 상품 유사성 필터를 통과한 후보가 없어 표장 유사도는 강한 감점에 쓰지 않았습니다.")

        st.markdown("### 혼동 가능성 종합")
        st.markdown(
            f"""
            <div class="card">
                <b>{report.get('confusion_analysis', {}).get('summary', '-')}</b><br>
                <small style="color:#546E7A;">
                검색 출처: {report.get('search_source', '-')} |
                실질 장애물 {report.get('direct_score_prior_count', 0)}건 /
                역사적 참고자료 {report.get('historical_reference_count', 0)}건
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if report.get("reference_summary"):
            st.markdown(f"- {report.get('reference_summary')}")

        if results:
            st.markdown("### 주요 선행상표 목록")
            debug_hits = st.checkbox(
                "디버그 모드: 선행상표가 어떤 검색 경로로 발견됐는지 보기",
                value=False,
                key=f"debug_hit_sources_{field_index}",
            )
            for index, item in enumerate(results[:10]):
                confusion_score = item.get("confusion_score", 0)
                if confusion_score >= 75:
                    card_class = "trademark-high"
                    risk_label = "높은 위험"
                    bar_color = "#F44336"
                elif confusion_score >= 55:
                    card_class = "trademark-medium"
                    risk_label = "주의"
                    bar_color = "#FF9800"
                else:
                    card_class = "trademark-low"
                    risk_label = "낮은 위험"
                    bar_color = "#4CAF50"

                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <table style="width:100%; border:none;">
                        <tr>
                            <td style="width:60%">
                                <b>{index + 1}. {item['trademarkName']}</b> &nbsp; {risk_label}<br>
                                <small>출원번호: {item['applicationNumber']} | 출원일: {item['applicationDate']}</small><br>
                                <small>상태: {item.get('status_normalized', item['registerStatus'])} | 생존성 분류: {item.get('survival_label', '-')} | 류: {item['classificationCode']}</small><br>
                                <small>출원인: {item['applicantName']} | 점수 반영 여부: {item.get('score_reflection_label', '-')}</small><br>
                                <small>상품군 판단: {item.get('product_similarity_label', '-')} | {item.get('product_reason', '-')}</small><br>
                                <small>표장 동일성: {item.get('mark_identity_label', '-')}</small><br>
                                {f"<small>배지: {_format_exact_override_badges(item)}</small><br>" if _format_exact_override_badges(item) else ""}
                                {f"<small>exact override 상세: {_format_exact_override_details(item)}</small><br>" if _format_exact_override_details(item) else ""}
                                {f"<small>참고: 완전 동일표장 사건에서는 발음 분석은 보조 설명이며 위험도를 낮추는 근거로 사용하지 않습니다.</small><br>" if (isinstance(item.get('exact_override'), dict) and item.get('exact_override', {}).get('should_override')) else ""}
                                <small>검색 경로: {_format_hit_sources_brief(item.get('hit_sources', []) or [], limit=3)}</small>
                            </td>
                            <td style="width:40%; text-align:right; vertical-align:top;">
                                <b style="font-size:20px;">혼동 위험 {confusion_score}%</b><br>
                                <small>표장 {item.get('mark_similarity', 0)}% / 상품 {item.get('product_similarity_score', 0)}%</small><br>
                                <div style="background:#ddd; border-radius:4px; height:8px; margin-top:4px;">
                                    <div style="background:{bar_color}; width:{confusion_score}%; height:8px; border-radius:4px;"></div>
                                </div>
                                <br>
                                <a href="https://www.kipris.or.kr" target="_blank" style="color:#2196F3; font-size:12px;">KIPRIS에서 보기 →</a>
                            </td>
                        </tr>
                        </table>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                refusal = item.get("refusal_analysis", {})
                if refusal.get("reason_summary"):
                    st.markdown(
                        f"- 거절이유 요약: {refusal.get('reason_summary')} "
                        f"(현재 상표 관련성: {refusal.get('current_mark_relevance_label', '-')})"
                    )
                if refusal.get("cited_marks"):
                    st.markdown(f"- 인용상표: {', '.join(refusal.get('cited_marks', []))}")
                if refusal.get("weak_elements") or refusal.get("refusal_core"):
                    st.markdown(
                        f"- 약한 요소: {', '.join(refusal.get('weak_elements', [])) or '-'} / "
                        f"거절 핵심 요부: {refusal.get('refusal_core', '-') or '-'}"
                    )

            st.markdown("### 데이터 표 보기")
            result_df = pd.DataFrame(
                [
                    {
                        "상표명": row["trademarkName"],
                        "혼동위험": f'{row.get("confusion_score", 0)}%',
                        "표장유사도": f'{row.get("mark_similarity", 0)}%',
                        "상품판단": row.get("product_similarity_label", "-"),
                        "상태": row.get("status_normalized", row["registerStatus"]),
                        "생존성": row.get("survival_label", "-"),
                        "점수반영": row.get("score_reflection_label", "-"),
                        "류": row["classificationCode"],
                        "출원인": row["applicantName"],
                        "검색경로": _format_hit_sources_brief(row.get("hit_sources", []) or [], limit=2),
                        "exact_override": "Y" if (isinstance(row.get("exact_override"), dict) and row.get("exact_override", {}).get("should_override")) else "",
                    }
                    for row in results[:10]
                ]
            )
            styled_df = result_df.style.map(similarity_cell_style, subset=["혼동위험", "표장유사도"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            if debug_hits:
                hit_rows = []
                for row in (results[:10] + excluded_results[:10]):
                    hit_rows.extend(_build_hit_source_rows(row))
                if hit_rows:
                    st.markdown("### 검색 근거(디버그)")
                    st.dataframe(pd.DataFrame(hit_rows), use_container_width=True, hide_index=True)
                    override_rows = []
                    for row in (results[:10] + excluded_results[:10]):
                        ex = row.get("exact_override", {}) if isinstance(row.get("exact_override"), dict) else {}
                        override_rows.append(
                            {
                                "상표명": strip_html(row.get("trademarkName", "")),
                                "출원번호": str(row.get("applicationNumber", "")),
                                "mark_identity": str(row.get("mark_identity", "")),
                                "exact_override": bool(ex.get("should_override")),
                                "original_overlap_type": str(ex.get("original_overlap_type", row.get("overlap_type_original", "")) or ""),
                                "final_overlap_type": str(ex.get("final_overlap_type", row.get("overlap_type", "")) or ""),
                                "original_product_score": int(ex.get("original_product_similarity_score", row.get("product_similarity_score_original", 0)) or 0),
                                "adjusted_product_score": int(ex.get("adjusted_product_similarity_score", row.get("product_similarity_score", 0)) or 0),
                            }
                        )
                    st.markdown("### exact override(디버그)")
                    st.dataframe(pd.DataFrame(override_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("표시할 검색 근거(hit_sources)가 없습니다.")
        else:
            st.markdown(
                """
                <div style="background:#E8F5E9; border:2px solid #4CAF50; border-radius:12px; padding:20px; text-align:center;">
                    <h3 style="color:#2E7D32;">상품 유사성 검토를 통과한 선행상표가 없어요!</h3>
                    <p style="color:#388E3C;">타 류·타 코드 후보는 점수에서 제외했고,<br>
                    등록 가능성이 매우 높습니다!</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if excluded_results:
            st.markdown(
                f"""
                <div class="tip-box" style="margin-top:12px;">
                검색 결과가 있었지만 상품 유사성 검토에서 제외된 후보 {len(excluded_results)}건은 최종 점수와 top_prior에 반영하지 않았습니다.
                예: {', '.join(row['trademarkName'] for row in excluded_results[:3])}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="tip-box" style="margin-top:16px;">
        본 결과는 AI 자동 분석 참고용이며, 최종 판단은 반드시 변리사와 상담 하세요.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("등록 가능성 높이기", use_container_width=True, type="primary"):
            st.session_state.step = 5
            st.rerun()
    with col2:
        st.download_button(
            "PDF로 출력하기",
            data=generate_report_pdf(build_report_payload()),
            file_name=f"{st.session_state.trademark_name}_검토보고서.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with col3:
        if st.button("처음부터 다시", use_container_width=True):
            reset_session()
            st.rerun()

elif st.session_state.step == 5:
    st.markdown("## 등록 가능성을 높이는 방법")
    st.markdown("### 선택한 상품군별 개선안을 따로 제안합니다.")

    for index, report in enumerate((st.session_state.analysis or {}).get("field_reports", []), start=1):
        improvements = report.get("improvements", {})
        field = report.get("field", {})
        current_score = report.get("score", 0)

        st.markdown("---")
        st.markdown(f"## {index}. {field_label(field)}")
        st.markdown(f"현재: **{st.session_state.trademark_name}** / **{report.get('specific_product', '-') }** / **{current_score}%**")

        st.markdown("### 방법 1: 상표명 변경")
        st.markdown(
            """
        <div class="tip-box">
        현재 상표명과 발음이 다른 새로운 이름을 사용하면 등록 가능성이 높아져요.
        </div>
        """,
            unsafe_allow_html=True,
        )

        for suggestion in improvements.get("name_suggestions", []):
            score_value = suggestion.get("score", 0)
            if score_value >= 90:
                color, bg = "#2E7D32", "#E8F5E9"
            elif score_value >= 70:
                color, bg = "#1565C0", "#E3F2FD"
            else:
                color, bg = "#E65100", "#FFF3E0"

            st.markdown(
                f"""
                <div style="background:{bg}; border-radius:8px; padding:12px 16px; margin:6px 0; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <b style="font-size:18px;">{suggestion['name']}</b><br>
                        <small style="color:#546E7A">{suggestion.get('reason', '')}</small>
                    </div>
                    <div style="text-align:right;">
                        <b style="font-size:22px; color:{color};">예상 {score_value}%</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 방법 2: 상품 범위 조정")
        for suggestion in improvements.get("code_suggestions", []):
            st.markdown(
                f"""
                <div style="background:#E3F2FD; border-radius:8px; padding:12px 16px; margin:6px 0;">
                    <b>{suggestion['description']}</b><br>
                    <small style="color:#546E7A">{suggestion.get('reason', '')}</small><br>
                    <b style="color:#1565C0;">→ 예상 {suggestion.get('expected_score', 0)}%로 향상</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 방법 3: 다른 상품군 검토")
        for suggestion in improvements.get("class_suggestions", []):
            st.markdown(
                f"""
                <div style="background:#F1F8E9; border-radius:8px; padding:12px 16px; margin:6px 0;">
                    <b>{suggestion['description']}</b><br>
                    <small style="color:#546E7A">{suggestion.get('reason', '')}</small><br>
                    <b style="color:#2E7D32;">→ 예상 {suggestion.get('expected_score', 0)}%로 향상</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
    <div class="tip-box" style="margin-top:24px;">
    본 결과는 AI 자동 분석 참고용이며, 최종 판단은 반드시 변리사와 상담 하세요.
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 결과로 돌아가기", use_container_width=True):
            st.session_state.step = 4
            st.rerun()
    with col2:
        if st.button("처음부터 다시", use_container_width=True):
            reset_session()
            st.rerun()
