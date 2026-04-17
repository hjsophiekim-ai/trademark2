"""G트리 상표 등록 가능성 시나리오 회귀 테스트.

4가지 지정 서비스업 시나리오:
  1. 금융, 통화 및 은행업  (S0201)  → 오렌G트리 선행상표와 direct overlap → 점수 ≤ 50
  2. 보험서비스업          (S0301)  → 오렌G트리와 상이 코드 → 시나리오 1보다 높은 점수
  3. 부동산업              (S1212)  → 오렌G트리와 상이 코드 → 시나리오 1보다 높은 점수
  4. 법무서비스업          (S120402)→ 완전 별개 류(45) → 가장 높은 점수
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# trademark_checker 패키지 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "trademark_checker"))

from kipris_api import search_all_pages
from scoring import evaluate_registration
from nice_catalog import get_groups, subgroup_to_field


# ── 공통 선행상표 데이터 ──────────────────────────────────────────────────────
# prior_mark_detail_fixtures.json 과 동일한 오렌G트리 지정상품 데이터 (직접 주입)
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
        {
            "prior_item_label": "금융투자 관련 인터넷을 통한 정보제공 및 분석업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
            "source_page_or_source_field": "fixture",
            "parsing_confidence": "high",
        },
        {
            "prior_item_label": "주식/증권시장 정보제공업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
            "source_page_or_source_field": "fixture",
            "parsing_confidence": "high",
        },
    ],
}


def _make_field(kind: str, group_label: str, subgroup_label: str) -> dict:
    """nice_group_catalog에서 subgroup → field dict 생성."""
    group = next(g for g in get_groups(kind) if g["group_label"] == group_label)
    subgroup = next(s for s in group["subgroups"] if s["subgroup_label"] == subgroup_label)
    return subgroup_to_field(
        {
            "kind": kind,
            "group_id": group["group_id"],
            "group_label": group["group_label"],
            "group_hint": group.get("group_hint", ""),
            **subgroup,
        }
    )


def _run(
    trademark_name: str,
    selected_class: str,
    selected_codes: list[str],
    prior_items: list[dict],
    field_label: str,
    field_group: str,
    field_subgroup: str,
    specific_product: str,
) -> dict:
    field = _make_field("services", field_group, field_subgroup)
    return evaluate_registration(
        trademark_name=trademark_name,
        trademark_type="문자만",
        is_coined=True,
        selected_classes=[selected_class],
        selected_codes=selected_codes,
        prior_items=prior_items,
        selected_fields=[field],
        specific_product=specific_product,
    )


class GTreeScenarioTests(unittest.TestCase):
    """G트리 상표 4대 시나리오 회귀 테스트."""

    # ── 시나리오 1: 금융, 통화 및 은행업 ──────────────────────────────────────
    def test_scenario1_finance_has_exact_primary_overlap_and_low_score(self) -> None:
        """G트리 / 금융,통화,은행업 → S0201 → 오렌G트리 exact_primary_overlap → score ≤ 50."""
        result = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="금융, 통화 및 은행업",
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )

        # selected_primary_codes가 S0201 포함
        self.assertIn("S0201", result.get("selected_primary_codes", result.get("selected_similarity_codes", [])))

        # 선행상표 최소 1건 필터 통과
        self.assertGreaterEqual(result["filtered_prior_count"], 1)

        # 오렌G트리가 top_prior에 포함
        top_names = [p["trademarkName"] for p in result.get("top_prior", [])]
        self.assertIn("오렌G트리", top_names)

        # overlap_type: exact_primary_overlap 또는 related_primary_overlap
        top_prior_oren = next(p for p in result["top_prior"] if p["trademarkName"] == "오렌G트리")
        self.assertIn(
            top_prior_oren.get("overlap_type"),
            ("exact_primary_overlap", "related_primary_overlap"),
        )

        # 최종 점수 ≤ 50 (직접 충돌)
        self.assertLessEqual(result["score"], 50, f"score should be ≤ 50 but got {result['score']}")

    # ── 시나리오 2: 보험서비스업 ──────────────────────────────────────────────
    def test_scenario2_insurance_has_no_direct_overlap_and_higher_score_than_finance(self) -> None:
        """G트리 / 보험서비스업 → S0301 → 오렌G트리와 코드 불일치 → 시나리오 1보다 높은 점수."""
        result_finance = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="금융, 통화 및 은행업",
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        result_insurance = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0301"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="보험서비스업",
            field_group="기타 서비스",
            field_subgroup="보험서비스업",
            specific_product="보험서비스업",
        )

        # selected_primary_codes S0301 포함
        self.assertIn("S0301", result_insurance.get("selected_primary_codes", result_insurance.get("selected_similarity_codes", [])))

        # 보험 시나리오 점수 > 금융 시나리오 점수
        self.assertGreater(
            result_insurance["score"],
            result_finance["score"],
            f"insurance ({result_insurance['score']}) should > finance ({result_finance['score']})",
        )

    # ── 시나리오 3: 부동산업 ──────────────────────────────────────────────────
    def test_scenario3_realestate_has_no_direct_overlap_and_higher_score_than_finance(self) -> None:
        """G트리 / 부동산업 → S1212 → 오렌G트리와 코드 불일치 → 시나리오 1보다 높은 점수."""
        result_finance = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="금융, 통화 및 은행업",
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        result_realestate = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S1212"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="부동산업",
            field_group="기타 서비스",
            field_subgroup="부동산업",
            specific_product="부동산업",
        )

        self.assertIn("S1212", result_realestate.get("selected_primary_codes", result_realestate.get("selected_similarity_codes", [])))

        self.assertGreater(
            result_realestate["score"],
            result_finance["score"],
            f"realestate ({result_realestate['score']}) should > finance ({result_finance['score']})",
        )

    # ── 시나리오 4: 법무서비스업 ──────────────────────────────────────────────
    def test_scenario4_legal_service_has_highest_score(self) -> None:
        """G트리 / 법무서비스업 → S120402 (제45류) → 오렌G트리와 류 불일치 → 최고 점수."""
        result_finance = _run(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_label="금융, 통화 및 은행업",
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        result_legal = _run(
            trademark_name="G트리",
            selected_class="45",
            selected_codes=["S120402"],
            prior_items=[],  # 오렌G트리는 제36류 → 제45류 검색에서 제외됨
            field_label="법무서비스업",
            field_group="기타 서비스",
            field_subgroup="법무서비스업",
            specific_product="법무서비스업",
        )

        self.assertIn("S120402", result_legal.get("selected_primary_codes", result_legal.get("selected_similarity_codes", [])))

        # 법무 점수 > 금융 점수
        self.assertGreater(
            result_legal["score"],
            result_finance["score"],
            f"legal ({result_legal['score']}) should > finance ({result_finance['score']})",
        )

        # 법무 시나리오: prior_items가 없으므로 direct blocker 없어야 함
        self.assertEqual(result_legal.get("direct_score_prior_count", 0), 0)

    # ── Mock 검색 통합 테스트 ──────────────────────────────────────────────────
    def test_mock_search_finds_oren_gtree_for_gtree_class36(self) -> None:
        """KIPRIS_USE_MOCK=true 환경에서 G트리 검색 시 오렌G트리 반환 및 designated_items 파싱 확인."""
        import importlib
        import kipris_api

        # 환경변수 설정 후 USE_MOCK 강제 적용
        os.environ["KIPRIS_USE_MOCK"] = "true"
        importlib.reload(kipris_api)  # USE_MOCK 재로드

        try:
            result = kipris_api.search_all_pages(
                "G트리",
                similar_goods_code="S0201",
                class_no="36",
                query_mode="primary_sc",
            )
            self.assertTrue(result["success"], "검색이 성공해야 함")
            self.assertGreaterEqual(result["total_count"], 1, "오렌G트리 최소 1건 반환 기대")

            names = [item["trademarkName"] for item in result["items"]]
            self.assertIn("오렌G트리", names, f"오렌G트리 미검색됨. 결과: {names}")

            oren = next(item for item in result["items"] if item["trademarkName"] == "오렌G트리")
            desig = oren.get("prior_designated_items", [])
            self.assertGreaterEqual(len(desig), 1, "designated_items 최소 1건 파싱 기대")

            all_codes = [code for d in desig for code in d.get("prior_similarity_codes", [])]
            self.assertIn("S0201", all_codes, f"S0201 코드 미파싱됨. 파싱된 코드: {all_codes}")
        finally:
            del os.environ["KIPRIS_USE_MOCK"]
            importlib.reload(kipris_api)


if __name__ == "__main__":
    unittest.main()
