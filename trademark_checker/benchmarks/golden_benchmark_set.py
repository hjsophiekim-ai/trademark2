from __future__ import annotations


def _case(
    case_id: str,
    category: str,
    expected: str,
    trademark_name: str,
    trademark_type: str,
    is_coined: bool,
    selected_kind: str,
    selected_classes: list[int],
    selected_codes: list[str],
    specific_product: str,
    prior_items: list[dict],
) -> dict:
    return {
        "id": case_id,
        "category": category,
        "expected": expected,
        "trademark_name": trademark_name,
        "trademark_type": trademark_type,
        "is_coined": is_coined,
        "selected_kind": selected_kind,
        "selected_classes": selected_classes,
        "selected_codes": selected_codes,
        "specific_product": specific_product,
        "selected_fields": [
            {
                "kind": selected_kind,
                "group_id": "golden",
                "group_label": "골든 벤치마크",
                "field_id": f"golden_{case_id}",
                "description": specific_product or "벤치마크",
                "example": specific_product or "",
                "class_no": f"제{selected_classes[0]}류" if selected_classes else "",
                "nice_classes": selected_classes,
                "keywords": [specific_product] if specific_product else [],
                "similarity_codes": selected_codes,
            }
        ],
        "prior_items": prior_items,
    }


CASES: list[dict] = []


def _add(case: dict) -> None:
    CASES.append(case)


