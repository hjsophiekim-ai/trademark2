"""상표 등록 가능성 분석 로직."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List

from similarity_code_db import get_code_metadata


COMMON_WORDS = {"사랑", "사랑해", "브랜드", "맛있는", "행복", "좋은", "예쁜", "최고"}
STATUS_WEIGHT = {
    "등록": 1.0,
    "출원": 0.78,
    "심사": 0.7,
    "공고": 0.86,
    "거절": 0.3,
    "포기": 0.2,
    "무효": 0.2,
    "취하": 0.2,
    "소멸": 0.2,
}
ECONOMIC_LINKS = {
    frozenset({"3", "35"}),
    frozenset({"5", "35"}),
    frozenset({"5", "44"}),
    frozenset({"9", "42"}),
    frozenset({"10", "44"}),
    frozenset({"14", "35"}),
    frozenset({"16", "41"}),
    frozenset({"18", "35"}),
    frozenset({"20", "35"}),
    frozenset({"25", "35"}),
    frozenset({"30", "43"}),
    frozenset({"31", "35"}),
    frozenset({"31", "44"}),
    frozenset({"39", "43"}),
}
GROUP_ALIAS = {
    "same_code": "group_exact_code",
    "same_class": "group_same_class",
    "exception": "group_related_market",
    "excluded": "group_irrelevant",
}
GROUP_LABEL = {
    "group_exact_code": "동일 유사군코드",
    "group_same_class": "동일 류",
    "group_related_market": "경제적 견련성 있는 타 류",
    "group_irrelevant": "무관한 타 류",
}


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _normalize(text: str) -> str:
    cleaned = strip_html(text).lower().strip()
    return "".join(ch for ch in cleaned if ch.isalnum() or ("가" <= ch <= "힣"))


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", strip_html(text or "")).lower()


def _clean_class_text(value: str) -> str:
    digits = re.findall(r"\d+", str(value or ""))
    if not digits:
        return ""
    return str(int(digits[0]))


def _extract_classes(value: str | Iterable[int] | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = list(value)

    classes = []
    for item in raw:
        class_no = _clean_class_text(str(item))
        if class_no and class_no not in classes:
            classes.append(class_no)
    return classes


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", strip_html(text or "").lower())
    return [token for token in tokens if len(token) >= 2]


def _status_weight(status: str) -> float:
    text = strip_html(status)
    for key, weight in STATUS_WEIGHT.items():
        if key in text:
            return weight
    return 0.55


def _is_sales_code(code: str) -> bool:
    return str(code or "").upper().startswith("S")


def similarity_percent(source: str, target: str) -> int:
    left = _normalize(source)
    right = _normalize(target)
    if not left or not right:
        return 0
    ratio = SequenceMatcher(None, left, right).ratio()
    if left == right:
        ratio = 1.0
    elif left in right or right in left:
        ratio = max(ratio, 0.86)
    return int(round(ratio * 100))


def _phonetic_similar(a: str, b: str) -> bool:
    """기존 backup/app.py의 단순 발음 유사 규칙을 유지한다."""
    if len(a) < 3 or len(b) < 3:
        return False
    return a[:3] == b[:3] and abs(len(a) - len(b)) <= 2


def _phonetic_similarity_percent(source: str, target: str) -> int:
    left = _compact(source).upper()
    right = _compact(target).upper()
    if not left or not right:
        return 0
    base = similarity_percent(source, target)
    if left == right:
        return 100
    if _phonetic_similar(left, right):
        return max(base, 84)
    if left[:2] == right[:2]:
        return max(base, 72)
    return base


def _concept_similarity_percent(source: str, target: str) -> int:
    left = set(_tokenize(source))
    right = set(_tokenize(target))
    if not left or not right:
        return 0
    if left == right:
        return 100
    overlap = left & right
    if overlap:
        return min(95, 55 + len(overlap) * 15)
    left_text = _normalize(source)
    right_text = _normalize(target)
    if left_text and right_text and (left_text in right_text or right_text in left_text):
        return 70
    return 0


def _mark_similarity(appearance: int, phonetic: int, conceptual: int, trademark_type: str) -> int:
    if trademark_type == "로고만":
        score = appearance * 0.6 + phonetic * 0.2 + conceptual * 0.2
    elif trademark_type == "문자+로고":
        score = appearance * 0.4 + phonetic * 0.4 + conceptual * 0.2
    else:
        score = appearance * 0.25 + phonetic * 0.5 + conceptual * 0.25
    return int(round(score))


def _selected_classes(selected_classes: Iterable[int | str], selected_fields: Iterable[dict]) -> list[str]:
    classes = _extract_classes(selected_classes)
    for field in selected_fields:
        class_no = _clean_class_text(field.get("class_no", field.get("류", "")))
        if class_no and class_no not in classes:
            classes.append(class_no)
    return classes


def _selected_context(
    selected_classes: Iterable[int | str],
    selected_codes: Iterable[str],
    selected_fields: Iterable[dict],
    specific_product: str,
) -> dict:
    class_list = _selected_classes(selected_classes, selected_fields)
    codes = [code for code in selected_codes if str(code).strip()]
    code_meta = [get_code_metadata(code) for code in codes]
    code_meta = [row for row in code_meta if row]
    text_fragments = [specific_product]
    text_fragments.extend(field.get("description", field.get("설명", "")) for field in selected_fields)
    text_fragments.extend(field.get("example", field.get("예시", "")) for field in selected_fields)
    text_fragments.extend(row.get("name", "") for row in code_meta)
    text_fragments.extend(row.get("설명", "") for row in code_meta)
    return {
        "classes": class_list,
        "codes": codes,
        "goods_codes": [code for code in codes if not _is_sales_code(code)],
        "sales_codes": [code for code in codes if _is_sales_code(code)],
        "code_meta": code_meta,
        "tokens": set(token for fragment in text_fragments for token in _tokenize(fragment)),
        "specific_product": specific_product,
        "field_labels": [field.get("description", field.get("설명", "")) for field in selected_fields],
    }


def _distinctiveness_analysis(
    trademark_name: str,
    is_coined: bool,
    trademark_type: str,
    specific_product: str,
    selected_fields: Iterable[dict],
) -> dict:
    normalized = _normalize(trademark_name)
    reasons: list[str] = []
    score_adjustment = 0

    if is_coined:
        score_adjustment += 18
        reasons.append("조어상표로 입력되어 식별력 측면에서 유리합니다.")
    else:
        score_adjustment -= 8
        reasons.append("일반 단어 계열로 입력되어 식별력은 조어상표보다 약하게 봅니다.")

    if len(normalized) <= 2:
        score_adjustment -= 12
        reasons.append("문자 수가 짧아 제33조 제1항 제6호(간단하고 흔한 표장) 위험이 있습니다.")
    elif len(normalized) >= 6:
        score_adjustment += 3

    if not is_coined and normalized in COMMON_WORDS:
        score_adjustment -= 14
        reasons.append("일상적 표현과 가까워 보통명칭·관용표장으로 보일 위험이 있습니다.")

    name_tokens = set(_tokenize(trademark_name))
    context_tokens = set(_tokenize(specific_product))
    for field in selected_fields:
        context_tokens.update(_tokenize(field.get("description", field.get("설명", ""))))
    descriptive_overlap = sorted(name_tokens & context_tokens)
    if descriptive_overlap and not is_coined:
        score_adjustment -= 10
        reasons.append(
            "지정상품과 직접 맞닿는 표현이 포함되어 성질표시(제33조) 쟁점이 생길 수 있습니다: "
            + ", ".join(descriptive_overlap[:3])
        )

    if trademark_type == "문자+로고":
        score_adjustment += 2
    elif trademark_type == "로고만":
        score_adjustment += 1

    if score_adjustment <= -20:
        label = "거절 가능성 큼"
        level = "high"
    elif score_adjustment < 0:
        label = "식별력 약함"
        level = "medium"
    elif is_coined:
        label = "식별력 문제 없음"
        level = "low"
    else:
        label = "보통 수준"
        level = "low"

    return {
        "label": label,
        "level": level,
        "score_adjustment": score_adjustment,
        "reasons": reasons,
        "summary": reasons[0] if reasons else "식별력상 특별한 약점은 크지 않습니다.",
    }


def _normalize_prior_item(item: dict, trademark_name: str) -> dict:
    name = strip_html(item.get("trademarkName", item.get("trademark_name", "알 수 없음")))
    classes = _extract_classes(item.get("classificationCode", item.get("class", "")))
    queried_codes = [code for code in item.get("queried_codes", []) if str(code).strip()]
    return {
        "trademarkName": name,
        "applicationNumber": item.get("applicationNumber", item.get("application_number", "-")),
        "applicationDate": item.get("applicationDate", item.get("application_date", "-")),
        "registerStatus": item.get("registerStatus", item.get("registrationStatus", item.get("status", "-"))),
        "applicantName": strip_html(item.get("applicantName", item.get("applicant", "-"))),
        "classificationCode": ",".join(classes) if classes else item.get("classificationCode", item.get("class", "-")),
        "classes": classes,
        "similarity": similarity_percent(trademark_name, name),
        "queried_codes": queried_codes,
        "similarityGroupCode": item.get("similarityGroupCode") or item.get("similarGoodsCode") or "",
    }


def _merge_prior_items(items: List[dict], trademark_name: str) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for item in items:
        normalized = _normalize_prior_item(item, trademark_name)
        key = (normalized["applicationNumber"], normalized["trademarkName"])
        current = merged.get(key)
        if current is None:
            merged[key] = normalized
            continue
        current_codes = set(current.get("queried_codes", []))
        current_codes.update(normalized.get("queried_codes", []))
        current["queried_codes"] = sorted(current_codes)
        current_classes = set(current.get("classes", []))
        current_classes.update(normalized.get("classes", []))
        current["classes"] = sorted(current_classes, key=int)
        current["classificationCode"] = ",".join(current["classes"]) if current["classes"] else current["classificationCode"]
        current["similarity"] = max(current["similarity"], normalized["similarity"])
    return sorted(merged.values(), key=lambda row: row["similarity"], reverse=True)


def _has_economic_link(selected_classes: list[str], item_classes: list[str]) -> bool:
    for selected in selected_classes:
        for item_class in item_classes:
            if frozenset({selected, item_class}) in ECONOMIC_LINKS:
                return True
    return False


def _item_code_tokens(code: str) -> set[str]:
    if not code:
        return set()
    row = get_code_metadata(code)
    if not row:
        return set()
    fragments = [row.get("name", ""), row.get("설명", ""), row.get("기준상품", "")]
    return {token for fragment in fragments for token in _tokenize(fragment)}


def _product_similarity(item: dict, context: dict) -> dict:
    selected_classes = context["classes"]
    selected_codes = context["codes"]
    selected_goods_codes = context["goods_codes"]
    item_classes = item.get("classes", [])
    shared_classes = [class_no for class_no in item_classes if class_no in selected_classes]
    explicit_code = item.get("similarityGroupCode", "")
    code_match = explicit_code in selected_codes if explicit_code else False

    if code_match:
        if _is_sales_code(explicit_code):
            return {
                "bucket": "same_class",
                "group": GROUP_ALIAS["same_class"],
                "label": "동일 판매업 코드(제한 반영)",
                "score": 36,
                "penalty_weight": 0.48,
                "strict_same_code": False,
                "include": True,
                "reason": f"선택 판매업 코드 {explicit_code}와 일치하지만 문서 기준에 따라 제한적으로만 반영합니다.",
            }
        return {
            "bucket": "same_code",
            "group": GROUP_ALIAS["same_code"],
            "label": "동일 유사군코드",
            "score": 95,
            "penalty_weight": 1.7,
            "strict_same_code": True,
            "include": True,
            "reason": f"선택 유사군코드 {explicit_code}와 직접 일치합니다.",
        }

    if shared_classes:
        item_tokens = _item_code_tokens(explicit_code)
        overlap_tokens = sorted(context["tokens"] & item_tokens)
        if explicit_code and item_tokens and overlap_tokens and explicit_code not in selected_goods_codes:
            return {
                "bucket": "same_class",
                "group": GROUP_ALIAS["same_class"],
                "label": "동일 류 인접 상품군",
                "score": 54,
                "penalty_weight": 0.92,
                "strict_same_code": False,
                "include": True,
                "reason": (
                    f"동일 류이며 유사군코드는 다르지만 상품 문맥이 맞닿아 있어 보조 검토군으로 포함합니다: "
                    + ", ".join(overlap_tokens[:3])
                ),
            }
        return {
            "bucket": "same_class",
            "group": GROUP_ALIAS["same_class"],
            "label": "동일 류 검토군",
            "score": 40,
            "penalty_weight": 0.68,
            "strict_same_code": False,
            "include": True,
            "reason": (
                f"선택 류 {', '.join(selected_classes)}와 선행상표 류 {', '.join(shared_classes)}가 겹치지만 "
                "문서 기준상 동일 류만으로는 자동 충돌로 보지 않아 보조 검토군으로만 반영합니다."
            ),
        }

    if _has_economic_link(selected_classes, item_classes):
        return {
            "bucket": "exception",
            "group": GROUP_ALIAS["exception"],
            "label": "타 류 예외군",
            "score": 24,
            "penalty_weight": 0.18,
            "strict_same_code": False,
            "include": True,
            "reason": "다른 류이지만 판매업·서비스업 등 경제적 견련성이 있어 예외 검토군으로 남깁니다.",
        }

    return {
        "bucket": "excluded",
        "group": GROUP_ALIAS["excluded"],
        "label": "검토 제외",
        "score": 0,
        "penalty_weight": 0.0,
        "strict_same_code": False,
        "include": False,
        "reason": "선택한 류·유사군코드와 직접적인 상품 관련성이 낮아 점수 반영에서 제외합니다.",
    }


def _enrich_mark_similarity(item: dict, trademark_name: str, trademark_type: str) -> dict:
    appearance = item["similarity"]
    phonetic = _phonetic_similarity_percent(trademark_name, item["trademarkName"])
    conceptual = _concept_similarity_percent(trademark_name, item["trademarkName"])
    mark_similarity = _mark_similarity(appearance, phonetic, conceptual, trademark_type)
    return {
        **item,
        "appearance_similarity": appearance,
        "phonetic_similarity": phonetic,
        "conceptual_similarity": conceptual,
        "mark_similarity": mark_similarity,
    }


def _confusion_metrics(item: dict) -> dict:
    product_score = item["product_similarity_score"]
    mark_score = item["mark_similarity"]
    status_weight = _status_weight(item["registerStatus"])
    confusion_score = int(round((mark_score * 0.58 + product_score * 0.42) * (0.72 + status_weight * 0.28)))

    if confusion_score >= 82:
        label = "높음"
    elif confusion_score >= 65:
        label = "중간"
    elif confusion_score >= 45:
        label = "낮음"
    else:
        label = "매우 낮음"

    return {
        **item,
        "confusion_score": confusion_score,
        "confusion_label": label,
    }


def _score_from_analysis(
    trademark_name: str,
    candidates: list[dict],
    distinctiveness: dict,
    is_coined: bool,
    trademark_type: str,
) -> int:
    score = 72 + distinctiveness["score_adjustment"]
    normalized = _normalize(trademark_name)

    if trademark_type == "문자+로고":
        score += 2
    elif trademark_type == "로고만":
        score += 1

    if len(normalized) >= 6:
        score += 3
    elif len(normalized) <= 2:
        score -= 8

    if " " in trademark_name.strip():
        score -= 3

    if not is_coined and normalized in COMMON_WORDS:
        score -= 8

    for item in candidates:
        group_weight = item.get("product_penalty_weight", {
            "same_code": 1.7,
            "same_class": 1.4,
            "exception": 0.22,
        }.get(item["product_bucket"], 0.0))
        penalty = (
            item["mark_similarity"] / 100
            * item["product_similarity_score"] / 100
            * _status_weight(item["registerStatus"])
            * 45
            * group_weight
        )
        score -= penalty

    severe_conflict = any(
        item["product_similarity_score"] >= 85 and item["mark_similarity"] >= 90 and item["confusion_score"] >= 88
        for item in candidates
    )
    if not severe_conflict:
        score = max(score, 12)

    return max(0, min(100, int(round(score))))


def _group_counts(bucket_counts: dict) -> dict:
    return {
        GROUP_ALIAS["same_code"]: bucket_counts.get("same_code", 0),
        GROUP_ALIAS["same_class"]: bucket_counts.get("same_class", 0),
        GROUP_ALIAS["exception"]: bucket_counts.get("exception", 0),
        GROUP_ALIAS["excluded"]: bucket_counts.get("excluded", 0),
    }


def _grouped_priors(included: list[dict], excluded: list[dict]) -> dict:
    grouped = {alias: [] for alias in GROUP_LABEL}
    for item in included + excluded:
        grouped[item.get("group_name", GROUP_ALIAS.get(item.get("product_bucket", "excluded"), GROUP_ALIAS["excluded"]))].append(item)
    return grouped


def _build_exclusion_summary(excluded: list[dict]) -> str:
    if not excluded:
        return "상품 유사성 검토에서 제외된 후보가 없습니다."
    reasons = {}
    for item in excluded:
        reason = item.get("product_reason", "상품 관련성 부족")
        reasons[reason] = reasons.get(reason, 0) + 1
    summary = ", ".join(f"{reason} {count}건" for reason, count in list(reasons.items())[:3])
    return (
        f"검색 결과 {len(excluded)}건은 상품 유사성 필터에서 제외되어 최종 점수와 top_prior에는 반영하지 않았습니다. "
        f"주요 제외 사유: {summary}"
    )


def _calibrate_score(
    raw_score: int,
    included: list[dict],
    distinctiveness: dict,
    is_coined: bool,
) -> tuple[int, list[str]]:
    explanations = []
    filtered_count = len(included)
    actual_risk_count = sum(1 for item in included if item.get("confusion_score", 0) >= 65)
    same_code_high = [
        item
        for item in included
        if item.get("product_bucket") == "same_code"
        and item.get("strict_same_code", False)
        and max(item.get("mark_similarity", 0), item.get("phonetic_similarity", 0)) >= 85
    ]
    same_class_medium = [
        item
        for item in included
        if item.get("product_bucket") == "same_class"
        and item.get("product_similarity_score", 0) >= 40
        and item.get("mark_similarity", 0) >= 70
    ]
    related_only = bool(included) and all(item.get("product_bucket") == "exception" for item in included)

    calibrated = raw_score

    if filtered_count == 0:
        if distinctiveness["level"] == "high":
            low, high = 60, 72
            explanations.append("식별력 자체가 강하게 약해 충돌 후보가 없어도 60~72 구간에서 점수를 형성했습니다.")
        elif distinctiveness["level"] == "medium":
            low, high = 72, 82
            explanations.append("식별력 약함은 있으나 상품 유사성 필터 통과 선행상표가 없어 72~82 구간으로 보정했습니다.")
        elif is_coined:
            low, high = 88, 95
            explanations.append("조어상표이고 상품 유사성 필터 통과 선행상표가 0건이어서 88~95 구간으로 캘리브레이션했습니다.")
        else:
            low, high = 82, 90
            explanations.append("식별력 보통 이상이며 상품 유사성 필터 통과 선행상표가 0건이어서 82~90 구간으로 캘리브레이션했습니다.")
        calibrated = min(max(calibrated, low), high)
        return calibrated, explanations

    if same_code_high:
        calibrated = min(calibrated, 48)
        explanations.append("동일 유사군코드에서 호칭/표장 유사도가 높은 충돌 후보가 있어 50 이하 구간까지 낮췄습니다.")
    elif same_class_medium:
        calibrated = min(max(calibrated, 55), 75)
        explanations.append("동일 류 보조 검토군에서 표장 유사도가 중간 이상이라 55~75 구간의 중간 리스크로 보정했습니다.")
    elif related_only:
        lower_bound = 60 if distinctiveness["level"] == "high" else 70
        calibrated = max(calibrated, lower_bound)
        explanations.append("타 류 예외군만 존재해 원칙적으로 과도한 감점을 막고 보조 경고 수준으로 유지했습니다.")

    if filtered_count and actual_risk_count == 0:
        explanations.append("필터 통과 후보는 있으나 실제 충돌 위험도는 낮아 점수 하락을 제한했습니다.")
    elif actual_risk_count:
        explanations.append(f"상품 유사성 필터 통과 후보 {filtered_count}건 중 실제 충돌 위험 후보는 {actual_risk_count}건입니다.")

    return calibrated, explanations


def calculate_score(
    trademark_name: str,
    results: List[dict],
    is_coined: bool,
    trademark_type: str,
) -> int:
    """기존 호환용 점수 함수. 포함 후보만 주어졌다고 보고 계산한다."""
    distinctiveness = _distinctiveness_analysis(
        trademark_name=trademark_name,
        is_coined=is_coined,
        trademark_type=trademark_type,
        specific_product="",
        selected_fields=[],
    )
    candidates = []
    for item in results:
        if item.get("product_bucket") == "excluded":
            continue
        enriched = {
            **item,
            "mark_similarity": item.get("mark_similarity", item.get("similarity", 0)),
            "product_similarity_score": item.get("product_similarity_score", 62),
            "confusion_score": item.get("confusion_score", item.get("similarity", 0)),
            "product_bucket": item.get("product_bucket", "same_class"),
        }
        candidates.append(enriched)
    return _score_from_analysis(trademark_name, candidates, distinctiveness, is_coined, trademark_type)


def get_score_band(score: int) -> dict:
    if score >= 90:
        return {"label": "등록 가능성 매우 높음", "color": "#4CAF50"}
    if score >= 70:
        return {"label": "등록 가능성 높음", "color": "#2196F3"}
    if score >= 50:
        return {"label": "주의 필요", "color": "#FF9800"}
    if score >= 30:
        return {"label": "등록 어려움", "color": "#F44336"}
    return {"label": "등록 불가 가능성 높음", "color": "#B71C1C"}


def evaluate_registration(
    trademark_name: str,
    trademark_type: str,
    is_coined: bool,
    selected_classes: Iterable[int | str],
    selected_codes: Iterable[str],
    prior_items: List[dict],
    selected_fields: Iterable[dict] | None = None,
    specific_product: str = "",
) -> dict:
    selected_fields = list(selected_fields or [])
    context = _selected_context(selected_classes, selected_codes, selected_fields, specific_product)
    distinctiveness = _distinctiveness_analysis(
        trademark_name=trademark_name,
        is_coined=is_coined,
        trademark_type=trademark_type,
        specific_product=specific_product,
        selected_fields=selected_fields,
    )

    normalized_priors = _merge_prior_items(prior_items, trademark_name)

    included: list[dict] = []
    excluded: list[dict] = []
    bucket_counts = {"same_code": 0, "same_class": 0, "exception": 0, "excluded": 0}

    for item in normalized_priors:
        product = _product_similarity(item, context)
        payload = {
            **item,
            "product_bucket": product["bucket"],
            "group_name": product["group"],
            "product_similarity_label": product["label"],
            "product_similarity_score": product["score"],
            "product_penalty_weight": product["penalty_weight"],
            "product_reason": product["reason"],
            "strict_same_code": product["strict_same_code"],
        }
        bucket_counts[product["bucket"]] += 1
        if not product["include"]:
            excluded.append(payload)
            continue
        enriched = _enrich_mark_similarity(payload, trademark_name, trademark_type)
        included.append(_confusion_metrics(enriched))

    included.sort(key=lambda row: (row["confusion_score"], row["mark_similarity"], row["similarity"]), reverse=True)
    excluded.sort(key=lambda row: row["similarity"], reverse=True)

    raw_score = _score_from_analysis(trademark_name, included, distinctiveness, is_coined, trademark_type)
    score, calibration_notes = _calibrate_score(raw_score, included, distinctiveness, is_coined)
    band = get_score_band(score)
    grouped_counts = _group_counts(bucket_counts)
    actual_risk_count = sum(1 for item in included if item.get("confusion_score", 0) >= 65)
    exclusion_reason_summary = _build_exclusion_summary(excluded)

    if included:
        top = included[0]
        confusion_summary = (
            f"가장 주의할 선행상표는 '{top['trademarkName']}'이며 "
            f"{top['product_similarity_label']} + 표장 유사도 {top['mark_similarity']}%로 혼동 위험이 {top['confusion_label']}입니다."
        )
    else:
        confusion_summary = "상품 유사성 필터를 통과한 선행상표가 없어 상대적 거절사유 리스크는 낮게 평가됩니다."

    signals = [distinctiveness["summary"]]
    signals.append(
        "상품 유사성 필터 결과: "
        f"동일 코드 {bucket_counts['same_code']}건, "
        f"동일 류 {bucket_counts['same_class']}건, "
        f"예외군 {bucket_counts['exception']}건, "
        f"제외 {bucket_counts['excluded']}건"
    )
    if included:
        top = included[0]
        signals.append(
            f"표장 유사도 상위 충돌 후보는 '{top['trademarkName']}'로 "
            f"외관 {top['appearance_similarity']}%, 호칭 {top['phonetic_similarity']}%, 관념 {top['conceptual_similarity']}%입니다."
        )
    else:
        signals.append("상품 관련성이 없는 타 류 후보는 강한 감점에 반영하지 않았습니다.")
    signals.extend(calibration_notes)

    return {
        "score": score,
        "raw_score": raw_score,
        "band": band,
        "signals": signals,
        "top_prior": included[:5],
        "included_priors": included,
        "excluded_priors": excluded[:10],
        "prior_count": len(included),
        "filtered_prior_count": len(included),
        "excluded_prior_count": len(excluded),
        "actual_risk_prior_count": actual_risk_count,
        "total_prior_count": len(normalized_priors),
        "group_counts": grouped_counts,
        "grouped_priors": _grouped_priors(included[:20], excluded[:20]),
        "exclusion_reason_summary": exclusion_reason_summary,
        "distinctiveness": distinctiveness["label"],
        "distinctiveness_analysis": distinctiveness,
        "product_similarity_analysis": {
            "summary": (
                f"선행상표 {len(normalized_priors)}건 중 "
                f"동일 유사군코드 {bucket_counts['same_code']}건, "
                f"동일 류 {bucket_counts['same_class']}건, "
                f"타 류 예외군 {bucket_counts['exception']}건만 본격 검토하고 "
                f"{bucket_counts['excluded']}건은 감점에서 제외했습니다."
            ),
            "bucket_counts": bucket_counts,
            "group_counts": grouped_counts,
            "filtered_prior_count": len(included),
            "excluded_prior_count": len(excluded),
            "exclusion_reason_summary": exclusion_reason_summary,
        },
        "mark_similarity_analysis": {
            "summary": (
                f"표장 유사도는 상품 유사성 필터를 통과한 {len(included)}건에 대해서만 산출했습니다."
                if included
                else "상품 유사성 필터를 통과한 후보가 없어 외관·호칭·관념 유사도는 참고 수준으로만 보았습니다."
            ),
            "actual_risk_prior_count": actual_risk_count,
        },
        "confusion_analysis": {
            "summary": confusion_summary,
            "highest_confusion_score": included[0]["confusion_score"] if included else 0,
            "actual_risk_prior_count": actual_risk_count,
        },
        "score_explanation": {
            "summary": " / ".join(calibration_notes) if calibration_notes else "상품 유사성 필터와 식별력 축을 분리해 점수를 산정했습니다.",
            "raw_score": raw_score,
            "final_score": score,
            "notes": calibration_notes,
        },
    }
