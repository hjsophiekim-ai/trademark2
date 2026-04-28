import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import _analyze_dominant_mark_overlap, _assess_class36_service_proximity, evaluate_registration


OREN_GTREE_CLASS36 = {
    "applicationNumber": "4020200012399",
    "trademarkName": "오렌G트리",
    "applicantName": "주식회사오렌G트리",
    "applicationDate": "20200801",
    "registerStatus": "등록",
    "classificationCode": "36",
    "registrationNumber": "4020200099999",
    "prior_designated_items": [
        {
            "prior_item_label": "금융 또는 재무에 관한 정보제공업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201", "S120401"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
            "source_page_or_source_field": "fixture",
            "parsing_confidence": "high",
        },
        {
            "prior_item_label": "금융 또는 재무에 관한 상담업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201", "S120401"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
            "source_page_or_source_field": "fixture",
            "parsing_confidence": "high",
        },
        {
            "prior_item_label": "금융 및 투자 관련 정보제공/자문/상담 및 연구업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
            "source_page_or_source_field": "fixture",
            "parsing_confidence": "high",
        },
    ],
}


def _field(kind: str, class_no: int, description: str) -> dict:
    return {
        "kind": kind,
        "group_id": "test_group",
        "group_label": "테스트 대분류",
        "field_id": "test_field",
        "description": description,
        "example": description,
        "class_no": f"제{class_no}류",
        "nice_classes": [class_no],
        "keywords": [description],
        "similarity_codes": [],
    }


class Class36ProximityTests(unittest.TestCase):
    def test_proximity_finance_bank_is_strong(self) -> None:
        prox = _assess_class36_service_proximity(["금융업"], ["은행업"])
        self.assertEqual(prox.get("level"), "strong")
        self.assertEqual(prox.get("overlap_type"), "same_class_core_service_link")
        self.assertGreaterEqual(int(prox.get("product_similarity_floor", 0) or 0), 55)

    def test_proximity_realestate_brokerage_is_strong(self) -> None:
        prox = _assess_class36_service_proximity(["부동산업"], ["부동산중개업"])
        self.assertEqual(prox.get("level"), "strong")
        self.assertEqual(prox.get("overlap_type"), "same_class_core_service_link")
        self.assertGreaterEqual(int(prox.get("product_similarity_floor", 0) or 0), 55)

    def test_proximity_finance_legal_is_weak(self) -> None:
        prox = _assess_class36_service_proximity(["금융업"], ["법무서비스업"])
        self.assertEqual(prox.get("level"), "weak")
        self.assertEqual(prox.get("overlap_type"), "same_class_only_weak")

    def test_dominant_overlap_gtree_oren_is_strong(self) -> None:
        dom = _analyze_dominant_mark_overlap("G트리", "오렌G트리")
        self.assertTrue(dom.get("shared_dominant_term"))
        self.assertTrue(dom.get("has_prefix_or_suffix_only_difference"))
        self.assertIn(dom.get("dominant_overlap_strength"), {"strong", "medium"})
        self.assertGreaterEqual(int(dom.get("mark_similarity_floor", 0) or 0), 82)

    def test_gtree_finance_no_sc_is_not_only_weak(self) -> None:
        result = evaluate_registration(
            trademark_name="G트리",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=[36],
            selected_codes=[],
            prior_items=[OREN_GTREE_CLASS36],
            selected_fields=[_field("services", 36, "금융업")],
            specific_product="금융업",
        )
        self.assertGreaterEqual(result.get("filtered_prior_count", 0), 1)
        top = (result.get("top_prior") or [{}])[0]
        self.assertNotEqual(top.get("overlap_type"), "same_class_only_weak")
        self.assertIn(top.get("overlap_type"), {"same_class_near_services", "same_class_core_service_link"})
        self.assertGreater(int(top.get("product_similarity_score", 0) or 0), 12)
        self.assertGreater(int(top.get("confusion_score", 0) or 0), 54)
        self.assertLess(int(result.get("score", 100) or 100), 75)

    def test_gtree_realestate_no_sc_is_not_only_weak(self) -> None:
        result = evaluate_registration(
            trademark_name="G트리",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=[36],
            selected_codes=[],
            prior_items=[OREN_GTREE_CLASS36],
            selected_fields=[_field("services", 36, "부동산업")],
            specific_product="부동산업",
        )
        self.assertGreaterEqual(result.get("filtered_prior_count", 0), 1)
        top = (result.get("top_prior") or [{}])[0]
        self.assertNotEqual(top.get("overlap_type"), "same_class_only_weak")
        self.assertIn(top.get("overlap_type"), {"same_class_near_services", "same_class_core_service_link"})
        self.assertGreater(int(top.get("product_similarity_score", 0) or 0), 12)
        self.assertGreater(int(top.get("confusion_score", 0) or 0), 54)
        self.assertLess(int(result.get("score", 100) or 100), 75)


if __name__ == "__main__":
    unittest.main()

