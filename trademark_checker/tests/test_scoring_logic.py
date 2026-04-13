import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import evaluate_registration


class ScoringCalibrationTests(unittest.TestCase):
    def test_lexai_furniture_with_no_filtered_priors_scores_high(self) -> None:
        result = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["20류"],
            selected_codes=["G2001", "S2021"],
            prior_items=[
                {
                    "applicationNumber": "1",
                    "trademarkName": "LEXAI",
                    "registerStatus": "등록",
                    "classificationCode": "9",
                    "applicantName": "A",
                },
                {
                    "applicationNumber": "2",
                    "trademarkName": "LEXI",
                    "registerStatus": "출원",
                    "classificationCode": "25",
                    "applicantName": "B",
                },
            ],
            selected_fields=[{"class_no": "20류", "description": "가구/인테리어", "example": "책상, 소파"}],
            specific_product="가구",
        )

        self.assertEqual(result["filtered_prior_count"], 0)
        self.assertGreaterEqual(result["score"], 82)

    def test_lexai_software_scores_lower_than_furniture_case(self) -> None:
        furniture = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["20류"],
            selected_codes=["G2001"],
            prior_items=[],
            selected_fields=[{"class_no": "20류", "description": "가구/인테리어", "example": "책상"}],
            specific_product="가구",
        )
        software = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["9류"],
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "3",
                    "trademarkName": "LEXAI",
                    "registerStatus": "등록",
                    "classificationCode": "9",
                    "applicantName": "C",
                }
            ],
            selected_fields=[{"class_no": "9류", "description": "전자기기/소프트웨어", "example": "앱"}],
            specific_product="소프트웨어",
        )

        self.assertLess(software["score"], furniture["score"])

    def test_class_3_vs_class_25_only_is_mostly_excluded(self) -> None:
        result = evaluate_registration(
            trademark_name="POOKIE",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["3류"],
            selected_codes=["G1201"],
            prior_items=[
                {
                    "applicationNumber": "4",
                    "trademarkName": "POOKIE",
                    "registerStatus": "등록",
                    "classificationCode": "25",
                    "applicantName": "D",
                }
            ],
            selected_fields=[{"class_no": "3류", "description": "화장품/미용", "example": "스킨케어"}],
            specific_product="화장품",
        )

        self.assertEqual(result["filtered_prior_count"], 0)
        self.assertGreaterEqual(result["score"], 70)
        self.assertEqual(result["group_counts"]["group_irrelevant"], 1)

    def test_same_similarity_code_and_high_phonetic_similarity_is_high_risk(self) -> None:
        result = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["20류"],
            selected_codes=["G2001"],
            prior_items=[
                {
                    "applicationNumber": "5",
                    "trademarkName": "LEXAIA",
                    "registerStatus": "등록",
                    "classificationCode": "20",
                    "similarityGroupCode": "G2001",
                    "applicantName": "E",
                }
            ],
            selected_fields=[{"class_no": "20류", "description": "가구/인테리어", "example": "책상"}],
            specific_product="가구",
        )

        self.assertEqual(result["group_counts"]["group_exact_code"], 1)
        self.assertLessEqual(result["score"], 50)

    def test_cross_class_same_similarity_code_is_included(self) -> None:
        result = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["20류"],
            selected_codes=["G2001"],
            prior_items=[
                {
                    "applicationNumber": "6",
                    "trademarkName": "LEXAI",
                    "registerStatus": "출원",
                    "classificationCode": "25",
                    "similarityGroupCode": "G2001",
                    "applicantName": "F",
                }
            ],
            selected_fields=[{"class_no": "20류", "description": "가구/인테리어", "example": "소파"}],
            specific_product="가구",
        )

        self.assertEqual(result["filtered_prior_count"], 1)
        self.assertEqual(result["group_counts"]["group_exact_code"], 1)

    def test_same_class_only_match_stays_in_supplementary_range(self) -> None:
        result = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["9류"],
            selected_codes=["G0901"],
            prior_items=[
                {
                    "applicationNumber": "7",
                    "trademarkName": "LEXAI",
                    "registerStatus": "등록",
                    "classificationCode": "9",
                    "applicantName": "G",
                }
            ],
            selected_fields=[{"class_no": "9류", "description": "전자기기/소프트웨어", "example": "앱"}],
            specific_product="소프트웨어",
        )

        self.assertEqual(result["filtered_prior_count"], 1)
        self.assertEqual(result["group_counts"]["group_same_class"], 1)
        self.assertGreaterEqual(result["score"], 55)
        self.assertLessEqual(result["score"], 75)

    def test_same_sales_code_is_only_limitedly_reflected(self) -> None:
        result = evaluate_registration(
            trademark_name="Lexai",
            trademark_type="문자만",
            is_coined=True,
            selected_classes=["35류"],
            selected_codes=["S2021"],
            prior_items=[
                {
                    "applicationNumber": "8",
                    "trademarkName": "LEXAI",
                    "registerStatus": "등록",
                    "classificationCode": "35",
                    "similarityGroupCode": "S2021",
                    "applicantName": "H",
                }
            ],
            selected_fields=[{"class_no": "35류", "description": "가구 판매업", "example": "온라인 스토어"}],
            specific_product="가구 판매업",
        )

        self.assertEqual(result["filtered_prior_count"], 1)
        self.assertEqual(result["group_counts"]["group_exact_code"], 0)
        self.assertEqual(result["group_counts"]["group_same_class"], 1)
        self.assertGreaterEqual(result["score"], 55)


if __name__ == "__main__":
    unittest.main()
