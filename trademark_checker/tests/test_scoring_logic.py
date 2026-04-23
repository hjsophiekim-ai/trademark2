import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nice_catalog import derive_selected_scope
from scoring import evaluate_registration


def run_eval(
    trademark_name: str,
    selected_class: str,
    selected_codes: list[str],
    prior_items: list[dict],
    specific_product: str = "소프트웨어",
    selected_kind: str = "goods",
    subgroup_similarity_codes: list[str] | None = None,
    subgroup_keywords: list[str] | None = None,
) -> dict:
    return evaluate_registration(
        trademark_name=trademark_name,
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[selected_class],
        selected_codes=selected_codes,
        prior_items=prior_items,
        selected_fields=[
            {
                "kind": selected_kind,
                "group_id": "test_group",
                "group_label": "테스트 대분류",
                "field_id": "test_field",
                "description": "테스트 상품군",
                "example": specific_product,
                "class_no": f"제{selected_class}류",
                "nice_classes": [int(selected_class)],
                "keywords": subgroup_keywords or [specific_product],
                "similarity_codes": subgroup_similarity_codes or selected_codes,
            }
        ],
        specific_product=specific_product,
    )


class ScoringStatusTests(unittest.TestCase):
    def test_exact_live_blocker_same_code_is_top_risk(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="9",
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "1",
                    "trademarkName": "LEXAI",
                    "registerStatus": "출원",
                    "classificationCode": "9",
                    "similarityGroupCode": "G0901",
                    "applicantName": "A",
                }
            ],
        )

        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertEqual(top["mark_similarity"], 100)
        self.assertGreaterEqual(top["confusion_score"], 95)
        self.assertTrue(top["counts_toward_final_score"])
        self.assertEqual(top["scope_bucket"], "exact_scope_candidates")
        self.assertLessEqual(result["score"], 18)

    def test_exact_live_blocker_same_class_without_sc_code_is_not_underrated(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="9",
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "1-no-sc",
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
            specific_product="소프트웨어",
        )

        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertEqual(top["mark_similarity"], 100)
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 55)
        self.assertGreaterEqual(int(top.get("confusion_score", 0)), 88)
        self.assertLessEqual(int(result.get("score", 100)), 35)

    def test_exact_live_blocker_class25_apparel_without_sc_code_uses_fallback(self) -> None:
        result = run_eval(
            trademark_name="FRESHWEAR",
            selected_class="25",
            selected_codes=[],
            prior_items=[
                {
                    "applicationNumber": "25-no-sc",
                    "trademarkName": "FRESHWEAR",
                    "registerStatus": "등록",
                    "classificationCode": "25",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "clothing", "prior_class_no": "25", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
            specific_product="의류",
            selected_kind="goods",
        )
        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 55)

    def test_exact_live_blocker_class30_food_without_sc_code_uses_fallback(self) -> None:
        result = run_eval(
            trademark_name="MORNINGTEA",
            selected_class="30",
            selected_codes=[],
            prior_items=[
                {
                    "applicationNumber": "30-no-sc",
                    "trademarkName": "MORNINGTEA",
                    "registerStatus": "등록",
                    "classificationCode": "30",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "coffee; tea", "prior_class_no": "30", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
            specific_product="커피",
            selected_kind="goods",
        )
        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 55)

    def test_exact_live_blocker_class35_retail_without_sc_code_uses_fallback(self) -> None:
        result = run_eval(
            trademark_name="GREENMART",
            selected_class="35",
            selected_codes=[],
            prior_items=[
                {
                    "applicationNumber": "35-no-sc",
                    "trademarkName": "GREENMART",
                    "registerStatus": "등록",
                    "classificationCode": "35",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "온라인쇼핑몰업", "prior_class_no": "35", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
            specific_product="판매업",
            selected_kind="services",
        )
        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 55)

    def test_exact_live_blocker_class42_saas_without_sc_code_uses_fallback(self) -> None:
        result = run_eval(
            trademark_name="CLOUDPULSE",
            selected_class="42",
            selected_codes=[],
            prior_items=[
                {
                    "applicationNumber": "42-no-sc",
                    "trademarkName": "CLOUDPULSE",
                    "registerStatus": "등록",
                    "classificationCode": "42",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "SaaS platform", "prior_class_no": "42", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
            specific_product="SaaS",
            selected_kind="services",
        )
        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 60)

    def test_exact_live_blocker_class44_medical_without_sc_code_uses_fallback(self) -> None:
        result = run_eval(
            trademark_name="WELLCLINIC",
            selected_class="44",
            selected_codes=[],
            prior_items=[
                {
                    "applicationNumber": "44-no-sc",
                    "trademarkName": "WELLCLINIC",
                    "registerStatus": "등록",
                    "classificationCode": "44",
                    "similarityGroupCode": "",
                    "prior_designated_items": [
                        {"prior_item_label": "medical clinic services", "prior_class_no": "44", "prior_similarity_codes": []}
                    ],
                    "applicantName": "A",
                }
            ],
            specific_product="의료업",
            selected_kind="services",
        )
        top = result["top_prior"][0]
        self.assertEqual(top["mark_identity"], "exact")
        self.assertTrue(top.get("exact_override", {}).get("should_override"))
        self.assertNotEqual(top.get("overlap_type"), "same_class_only")
        self.assertGreaterEqual(int(top.get("product_similarity_score", 0)), 60)

    def test_exact_mark_but_irrelevant_scope_is_not_direct_penalty(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="20",
            selected_codes=["G2001"],
            prior_items=[
                {
                    "applicationNumber": "2",
                    "trademarkName": "LEXAI",
                    "registerStatus": "등록",
                    "classificationCode": "9",
                    "similarityGroupCode": "G0901",
                    "applicantName": "B",
                }
            ],
            specific_product="가구",
        )

        self.assertEqual(result["filtered_prior_count"], 0)
        self.assertEqual(result["excluded_prior_count"], 1)
        self.assertEqual(result["excluded_priors"][0]["mark_identity"], "exact")
        self.assertGreaterEqual(result["score"], 88)

    def test_same_class_different_similarity_code_is_secondary_review(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="20",
            selected_codes=["G2001"],
            prior_items=[
                {
                    "applicationNumber": "3",
                    "trademarkName": "LEXAIA",
                    "registerStatus": "등록",
                    "classificationCode": "20",
                    "similarityGroupCode": "G2002",
                    "applicantName": "C",
                }
            ],
            specific_product="가구",
        )

        top = result["top_prior"][0]
        self.assertEqual(top["scope_bucket"], "same_class_candidates")
        self.assertTrue(top["counts_toward_final_score"])
        self.assertLessEqual(top["product_similarity_score"], 24)
        self.assertLessEqual(result["score"], 75)

    def test_default_subgroup_codes_do_not_override_user_selected_similarity_code(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="20",
            selected_codes=["G2001"],
            subgroup_similarity_codes=["G2001", "G2002"],
            prior_items=[
                {
                    "applicationNumber": "3-1",
                    "trademarkName": "LEXAIA",
                    "registerStatus": "등록",
                    "classificationCode": "20",
                    "similarityGroupCode": "G2002",
                    "applicantName": "C",
                }
            ],
            specific_product="가구",
        )

        top = result["top_prior"][0]
        self.assertEqual(top["scope_bucket"], "same_class_candidates")
        self.assertFalse(top["strict_same_code"])

    def test_software_goods_and_class_42_service_use_exception_review(self) -> None:
        result = evaluate_registration(
            trademark_name="LexAI",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=[9],
            selected_codes=["G390802"],
            prior_items=[
                {
                    "applicationNumber": "4",
                    "trademarkName": "LEXAI",
                    "registerStatus": "출원",
                    "classificationCode": "42",
                    "similarityGroupCode": "S123301",
                    "applicantName": "D",
                }
            ],
            selected_fields=[
                {
                    "kind": "goods",
                    "group_id": "electronics_it",
                    "group_label": "전자/IT",
                    "field_id": "software_apps",
                    "description": "소프트웨어/앱",
                    "example": "소프트웨어",
                    "class_no": "제9류",
                    "nice_classes": [9],
                    "keywords": ["소프트웨어", "SaaS", "플랫폼"],
                    "similarity_codes": ["G390802"],
                }
            ],
            specific_product="AI 소프트웨어",
        )

        top = result["top_prior"][0]
        self.assertEqual(top["scope_bucket"], "related_market_candidates")
        self.assertTrue(top["counts_toward_final_score"])
        self.assertGreaterEqual(top["product_similarity_score"], 50)

    def test_class_9_hardware_context_does_not_get_software_exception_boost(self) -> None:
        result = evaluate_registration(
            trademark_name="LexAI",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=[9],
            selected_codes=["G390803"],
            prior_items=[
                {
                    "applicationNumber": "4-1",
                    "trademarkName": "LEXAI",
                    "registerStatus": "출원",
                    "classificationCode": "42",
                    "similarityGroupCode": "S123301",
                    "applicantName": "D",
                }
            ],
            selected_fields=[
                {
                    "kind": "goods",
                    "group_id": "electronics_it",
                    "group_label": "전자/IT",
                    "field_id": "electronic_devices",
                    "description": "전자기기/센서",
                    "example": "전자기기",
                    "class_no": "제9류",
                    "nice_classes": [9],
                    "keywords": ["전자기기", "카메라", "센서", "컴퓨터"],
                    "similarity_codes": ["G390803"],
                }
            ],
            specific_product="카메라 센서",
        )

        top = result["top_prior"][0]
        self.assertEqual(top["scope_bucket"], "related_market_candidates")
        self.assertLess(top["product_similarity_score"], 58)

    def test_historical_only_refusal_does_not_directly_lower_final_score(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="9",
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "5",
                    "trademarkName": "LEXAI",
                    "registerStatus": "거절",
                    "classificationCode": "9",
                    "similarityGroupCode": "G0901",
                    "applicantName": "E",
                    "reasonSummary": "동일 표장이지만 거절 이력만 존재",
                }
            ],
        )

        top = result["top_prior"][0]
        self.assertFalse(top["counts_toward_final_score"])
        self.assertIn("동일 표장이나 현재 생존 장애물은 아님", top["score_reflection_label"])
        self.assertEqual(result["direct_score_prior_count"], 0)
        self.assertEqual(result["historical_reference_count"], 1)
        self.assertGreaterEqual(result["score"], 88)

    def test_flexaicam_refusal_is_reference_only_for_lexai(self) -> None:
        result = run_eval(
            trademark_name="LexAI",
            selected_class="9",
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "6",
                    "trademarkName": "FlexAiCam",
                    "registerStatus": "거절",
                    "classificationCode": "9",
                    "similarityGroupCode": "G0901",
                    "applicantName": "F",
                    "reasonSummary": "Flex는 약한 요소이고 AiCam이 핵심 요부이며 에이캠, 에이켐, ICAM과의 호칭·외관 충돌로 거절",
                    "weakElements": ["Flex"],
                    "refusalCore": "AiCam",
                    "citedMarks": ["에이캠", "에이켐", "ICAM"],
                    "refusalBasis": ["호칭", "외관"],
                    "currentMarkRelevance": "low",
                }
            ],
        )

        top = result["top_prior"][0]
        refusal = top["refusal_analysis"]
        self.assertEqual(refusal["weak_elements"], ["Flex"])
        self.assertEqual(refusal["refusal_core"], "AiCam")
        self.assertEqual(refusal["cited_marks"], ["에이캠", "에이켐", "ICAM"])
        self.assertEqual(refusal["current_mark_relevance"], "low")
        self.assertFalse(top["counts_toward_final_score"])
        self.assertIn("직접 관련 낮음", top["score_reflection_label"])


    def test_derived_similarity_codes_flow_into_review_engine(self) -> None:
        field = {
            "kind": "services",
            "group_id": "misc_services",
            "group_label": "기타 서비스",
            "field_id": "finance_scope",
            "description": "금융, 통화 및 은행업",
            "example": "금융, 통화 및 은행업",
            "class_no": "제36류",
            "nice_classes": [36],
            "keywords": ["금융", "통화", "은행"],
            "similarity_codes": ["S0201"],
        }
        scope = derive_selected_scope(
            "services",
            [field],
            specific_products={"finance_scope": "재무상담 서비스"},
            code_lookup=lambda *_args, **_kwargs: [
                {
                    "code": "S120401",
                    "selected": True,
                    "match_reason": "keyword_dictionary_match",
                    "match_confidence": "high",
                }
            ],
        )

        result = evaluate_registration(
            trademark_name="LexBank",
            trademark_type="문자상표",
            is_coined=True,
            selected_classes=scope["derived_nice_classes"],
            selected_codes=scope["derived_similarity_codes"],
            prior_items=[
                {
                    "applicationNumber": "7",
                    "trademarkName": "LEXBANK",
                    "registerStatus": "출원",
                    "classificationCode": "36",
                    "similarityGroupCode": "S120401",
                    "applicantName": "G",
                }
            ],
            selected_fields=[field],
            specific_product="재무상담 서비스",
        )

        self.assertEqual(scope["derived_nice_classes"], [36])
        self.assertEqual(scope["derived_similarity_codes"], ["S0201", "S120401"])
        self.assertEqual(result["selected_similarity_codes"], ["S0201", "S120401"])
        self.assertGreaterEqual(result["filtered_prior_count"], 1)


if __name__ == "__main__":
    unittest.main()
