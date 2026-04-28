from __future__ import annotations

from ui_priors import build_prior_user_view_model, contains_forbidden_fragments


def test_user_view_model_removes_markup_fragments() -> None:
    item = {
        "trademarkName": "오렌G트리</td><td style=\"width:40%\">",
        "applicationNumber": "12345</tr>",
        "applicationDate": "20200101",
        "registerStatus": "등록",
        "status_normalized": "등록",
        "classificationCode": "36",
        "applicantName": "<div style=\"background:#ddd\">ACME</div>",
        "confusion_score": 69,
        "mark_similarity": 84,
        "product_similarity_score": 45,
        "product_similarity_label": "동일 류 내 근접 서비스업(경제적 견련성)",
        "hit_sources": [{"query_reason": "phonetic_variant", "term": "X"}],
    }
    model = build_prior_user_view_model(item, 1)
    combined = " | ".join([str(v) for v in model.values()])
    assert not contains_forbidden_fragments(combined)


def test_user_view_model_contains_required_fields() -> None:
    item = {
        "trademarkName": "오렌G트리",
        "applicationNumber": "4020200012399",
        "applicationDate": "20200801",
        "registerStatus": "등록",
        "classificationCode": "36",
        "applicantName": "주식회사오렌G트리",
        "confusion_score": 69,
        "mark_similarity": 84,
        "product_similarity_score": 45,
        "product_similarity_label": "동일 류 내 근접 서비스업(경제적 견련성)",
    }
    model = build_prior_user_view_model(item, 1)
    assert model["trademark_name"] == "오렌G트리"
    assert model["risk_label"]
    assert model["status"]
    assert model["class_code"] == "36"
    assert model["confusion_score"] == 69
    assert model["kipris_url"].startswith("https://")

