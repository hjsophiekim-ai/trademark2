"""상품/서비스업 범위 예외와 절대적 거절사유 보조 엔진."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable


GOODS_CLASS_RANGE = set(range(1, 35))
SERVICES_CLASS_RANGE = set(range(35, 46))

SOFTWARE_PRIMARY_CODES = {"G390802"}
SOFTWARE_SECONDARY_CODES: set[str] = set()
SOFTWARE_SERVICE_CLASSES = {35, 38, 42}
SOFTWARE_KEYWORDS = {
    "software",
    "saas",
    "app",
    "platform",
    "program",
    "cloud",
    "ai",
    "소프트웨어",
    "애플리케이션",
    "프로그램",
    "플랫폼",
    "클라우드",
}

ECONOMIC_LINKS = {
    frozenset({3, 35}),
    frozenset({5, 35}),
    frozenset({5, 44}),
    frozenset({9, 42}),
    frozenset({10, 44}),
    frozenset({14, 35}),
    frozenset({16, 41}),
    frozenset({18, 35}),
    frozenset({20, 35}),
    frozenset({25, 35}),
    frozenset({30, 43}),
    frozenset({31, 35}),
    frozenset({31, 44}),
    frozenset({39, 43}),
}

SCOPE_GROUP_LABELS = {
    "exact_scope_candidates": "실질 충돌 후보",
    "same_class_candidates": "동일 니스류 보조 검토",
    "related_market_candidates": "상품-서비스업 예외 검토",
    "irrelevant_candidates": "제외 후보",
}

RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "fatal": 4}
PUBLIC_MARK_KEYWORDS = {
    "대한민국",
    "국가대표",
    "특허청",
    "국세청",
    "서울특별시",
    "서울시",
    "부산광역시",
    "대한적십자사",
    "koreagov",
    "governmentofkorea",
    "un",
    "unesco",
    "who",
}
IMPROPER_TERMS = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
}
FAMOUS_MARKS = {
    "google",
    "apple",
    "samsung",
    "naver",
    "kakao",
    "nike",
    "tesla",
    "starbucks",
}
NON_DISTINCTIVE_WORDS = {
    "love", "good", "best", "smile", "happy", "great", "cool", "hot", "top",
    "pro", "plus", "ultra", "super", "smart", "fresh", "clean", "fast", "pretty",
    "big", "small", "new", "old", "red", "blue", "green", "black", "white",
    "사랑", "행복", "최고", "좋은", "미소", "감사", "전문", "예쁜",
    "고양이", "강아지", "사과", "포도", "바나나", "나무", "꽃", "하늘",
    "바다", "산", "물", "불",
    "신선", "달콤", "깔끔", "빠른", "느린", "큰", "작은", "예쁜",
    "행복한", "슬픈", "화난", "졸린",
    "테크", "온라인", "디지털", "오리지널", "베스트",
    "브랜드", "몰", "스토어", "샵", "트리", "랩",
    "패션", "뷰티", "헬스",
}
DESCRIPTIVE_PATTERNS = {
    "cool": {3, 5, 32}, # 화장품, 약제, 음료 등에서 '시원한'
    "sweet": {30, 32},  # 과자, 음료 등에서 '달콤한'
    "fresh": {29, 30, 31, 32, 43}, # 신선한
    "clean": {3, 37}, # 세정, 청소
    "fast": {39, 43}, # 배달, 음식
    "pretty": {3},   # 화장품, 향수 등에서 '예쁜'
    "시원": {3, 5, 32},
    "달콤": {30, 32},
    "신선": {29, 30, 31, 32, 43},
    "깔끔": {3, 37},
    "빠른": {39, 43},
    "예쁜": {3},
}
COMMON_SURNAMES = {
    "kim",
    "lee",
    "park",
    "choi",
    "jung",
    "kang",
    "김",
    "이",
    "박",
    "최",
    "정",
    "강",
}
WEAK_GEO_SUFFIXES = {
    "",
    "city",
    "mall",
    "line",
    "service",
    "services",
    "store",
    "shop",
    "tree",
    "lab",
    "group",
    "k",
    "s",
    "lo",
    "si",
    "시",
    "몰",
    "라인",
    "서비스",
    "트리",
    "샵",
    "스토어",
    "랩",
}
GEOGRAPHIC_NAMES = {
    # 국가명 (상표법 제33조 제1항 제4호 - 현저한 지명)
    "대한민국": {"대한민국", "korea", "Republic of Korea", "Korea"},
    "미국": {"미국", "usa", "america", "United States", "US"},
    "영국": {"영국", "uk", "britain", "United Kingdom", "Britain"},
    "독일": {"독일", "germany", "Deutschland"},
    "프랑스": {"프랑스", "france"},
    "일본": {"일본", "japan", "Japan"},
    "중국": {"중국", "china", "China"},
    "러시아": {"러시아", "russia", "Russia"},
    "캐나다": {"캐나다", "canada", "Canada"},
    "호주": {"호주", "australia", "Australia"},
    "인도": {"인도", "india", "India"},
    "브라질": {"브라질", "brazil", "Brazil"},
    "멕시코": {"멕시코", "mexico", "Mexico"},
    "스페인": {"스페인", "spain", "Spain"},
    "이탈리아": {"이탈리아", "italy", "Italy"},
    "스위스": {"스위스", "swiss", "Switzerland"},
    "네덜란드": {"네덜란드", "netherlands", "Holland"},
    "홍콩": {"홍콩", "hongkong", "hong kong", "Hong Kong"},
    "싱가포르": {"싱가포르", "singapore", "Singapore"},
    "대만": {"대만", "taiwan", "Taiwan"},
    # 주요 도시명
    "서울": {"서울", "서울시", "seoul", "Seoul"},
    "부산": {"부산", "busan", "Busan"},
    "인천": {"인천", "incheon", "Incheon"},
    "대구": {"대구", "daegu", "Daegu"},
    "대전": {"대전", "daejeon", "Daejeon"},
    "광주": {"광주", "gwangju", "Gwangju"},
    "울산": {"울산", "ulsan", "Ulsan"},
    "세종": {"세종", "sejong", "Sejong"},
    "제주": {"제주", "jeju", "Jeju"},
    "수원": {"수원", "suwon", "Suwon"},
    "창원": {"창원", "changwon", "Changwon"},
    "도쿄": {"도쿄", "tokyo", "Tokyo"},
    "오사카": {"오사카", "osaka", "Osaka"},
    "파리": {"파리", "paris", "Paris"},
    "런던": {"런던", "london", "London"},
    "뉴욕": {"뉴욕", "newyork", "new york", "New York"},
    " LA": {"LA", "losangeles", "los angeles", "Los Angeles"},
    "시드니": {"시드니", "sydney", "Sydney"},
    "베를린": {"베를린", "berlin", "Berlin"},
    "밀라노": {"밀라노", "milan", "Milan"},
}
DESCRIPTIVE_HINTS = {
    "finance",
    "financial",
    "bank",
    "insurance",
    "realestate",
    "legal",
    "law",
    "mall",
    "service",
    "shop",
    "store",
    "금융",
    "은행",
    "보험",
    "부동산",
    "법무",
    "법률",
    "몰",
    "서비스",
}
QUALITY_CLAIMS = {
    "organic": {29, 30, 31, 32},
    "bank": {36},
    "insurance": {36},
    "hospital": {44},
    "university": {41},
    "유기농": {29, 30, 31, 32},
    "은행": {36},
    "보험": {36},
    "병원": {44},
    "대학교": {41},
}


def infer_kind_from_classes(classes: Iterable[int | str]) -> str | None:
    normalized = []
    for value in classes:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    if not normalized:
        return None
    if all(value in GOODS_CLASS_RANGE for value in normalized):
        return "goods"
    if all(value in SERVICES_CLASS_RANGE for value in normalized):
        return "services"
    return None


def build_scope_counts(bucket_counts: dict[str, int]) -> dict[str, int]:
    return {
        "exact_scope_candidates": bucket_counts.get("same_code", 0),
        "same_class_candidates": bucket_counts.get("same_class", 0),
        "related_market_candidates": bucket_counts.get("exception", 0),
        "irrelevant_candidates": bucket_counts.get("excluded", 0),
    }


def has_economic_link(selected_classes: Iterable[int], item_classes: Iterable[int]) -> bool:
    for selected in selected_classes:
        for item_class in item_classes:
            if frozenset({int(selected), int(item_class)}) in ECONOMIC_LINKS:
                return True
    return False


def _normalize_codes(values: Iterable[str]) -> set[str]:
    return {
        str(code or "").strip().upper()
        for code in values
        if str(code or "").strip()
    }


def _normalize_keywords(values: Iterable[str]) -> set[str]:
    normalized = set()
    for value in values:
        text = str(value or "").strip().lower()
        if text:
            normalized.add(text)
    return normalized


def _has_software_keyword(keywords: set[str]) -> bool:
    return any(any(token in keyword for token in SOFTWARE_KEYWORDS) for keyword in keywords)


def _has_software_goods_signal(
    codes: set[str],
    keywords: set[str],
    *,
    require_keyword_for_secondary: bool,
) -> bool:
    if codes & SOFTWARE_PRIMARY_CODES:
        return True

    keyword_match = _has_software_keyword(keywords)
    if keyword_match and (codes & SOFTWARE_SECONDARY_CODES):
        return True
    if keyword_match and not codes:
        return True
    if not require_keyword_for_secondary and codes & SOFTWARE_SECONDARY_CODES:
        return True
    return False


def software_service_exception(
    selected_kind: str | None,
    item_kind: str | None,
    selected_classes: Iterable[int],
    item_classes: Iterable[int],
    selected_codes: Iterable[str],
    item_code: str,
    selected_keywords: Iterable[str],
    similarity_hint: int,
    mark_identity: str,
) -> dict:
    selected_classes = {int(value) for value in selected_classes}
    item_classes = {int(value) for value in item_classes}
    selected_codes = _normalize_codes(selected_codes)
    item_code = str(item_code or "").strip().upper()
    selected_keywords = _normalize_keywords(selected_keywords)

    if {selected_kind, item_kind} != {"goods", "services"}:
        return {"applies": False}

    selected_has_software = _has_software_goods_signal(
        selected_codes,
        selected_keywords,
        require_keyword_for_secondary=True,
    )
    item_has_software = _has_software_goods_signal(
        {item_code} if item_code else set(),
        set(),
        require_keyword_for_secondary=False,
    )
    service_has_software = bool(selected_classes & SOFTWARE_SERVICE_CLASSES) or bool(item_classes & SOFTWARE_SERVICE_CLASSES)

    if not service_has_software:
        return {"applies": False}
    if not (selected_has_software or item_has_software):
        return {"applies": False}
    if mark_identity != "exact" and similarity_hint < 85:
        return {"applies": False}

    return {
        "applies": True,
        "score": 58,
        "penalty_weight": 0.52,
        "reason": (
            "소프트웨어와 35·38·42류 서비스의 예외 결합은 제한적으로만 인정합니다. "
            "이번 후보는 소프트웨어 신호와 서비스류가 함께 확인되어 보조 예외 검토군으로 포함했습니다."
        ),
    }


def cross_kind_exception(
    selected_kind: str | None,
    item_kind: str | None,
    selected_classes: Iterable[int],
    item_classes: Iterable[int],
    selected_codes: Iterable[str],
    item_code: str,
    selected_keywords: Iterable[str],
    similarity_hint: int,
    mark_identity: str,
) -> dict:
    software_exception = software_service_exception(
        selected_kind=selected_kind,
        item_kind=item_kind,
        selected_classes=selected_classes,
        item_classes=item_classes,
        selected_codes=selected_codes,
        item_code=item_code,
        selected_keywords=selected_keywords,
        similarity_hint=similarity_hint,
        mark_identity=mark_identity,
    )
    if software_exception.get("applies"):
        return software_exception

    if selected_kind and item_kind and selected_kind != item_kind:
        if mark_identity != "exact" and similarity_hint < 88:
            return {"applies": False}
        if has_economic_link(selected_classes, item_classes):
            return {
                "applies": True,
                "score": 32,
                "penalty_weight": 0.24,
                "reason": (
                    "상품과 서비스업이 직접 동일 범위는 아니지만 거래 현실상 경제적 견련성이 있어 "
                    "보조 예외 검토군으로만 포함했습니다."
                ),
            }
        return {"applies": False}

    if has_economic_link(selected_classes, item_classes):
        return {
            "applies": True,
            "score": 28,
            "penalty_weight": 0.22,
            "reason": "다른 류이지만 거래상 관련성이 있어 보조 경고 수준으로만 반영했습니다.",
        }

    return {"applies": False}


def _normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _compact(value: object) -> str:
    text = _normalize_text(value)
    text = text.replace("-", "").replace("_", "").replace(" ", "")
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def _collapse_repeats(value: str) -> str:
    return re.sub(r"(.)\1+", r"\1", value)


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, lch in enumerate(left, start=1):
        curr = [i]
        for j, rch in enumerate(right, start=1):
            cost = 0 if lch == rch else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _normalize_geo_variant(value: object) -> str:
    text = _compact(value)
    text = _collapse_repeats(text)
    replacements = {
        "seoulcity": "seoulcity",
        "seo ul": "seoul",
        "seouls": "seouls",
    }
    return replacements.get(text, text)


def _iter_text_parts(trademark_name: str) -> list[str]:
    raw = _normalize_text(trademark_name)
    parts = re.split(r"[^0-9a-z가-힣]+", raw)
    parts = [part for part in parts if part]
    compact = _compact(trademark_name)
    if compact and compact not in parts:
        parts.append(compact)
    return parts


def _context_tokens(specific_product: str, selected_fields: Iterable[dict]) -> set[str]:
    tokens: set[str] = set()
    for value in [specific_product, *[field.get("description", "") for field in selected_fields]]:
        for token in re.findall(r"[0-9a-z가-힣]+", _normalize_text(value)):
            if len(token) >= 2:
                tokens.add(token)
                tokens.add(_compact(token))
    return tokens


def _geo_match_payload(trademark_name: str) -> dict | None:
    compact_mark = _normalize_geo_variant(trademark_name)
    if not compact_mark:
        return None

    for canonical, variants in GEOGRAPHIC_NAMES.items():
        normalized_variants = {_normalize_geo_variant(variant) for variant in variants}
        for variant in normalized_variants:
            if not variant:
                continue
            # 국가명 또는 주요 도시명의 직접 일치 → fatal (상표법 제33조 제1항 제4호)
            if compact_mark == variant:
                is_country_name = canonical in {
                    "대한민국", "미국", "영국", "독일", "프랑스", "일본", "중국",
                    "러시아", "캐나다", "호주", "인도", "브라질", "멕시코", "스페인",
                    "이탈리아", "스위스", "네덜란드", "홍콩", "싱가포르", "대만"
                }
                cap = 5 if is_country_name else 10
                return {
                    "basis": "제33-1-4",
                    "level": "fatal",
                    "cap": cap,
                    "reason": f"'{trademark_name}'는 현저한 지명 '{canonical}' 자체와 동일하거나 가깝습니다. 상표법 제33조 제1항 제4호에 따라 등록이 거절될 가능성이 매우 높습니다.",
                }
            if compact_mark.startswith(variant):
                remainder = compact_mark[len(variant):]
                if remainder in WEAK_GEO_SUFFIXES or len(remainder) <= 2:
                    return {
                        "basis": "제33-1-4",
                        "level": "high",
                        "cap": 22,
                        "reason": (
                            f"'{trademark_name}'는 현저한 지명 '{canonical}'에 약한 부가요소만 붙은 형태로 보여 "
                            "지명 표장 위험이 높아 등록 가능성이 낮습니다."
                        ),
                    }
            if _edit_distance(compact_mark, variant) <= 1 or SequenceMatcher(None, compact_mark, variant).ratio() >= 0.9:
                return {
                    "basis": "제33-1-4",
                    "level": "high",
                    "cap": 18,
                    "reason": (
                        f"'{trademark_name}'는 현저한 지명 '{canonical}'의 근접 철자변형으로 보일 수 있어 "
                        "지명 표장 위험이 높아 등록 가능성이 낮습니다."
                    ),
                }
    return None


def _append_finding(findings: list[dict], finding: dict | None) -> None:
    if not finding:
        return
    findings.append(finding)


def _highest_risk(findings: list[dict]) -> str:
    level = "none"
    for finding in findings:
        if RISK_ORDER[finding["level"]] > RISK_ORDER[level]:
            level = finding["level"]
    return level


def _quality_mismatch_findings(trademark_name: str, selected_classes: Iterable[int]) -> list[dict]:
    compact_mark = _compact(trademark_name)
    class_set = {int(value) for value in selected_classes if str(value).strip()}
    findings: list[dict] = []
    for claim, allowed_classes in QUALITY_CLAIMS.items():
        if claim not in compact_mark:
            continue
        if class_set & allowed_classes:
            continue
        findings.append(
            {
                "basis": "제34-1-12",
                "level": "medium",
                "cap": 58,
                "reason": f"'{claim}' 표현은 지정상품/서비스와 맞지 않아 품질오인 또는 기만 우려가 있습니다.",
            }
        )
    return findings


def _famous_mark_findings(trademark_name: str) -> list[dict]:
    compact_mark = _normalize_geo_variant(trademark_name)
    findings: list[dict] = []
    for mark in FAMOUS_MARKS:
        if not compact_mark:
            continue
        if compact_mark == mark or _edit_distance(compact_mark, mark) <= 1 or SequenceMatcher(None, compact_mark, mark).ratio() >= 0.9:
            findings.append(
                {
                    "basis": "제34-1-11",
                    "level": "high",
                    "cap": 32,
                    "reason": f"저명한 타인 표장 '{mark}'과의 혼동 우려가 있습니다.",
                }
            )
            findings.append(
                {
                    "basis": "제34-1-13",
                    "level": "medium",
                    "cap": 38,
                    "reason": "저명 표장에 대한 편승 또는 부정한 목적 추정 가능성을 보조 경고로 반영했습니다.",
                }
            )
            break
    return findings


def assess_distinctiveness_strength(
    trademark_name: str,
    selected_fields: Iterable[dict] | None,
    selected_classes: Iterable[int | str] | None,
    specific_product: str,
    has_live_exact_mark_any_class: bool = False,
) -> str:
    selected_fields = list(selected_fields or [])
    selected_classes = [int(value) for value in (selected_classes or []) if str(value).strip()]
    context = _context_tokens(specific_product, selected_fields)
    compact_mark = _compact(trademark_name)

    if not compact_mark:
        return "inherently_distinctive"

    if has_live_exact_mark_any_class:
        return "inherently_distinctive"

    geo_finding = _geo_match_payload(trademark_name)
    if geo_finding and geo_finding.get("basis") == "제33-1-4":
        return "non_distinctive_geographic"

    for claim, classes in QUALITY_CLAIMS.items():
        if _compact(claim) and _compact(claim) in compact_mark:
            if any(cls in classes for cls in selected_classes):
                return "non_distinctive_descriptive"

    if compact_mark in COMMON_SURNAMES:
        return "weak_but_registrable"

    if len(compact_mark) <= 2 and re.fullmatch(r"[가-힣]{1,2}", compact_mark or ""):
        return "weak_but_registrable"

    if compact_mark in context:
        return "non_distinctive_generic"

    if compact_mark in NON_DISTINCTIVE_WORDS:
        return "weak_but_registrable"

    return "inherently_distinctive"


def evaluate_absolute_refusal(
    trademark_name: str,
    trademark_type: str,
    is_coined: bool,
    specific_product: str,
    selected_fields: Iterable[dict] | None = None,
    selected_classes: Iterable[int | str] | None = None,
    selected_codes: Iterable[str] | None = None,
    has_live_exact_mark_any_class: bool = False,
) -> dict:
    """제33조/제34조 기반 절대적 거절사유 및 식별력 리스크를 평가한다."""

    del trademark_type
    del selected_codes

    selected_fields = list(selected_fields or [])
    selected_classes = [int(value) for value in (selected_classes or []) if str(value).strip()]
    compact_mark = _compact(trademark_name)
    mark_parts = _iter_text_parts(trademark_name)
    context = _context_tokens(specific_product, selected_fields)
    findings: list[dict] = []
    public_keywords_normalized = {_compact(keyword) for keyword in PUBLIC_MARK_KEYWORDS}

    geo_finding = _geo_match_payload(trademark_name)
    _append_finding(findings, geo_finding)

    if compact_mark in public_keywords_normalized or any(
        _compact(part) in public_keywords_normalized for part in mark_parts
    ):
        findings.append(
            {
                "basis": "제34-1-1",
                "level": "fatal",
                "cap": 5,
                "reason": "국가·공공기관·국제기구 관련 표장과 충돌할 수 있는 표현이 포함되어 있습니다.",
            }
        )

    distinctiveness_strength = assess_distinctiveness_strength(
        trademark_name=trademark_name,
        selected_fields=selected_fields,
        selected_classes=selected_classes,
        specific_product=specific_product,
        has_live_exact_mark_any_class=has_live_exact_mark_any_class,
    )

    for claim, classes in QUALITY_CLAIMS.items():
        claim_compact = _compact(claim)
        if not claim_compact:
            continue
        if claim_compact in compact_mark and any(cls in classes for cls in selected_classes):
            findings.append(
                {
                    "basis": "제33-1-3",
                    "level": "fatal",
                    "cap": 8,
                    "reason": f"'{claim}' 표현은 지정상품/서비스의 성질·용도·업종을 직접 표시합니다.",
                }
            )
            break

    if distinctiveness_strength == "non_distinctive_generic" and not any(
        finding["basis"] in {"제33-1-1", "제33-1-3"} for finding in findings
    ):
        findings.append(
            {
                "basis": "제33-1-1",
                "level": "fatal",
                "cap": 12,
                "reason": "표장이 지정상품/서비스의 보통명칭 또는 핵심 명칭 자체와 가깝습니다.",
            }
        )

    if distinctiveness_strength == "non_distinctive_descriptive" and not any(
        finding["basis"] == "제33-1-3" for finding in findings
    ):
        findings.append(
            {
                "basis": "제33-1-3",
                "level": "high",
                "cap": 48,
                "reason": "표장이 지정상품/서비스의 성질·용도·품질 등을 직접 표시하는 표현에 가깝습니다.",
            }
        )

    # 기술적 표장 (제33조 제1항 제3호 - 성질표시 표장)
    # "pretty skin"에서 "pretty"를 감지하려면 공백 제거 후 combined_mark에서 체크하는 기존 방식과
    #并存하여, 각 어절 단위(공백-split)에서도 패턴 체크
    if not is_coined:
        for pattern, classes in DESCRIPTIVE_PATTERNS.items():
            if pattern in compact_mark:
                if any(cls in classes for cls in selected_classes):
                    findings.append(
                        {
                            "basis": "제33-1-3",
                            "level": "fatal",
                            "cap": 8,
                            "reason": f"'{trademark_name}'는 지정상품의 품질, 원재료, 효능 또는 성질을 직접적으로 나타내는 기술적 표장(성질표시)에 해당합니다. 상표법 제33조 제1항 제3호에 의해 등록이 거절될 가능성이 매우 높습니다.",
                        }
                    )
                    break
            # combined mark에서 안 잡히면 어절 단위로도 체크 (예: "pretty skin"에서 "pretty")
            # NOTE: 어절 단위에서는 has_alphanum exemption을 적용하지 않음
            # 왜냐하면 "pretty" 단독으로는 이미 NON_DISTINCTIVE_WORDS에 걸러지기 때문
            parts = _iter_text_parts(trademark_name)
            for part in parts:
                part_compact = _compact(part)
                if pattern in part_compact:
                    if any(cls in classes for cls in selected_classes):
                        findings.append(
                            {
                                "basis": "제33-1-3",
                                "level": "fatal",
                                "cap": 8,
                                "reason": f"'{trademark_name}'의 구성 요소 '{part}'는 지정상품의 품질, 원재료, 효능 또는 성질을 직접적으로 나타내는 기술적 표장(성질표시)에 해당합니다.",
                            }
                        )
                        break

    if any(term in compact_mark for term in IMPROPER_TERMS):
        findings.append(
            {
                "basis": "제34-1-4",
                "level": "high",
                "cap": 18,
                "reason": "공서양속 저해 우려가 있는 표현이 포함되어 있습니다.",
            }
        )

    if compact_mark in COMMON_SURNAMES:
        findings.append(
            {
                "basis": "제33-1-5",
                "level": "medium",
                "cap": 55,
                "reason": "흔히 있는 성 또는 명칭만으로는 식별력이 약합니다.",
            }
        )

    if len(compact_mark) <= 2 or re.fullmatch(r"[a-z0-9]{1,2}", compact_mark or ""):
        findings.append(
            {
                "basis": "제33-1-6",
                "level": "high" if len(compact_mark) <= 1 else "medium",
                "cap": 40,
                "reason": "문자 수가 매우 짧거나 간단해 간단하고 흔한 표장 위험이 있습니다.",
            }
        )

    if compact_mark and compact_mark in context:
        findings.append(
            {
                "basis": "제33-1-1",
                "level": "fatal",
                "cap": 12,
                "reason": "표장이 지정상품/서비스의 보통명칭 또는 핵심 명칭 자체와 가깝습니다.",
            }
        )
    elif not is_coined and compact_mark and any(token in compact_mark for token in DESCRIPTIVE_HINTS if token in context):
        findings.append(
            {
                "basis": "제33-1-3",
                "level": "high",
                "cap": 48,
                "reason": "표장이 지정상품/서비스의 성질·용도·업종을 직접 설명하는 표현과 밀접합니다.",
            }
        )

    if not is_coined and compact_mark in {"brand", "mall", "service", "store", "tree", "브랜드", "몰", "서비스"}:
        findings.append(
            {
                "basis": "제33-1-2",
                "level": "medium",
                "cap": 58,
                "reason": "관용적이거나 거래계에서 흔히 쓰이는 표현에 가까워 보입니다.",
            }
        )

    findings.extend(_quality_mismatch_findings(trademark_name, selected_classes))
    findings.extend(_famous_mark_findings(trademark_name))

    level = _highest_risk(findings)
    cap = min((finding["cap"] for finding in findings), default=95)

    distinctiveness_score = 86
    for finding in findings:
        if finding["level"] == "fatal":
            distinctiveness_score -= 35
        elif finding["level"] == "high":
            distinctiveness_score -= 24
        elif finding["level"] == "medium":
            distinctiveness_score -= 14
        elif finding["level"] == "low":
            distinctiveness_score -= 6
    distinctiveness_score = max(0, min(100, distinctiveness_score))

    bases = []
    for finding in findings:
        if finding["basis"] not in bases:
            bases.append(finding["basis"])

    acquired_needed = any(
        basis in {"제33-1-3", "제33-1-4", "제33-1-5", "제33-1-6", "제33-1-7"}
        for basis in bases
    )

    if level in {"fatal", "high"}:
        label = "거절 가능성 큼"
    elif level == "medium":
        label = "식별력 약함"
    else:
        label = "식별력 문제 없음"

    reasons = [finding["reason"] for finding in findings]
    # 가장 낮은 cap을 가진 사유를 우선적으로 summary로 채택
    if findings:
        best_finding = min(findings, key=lambda x: x["cap"])
        summary = best_finding["reason"]
    else:
        summary = "절대적 거절사유 관점에서 두드러진 식별력 장애는 크지 않습니다."

    return {
        "label": label,
        "level": level,
        "summary": summary,
        "reasons": reasons,
        "findings": findings,
        "score_adjustment": distinctiveness_score - 80,
        "distinctiveness_score": distinctiveness_score,
        "absolute_risk_level": level,
        "absolute_refusal_bases": bases,
        "absolute_probability_cap": cap,
        "acquired_distinctiveness_needed": acquired_needed,
    }
