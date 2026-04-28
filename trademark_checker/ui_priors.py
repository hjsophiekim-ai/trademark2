from __future__ import annotations

from scoring import strip_html


FORBIDDEN_UI_FRAGMENTS = (
    "<td",
    "<tr",
    "<div style=",
    "검색 경로:",
    "hit_sources",
    "query_reason",
    "unsafe_allow_html",
)


def safe_inline_text(value: object) -> str:
    text = strip_html(str(value or ""))
    return text.replace("<", " ").replace(">", " ").replace("\n", " ").strip()


def risk_badge_from_confusion(confusion_score: int) -> dict:
    score = int(confusion_score or 0)
    if score >= 75:
        return {"label": "높은 위험", "level": "high"}
    if score >= 55:
        return {"label": "주의", "level": "medium"}
    return {"label": "낮은 위험", "level": "low"}


def build_prior_user_view_model(item: dict, rank: int) -> dict:
    confusion_score = int(item.get("confusion_score", 0) or 0)
    mark_similarity = int(item.get("mark_similarity", item.get("similarity", 0)) or 0)
    product_similarity = int(item.get("product_similarity_score", 0) or 0)

    badge = risk_badge_from_confusion(confusion_score)
    name = safe_inline_text(item.get("trademarkName", "-")) or "-"
    application_number = safe_inline_text(item.get("applicationNumber", "-")) or "-"
    application_date = safe_inline_text(item.get("applicationDate", "-")) or "-"
    status = safe_inline_text(item.get("status_normalized", item.get("registerStatus", "-"))) or "-"
    class_code = safe_inline_text(item.get("classificationCode", "-")) or "-"
    applicant = safe_inline_text(item.get("applicantName", "-")) or "-"
    product_label = safe_inline_text(item.get("product_similarity_label", "-")) or "-"

    return {
        "rank": int(rank),
        "trademark_name": name,
        "risk_label": badge["label"],
        "risk_level": badge["level"],
        "application_number": application_number,
        "application_date": application_date,
        "status": status,
        "class_code": class_code,
        "applicant": applicant,
        "confusion_score": confusion_score,
        "mark_similarity": mark_similarity,
        "product_similarity": product_similarity,
        "product_summary": product_label,
        "kipris_url": "https://www.kipris.or.kr",
    }


def contains_forbidden_fragments(text: str) -> bool:
    raw = str(text or "")
    lowered = raw.lower()
    for fragment in FORBIDDEN_UI_FRAGMENTS:
        if str(fragment).lower() in lowered:
            return True
    return False