def build_cases() -> list[dict]:
    if CASES:
        return CASES

    common_live = {"registerStatus": "등록", "applicantName": "A"}
    common_applied = {"registerStatus": "출원", "applicantName": "B"}

    class_keyword_examples = {
        9: ("소프트웨어", "downloadable software; digital media files"),
        25: ("의류", "clothing; footwear"),
        30: ("커피", "coffee; tea; confectionery"),
        35: ("판매업", "온라인쇼핑몰업; 소매업"),
        41: ("교육", "education; training; publishing"),
        42: ("SaaS", "SaaS platform; cloud software design"),
        44: ("의료업", "medical clinic services"),
    }

    idx = 1
    for class_no, (target_text, prior_text) in class_keyword_examples.items():
        mark = f"ALPHA{class_no}"
        _add(
            _case(
                case_id=f"EXACT_SAME_CLASS_NO_SC_{class_no}",
                category="exact same mark + same class",
                expected="should_be_strong_blocker",
                trademark_name=mark,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="services" if class_no >= 35 else "goods",
                selected_classes=[class_no],
                selected_codes=[],
                specific_product=target_text,
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": mark,
                        "classificationCode": str(class_no),
                        "similarityGroupCode": "",
                        "prior_designated_items": [
                            {"prior_item_label": prior_text, "prior_class_no": str(class_no), "prior_similarity_codes": []}
                        ],
                        **common_live,
                    }
                ],
            )
        )
        idx += 1

    _add(
        _case(
            case_id="EXACT_RELATED_LINK_9_42",
            category="exact same mark + related class",
            expected="should_be_medium_risk",
            trademark_name="LEXAI",
            trademark_type="문자만",
            is_coined=True,
            selected_kind="goods",
            selected_classes=[9],
            selected_codes=[],
            specific_product="소프트웨어",
            prior_items=[
                {
                    "applicationNumber": f"{idx}",
                    "trademarkName": "LEXAI",
                    "classificationCode": "42",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "SaaS platform", "prior_class_no": "42", "prior_similarity_codes": []}
                    ],
                    **common_live,
                }
            ],
        )
    )
    idx += 1

    _add(
        _case(
            case_id="EXACT_UNRELATED_CLASS_NO_OVERRIDE",
            category="exact same mark + unrelated class",
            expected="should_not_be_exact_override",
            trademark_name="LEXSTONE",
            trademark_type="문자만",
            is_coined=True,
            selected_kind="goods",
            selected_classes=[20],
            selected_codes=[],
            specific_product="가구",
            prior_items=[
                {
                    "applicationNumber": f"{idx}",
                    "trademarkName": "LEXSTONE",
                    "classificationCode": "9",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "downloadable software", "prior_class_no": "9", "prior_similarity_codes": []}
                    ],
                    **common_live,
                }
            ],
        )
    )
    idx += 1

    phonetic_pairs = [
        ("POOKIE", "POOKY"),
        ("POOKIE", "FOOKY"),
        ("ROCKY", "LOCKY"),
        ("KOOZIE", "COOZY"),
        ("MEETECH", "MEETTEK"),
    ]
    for a, b in phonetic_pairs:
        _add(
            _case(
                case_id=f"PHON_{a}_{b}",
                category="high phonetic similarity only",
                expected="should_be_medium_risk",
                trademark_name=a,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="goods",
                selected_classes=[9],
                selected_codes=[],
                specific_product="소프트웨어",
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": b,
                        "classificationCode": "9",
                        "similarityGroupCode": "",
                        "prior_designated_items": [],
                        **common_applied,
                    }
                ],
            )
        )
        idx += 1

    _add(
        _case(
            case_id="SAME_CLASS_ONLY_WEAK_GOODS",
            category="same class only but weak goods overlap",
            expected="should_remain_same_class_only",
            trademark_name="LEXBANK",
            trademark_type="문자만",
            is_coined=True,
            selected_kind="services",
            selected_classes=[36],
            selected_codes=[],
            specific_product="재무상담",
            prior_items=[
                {
                    "applicationNumber": f"{idx}",
                    "trademarkName": "LEXBANKING",
                    "classificationCode": "36",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "보험업", "prior_class_no": "36", "prior_similarity_codes": []}
                    ],
                    **common_live,
                }
            ],
        )
    )
    idx += 1

    for i in range(10):
        class_no = 9 if i % 2 == 0 else 25
        mark = f"OMEGA{i}"
        prior = f"OMEGA{i}X"
        _add(
            _case(
                case_id=f"SC_MISSING_{i}",
                category="SC code missing cases",
                expected="should_remain_same_class_only",
                trademark_name=mark,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="goods",
                selected_classes=[class_no],
                selected_codes=[],
                specific_product=class_keyword_examples[class_no][0],
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": prior,
                        "classificationCode": str(class_no),
                        "similarityGroupCode": "",
                        "prior_designated_items": [],
                        **common_applied,
                    }
                ],
            )
        )
        idx += 1

    related_pairs = [
        (9, 35, "소프트웨어", "컴퓨터 소프트웨어 온라인 판매업"),
        (25, 35, "의류", "의류 소매업"),
        (30, 43, "커피", "카페업"),
        (31, 44, "식품", "건강관리 서비스"),
        (9, 42, "소프트웨어", "SaaS platform"),
        (20, 35, "가구", "가구 판매업"),
        (18, 35, "가방", "가방 소매업"),
        (31, 35, "식품", "식품 판매업"),
        (5, 44, "건강", "medical clinic services"),
        (16, 41, "출판", "publishing"),
    ]
    for a, b, target_text, prior_text in related_pairs:
        mark = f"REL{a}_{b}"
        _add(
            _case(
                case_id=f"EXACT_RELATED_{a}_{b}",
                category="exact same mark + related class",
                expected="should_be_medium_risk",
                trademark_name=mark,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="services" if a >= 35 else "goods",
                selected_classes=[a],
                selected_codes=[],
                specific_product=target_text,
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": mark,
                        "classificationCode": str(b),
                        "similarityGroupCode": "",
                        "prior_designated_items": [
                            {"prior_item_label": prior_text, "prior_class_no": str(b), "prior_similarity_codes": []}
                        ],
                        **common_live,
                    }
                ],
            )
        )
        idx += 1

    unrelated_pairs = [
        (9, 20, "소프트웨어", "가구"),
        (25, 1, "의류", "산업용 화학품"),
        (30, 9, "커피", "downloadable software"),
        (44, 30, "의료업", "coffee"),
        (41, 1, "교육", "산업용 화학품"),
        (42, 25, "SaaS", "clothing"),
        (35, 1, "판매업", "산업용 화학품"),
        (20, 44, "가구", "medical clinic services"),
        (18, 30, "가방", "tea"),
        (31, 9, "식품", "digital media files"),
    ]
    for a, b, target_text, prior_text in unrelated_pairs:
        mark = f"UNREL{a}_{b}"
        _add(
            _case(
                case_id=f"EXACT_UNRELATED_{a}_{b}",
                category="exact same mark + unrelated class",
                expected="should_not_be_exact_override",
                trademark_name=mark,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="services" if a >= 35 else "goods",
                selected_classes=[a],
                selected_codes=[],
                specific_product=target_text,
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": mark,
                        "classificationCode": str(b),
                        "similarityGroupCode": "",
                        "prior_designated_items": [
                            {"prior_item_label": prior_text, "prior_class_no": str(b), "prior_similarity_codes": []}
                        ],
                        **common_live,
                    }
                ],
            )
        )
        idx += 1

    extra_phonetic = [
        ("NEUROAI", "NEUROAY"),
        ("DATAMART", "DATAMARTT"),
        ("CARELINE", "KERELINE"),
        ("CLOUDTEK", "CLOUDTECH"),
        ("MEDITEC", "MEDITEK"),
        ("EDULINE", "EDYLINE"),
        ("APPCARE", "APPCAREE"),
        ("KOFFEE", "COFFEE"),
        ("TEALINE", "TLINE"),
        ("FOOTWEAR", "FOOTWARE"),
    ]
    for a, b in extra_phonetic:
        _add(
            _case(
                case_id=f"PHON2_{a}_{b}",
                category="high phonetic similarity only",
                expected="should_be_medium_risk",
                trademark_name=a,
                trademark_type="문자만",
                is_coined=True,
                selected_kind="goods",
                selected_classes=[9],
                selected_codes=[],
                specific_product="소프트웨어",
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": b,
                        "classificationCode": "9",
                        "similarityGroupCode": "",
                        "prior_designated_items": [],
                        **common_applied,
                    }
                ],
            )
        )
        idx += 1

    for i in range(15):
        _add(
            _case(
                case_id=f"SAME_CLASS_WEAK_{i}",
                category="same class only but weak goods overlap",
                expected="should_remain_same_class_only",
                trademark_name=f"WEAK{i}BANK",
                trademark_type="문자만",
                is_coined=True,
                selected_kind="services",
                selected_classes=[36],
                selected_codes=[],
                specific_product="재무상담",
                prior_items=[
                    {
                        "applicationNumber": f"{idx}",
                        "trademarkName": f"WEAK{i}BANKING",
                        "classificationCode": "36",
                        "similarityGroupCode": "",
                        "prior_designated_items": [
                            {"prior_item_label": "보험업", "prior_class_no": "36", "prior_similarity_codes": []}
                        ],
                        **common_applied,
                    }
                ],
            )
        )
        idx += 1

    return CASES

