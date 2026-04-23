from __future__ import annotations


def _case(
    case_id: str,
    category: str,
    expected_judgment: str,
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
        "expected_judgment": expected_judgment,
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
                "group_id": "final_qa",
                "group_label": "최종 QA",
                "field_id": f"final_qa_{case_id}",
                "description": specific_product or "QA",
                "example": specific_product or "",
                "class_no": f"제{selected_classes[0]}류" if selected_classes else "",
                "nice_classes": selected_classes,
                "keywords": [specific_product] if specific_product else [],
                "similarity_codes": selected_codes,
            }
        ],
        "prior_items": prior_items,
    }


def build_final_qa_cases() -> list[dict]:
    cases: list[dict] = []

    def add(c: dict) -> None:
        cases.append(c)

    def prior_exact_same_class_no_sc(
        mark: str,
        class_no: int,
        designated_text: str,
        status: str = "등록",
        app: str = "A",
    ) -> list[dict]:
        return [
            {
                "applicationNumber": f"QA-{mark}-{class_no}-{status}",
                "trademarkName": mark,
                "registerStatus": status,
                "classificationCode": str(class_no),
                "similarityGroupCode": "",
                "prior_designated_items": [
                    {"prior_item_label": designated_text, "prior_class_no": str(class_no), "prior_similarity_codes": []}
                ],
                "applicantName": app,
            }
        ]

    def prior_class35(mark: str, service_text: str, status: str = "등록", app: str = "A") -> list[dict]:
        return [
            {
                "applicationNumber": f"QA-{mark}-35-{status}",
                "trademarkName": mark,
                "registerStatus": status,
                "classificationCode": "35",
                "similarityGroupCode": "",
                "prior_designated_items": [
                    {"prior_item_label": service_text, "prior_class_no": "35", "prior_similarity_codes": []}
                ],
                "applicantName": app,
            }
        ]

    def prior_same_code_phonetic(
        mark: str,
        class_no: int,
        sc_code: str,
        designated_text: str,
        status: str = "출원",
        app: str = "B",
    ) -> list[dict]:
        return [
            {
                "applicationNumber": f"QA-{mark}-{class_no}-{sc_code}-{status}",
                "trademarkName": mark,
                "registerStatus": status,
                "classificationCode": str(class_no),
                "similarityGroupCode": sc_code,
                "prior_designated_items": [
                    {
                        "prior_item_label": designated_text,
                        "prior_class_no": str(class_no),
                        "prior_similarity_codes": [sc_code],
                    }
                ],
                "applicantName": app,
            }
        ]

    add(
        _case(
            "A1",
            "A. 완전 동일표장 + 동일류 + SC 없음",
            "강한 blocker",
            "LexAI",
            "문자만",
            True,
            "goods",
            [9],
            ["G0901"],
            "소프트웨어",
            prior_exact_same_class_no_sc("LexAI", 9, "downloadable software; digital media files"),
        )
    )
    add(
        _case(
            "A2",
            "A. 완전 동일표장 + 동일류 + SC 없음",
            "강한 blocker",
            "꽃순이",
            "문자만",
            False,
            "goods",
            [25],
            [],
            "의류",
            prior_exact_same_class_no_sc("꽃순이", 25, "의류; 신발; 모자"),
        )
    )
    add(
        _case(
            "A3",
            "A. 완전 동일표장 + 동일류 + SC 없음",
            "강한 blocker(Stage2) + Stage1/2 구분",
            "서울병원",
            "문자만",
            False,
            "services",
            [44],
            [],
            "의료서비스",
            prior_exact_same_class_no_sc("서울병원", 44, "medical clinic services"),
        )
    )

    add(
        _case(
            "B4",
            "B. 완전 동일표장 + 관련류",
            "related goods/services strong~medium-high",
            "LexAI",
            "문자만",
            True,
            "services",
            [42],
            [],
            "SaaS",
            [
                {
                    "applicationNumber": "QA-LexAI-9-등록",
                    "trademarkName": "LexAI",
                    "registerStatus": "등록",
                    "classificationCode": "9",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "downloadable software", "prior_class_no": "9", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
        )
    )
    add(
        _case(
            "B5",
            "B. 완전 동일표장 + 관련류",
            "class35 direct retail link",
            "동일상표",
            "문자만",
            True,
            "goods",
            [25],
            [],
            "의류",
            prior_class35("동일상표", "의류 소매업"),
        )
    )
    add(
        _case(
            "B6",
            "B. 완전 동일표장 + 관련류",
            "class35 strong linkage",
            "동일상표",
            "문자만",
            True,
            "goods",
            [9],
            [],
            "소프트웨어",
            prior_class35("동일상표", "컴퓨터 소프트웨어 온라인 판매업", status="등록"),
        )
    )

    add(
        _case(
            "C7",
            "C. 완전 동일표장 + 무관류",
            "광고업은 과대평가 금지(weak/none)",
            "동일상표",
            "문자만",
            True,
            "services",
            [44],
            [],
            "의료서비스",
            prior_class35("동일상표", "광고업"),
        )
    )
    add(
        _case(
            "C8",
            "C. 완전 동일표장 + 무관류",
            "자문업은 과대평가 금지(none)",
            "동일상표",
            "문자만",
            True,
            "goods",
            [1],
            [],
            "산업용 화학품",
            prior_class35("동일상표", "경영자문업"),
        )
    )

    add(
        _case(
            "D9",
            "D. 발음 유사표장",
            "high phonetic + strong warning",
            "pookie",
            "문자만",
            True,
            "goods",
            [9],
            ["G0901"],
            "소프트웨어",
            prior_same_code_phonetic("pooky", 9, "G0901", "downloadable software"),
        )
    )
    add(
        _case(
            "D10",
            "D. 발음 유사표장",
            "medium+ phonetic, pooky보다 약함",
            "pookie",
            "문자만",
            True,
            "goods",
            [9],
            ["G0901"],
            "소프트웨어",
            prior_same_code_phonetic("fooky", 9, "G0901", "downloadable software"),
        )
    )
    add(
        _case(
            "D11",
            "D. 발음 유사표장",
            "P/B weak, fooky보다 과대평가 금지",
            "pookie",
            "문자만",
            True,
            "goods",
            [9],
            ["G0901"],
            "소프트웨어",
            prior_same_code_phonetic("booky", 9, "G0901", "downloadable software"),
        )
    )
    add(
        _case(
            "D12",
            "D. 발음 유사표장",
            "R/L medium",
            "rocky",
            "문자만",
            True,
            "goods",
            [9],
            ["G0901"],
            "소프트웨어",
            prior_same_code_phonetic("locky", 9, "G0901", "downloadable software"),
        )
    )

    add(
        _case(
            "E13",
            "E. 식별력(Stage1) 검증",
            "Stage1 high/fatal 자동판정 금지",
            "유반하지",
            "문자만",
            False,
            "services",
            [44],
            [],
            "의료업",
            [],
        )
    )
    add(
        _case(
            "E14",
            "E. 식별력(Stage1) 검증",
            "Stage1 cap 금지 + Stage2에서만 검토",
            "꽃순이",
            "문자만",
            False,
            "goods",
            [25],
            [],
            "의류",
            [
                {
                    "applicationNumber": "QA-꽃순이-35-등록",
                    "trademarkName": "꽃순이",
                    "registerStatus": "등록",
                    "classificationCode": "35",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "의류 소매업", "prior_class_no": "35", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
        )
    )
    add(
        _case(
            "E15",
            "E. 식별력(Stage1) 검증",
            "지명+서비스 직접표시이면 Stage1 강한 거절 유지",
            "서울병원",
            "문자만",
            False,
            "services",
            [44],
            [],
            "의료업",
            [],
        )
    )

    return cases

