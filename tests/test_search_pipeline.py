"""Search pipeline regression tests.

Tests for:
1. subgroup → primary code derivation (금융→S0201, 보험→S0301, 부동산→S1212, 법무→S120402)
2. selected_primary_codes empty → TN+class fallback search still runs
3. TN+class fallback recovers at least 1 prior candidate (mock mode)
4. Prior detail parsing after search → item-level SC codes extracted
5. Finance case: prior item S0201/S120401 overlap recognized
6. Direct overlap case: final probability ≤ 50
7. 보험/부동산 scores higher than 금융
8. "0건 → 90%" regression prevention test
"""

from __future__ import annotations

import os
import sys
import importlib
import unittest
from pathlib import Path

# Add trademark_checker to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "trademark_checker"))

from nice_catalog import get_groups, subgroup_to_field, derive_selected_scope
from scoring import evaluate_registration


# ── Fixture: 오렌G트리 class 36 선행상표 (S0201 지정) ──────────────────────────
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
        },
        {
            "prior_item_label": "금융 또는 재무에 관한 상담업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201", "S120401"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
        },
        {
            "prior_item_label": "금융 및 투자 관련 정보제공/자문/상담 및 연구업",
            "prior_class_no": "36",
            "prior_similarity_codes": ["S0201"],
            "prior_item_type": "service",
            "prior_underlying_goods_codes": [],
        },
    ],
}


def _make_field(kind: str, group_label: str, subgroup_label: str) -> dict:
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


def _eval(trademark_name, selected_class, selected_codes, prior_items,
          field_group, field_subgroup, specific_product):
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


class TestSubgroupToPrimaryCode(unittest.TestCase):
    """Test 1: subgroup → primary code derivation."""

    def _assert_code(self, group: str, subgroup: str, expected_code: str) -> None:
        field = _make_field("services", group, subgroup)
        # derive_selected_scope(selected_kind, selected_fields, ...)
        scope = derive_selected_scope("services", [field])
        primary_codes = scope.get("selected_primary_codes", scope.get("recommended_similarity_codes", []))
        # Also check raw similarity_codes on the field itself
        field_codes = field.get("similarity_codes", [])
        all_codes = list(dict.fromkeys(primary_codes + field_codes))
        self.assertIn(
            expected_code,
            all_codes,
            f"Expected {expected_code} in codes for '{subgroup}', got primary={primary_codes}, field={field_codes}",
        )

    def test_finance_maps_to_s0201(self) -> None:
        self._assert_code("기타 서비스", "금융, 통화 및 은행업", "S0201")

    def test_insurance_maps_to_s0301(self) -> None:
        self._assert_code("기타 서비스", "보험서비스업", "S0301")

    def test_realestate_maps_to_s1212(self) -> None:
        self._assert_code("기타 서비스", "부동산업", "S1212")

    def test_legal_maps_to_s120402(self) -> None:
        field = _make_field("services", "기타 서비스", "법무서비스업")
        scope = derive_selected_scope("services", [field])
        primary_codes = scope.get("selected_primary_codes", scope.get("recommended_similarity_codes", []))
        field_codes = field.get("similarity_codes", [])
        all_codes = list(dict.fromkeys(primary_codes + field_codes))
        self.assertIn("S120402", all_codes, f"Got: {all_codes}")


class TestSearchFallback(unittest.TestCase):
    """Test 2 & 3: even when primary codes are empty, TN+class fallback fires."""

    def setUp(self):
        os.environ["KIPRIS_USE_MOCK"] = "true"
        import kipris_api
        importlib.reload(kipris_api)
        self.kipris_api = kipris_api

    def tearDown(self):
        os.environ.pop("KIPRIS_USE_MOCK", None)
        importlib.reload(self.kipris_api)

    def test_class_only_fallback_always_runs(self) -> None:
        """Test 2: build_kipris_search_plan always includes class_only step."""
        from kipris_api import build_kipris_search_plan
        plan = build_kipris_search_plan("테스트", selected_classes=["36"], primary_codes=[], related_codes=[])
        modes = [step["query_mode"] for step in plan]
        self.assertIn("class_only", modes, f"class_only missing from plan: {modes}")

    def test_text_fallback_always_present(self) -> None:
        """Test 2b: build_kipris_search_plan always includes text_fallback step."""
        from kipris_api import build_kipris_search_plan
        plan = build_kipris_search_plan("테스트", selected_classes=["36"], primary_codes=[], related_codes=[])
        modes = [step["query_mode"] for step in plan]
        self.assertIn("text_fallback", modes, f"text_fallback missing from plan: {modes}")

    def test_empty_primary_codes_plan_still_has_search_steps(self) -> None:
        """Test 2c: empty primary_codes → plan still has at least 2 steps."""
        from kipris_api import build_kipris_search_plan
        plan = build_kipris_search_plan("G트리", selected_classes=["36"], primary_codes=[], related_codes=[])
        self.assertGreaterEqual(len(plan), 2, f"Plan too short: {plan}")

    def test_mock_search_recovers_prior_candidate(self) -> None:
        """Test 3: mock search for G트리 in class 36 returns at least 1 result."""
        result = self.kipris_api.search_all_pages(
            "G트리",
            similar_goods_code=None,
            class_no="36",
            query_mode="class_only",
        )
        self.assertTrue(result.get("success"), "Mock search should succeed")
        self.assertGreaterEqual(
            result.get("total_count", 0), 1,
            f"Expected at least 1 result, got: {result.get('total_count', 0)}"
        )


class TestPriorDetailParsing(unittest.TestCase):
    """Test 4: prior detail parsing produces item-level SC codes."""

    def setUp(self):
        os.environ["KIPRIS_USE_MOCK"] = "true"
        import kipris_api
        importlib.reload(kipris_api)
        self.kipris_api = kipris_api

    def tearDown(self):
        os.environ.pop("KIPRIS_USE_MOCK", None)
        importlib.reload(self.kipris_api)

    def test_search_result_has_designated_items_with_sc_codes(self) -> None:
        """Test 4: 오렌G트리 search result includes prior_designated_items with S0201."""
        result = self.kipris_api.search_all_pages(
            "G트리",
            similar_goods_code="S0201",
            class_no="36",
            query_mode="primary_sc",
        )
        self.assertTrue(result.get("success"))
        items = result.get("items", [])
        oren = next((i for i in items if "오렌G트리" in i.get("trademarkName", "")), None)
        self.assertIsNotNone(oren, f"오렌G트리 not found in {[i.get('trademarkName') for i in items]}")

        desig = oren.get("prior_designated_items", [])
        self.assertGreaterEqual(len(desig), 1, "No designated items parsed")
        all_codes = [c for d in desig for c in d.get("prior_similarity_codes", [])]
        self.assertIn("S0201", all_codes, f"S0201 not in parsed codes: {all_codes}")


class TestOverlapRecognition(unittest.TestCase):
    """Test 5: finance prior item with S0201/S120401 is recognized as overlap."""

    def test_finance_prior_item_s0201_triggers_overlap(self) -> None:
        result = _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        top = result.get("top_prior", [])
        oren = next((p for p in top if "오렌G트리" in p.get("trademarkName", "")), None)
        self.assertIsNotNone(oren, f"오렌G트리 not in top_prior: {[p.get('trademarkName') for p in top]}")
        self.assertIn(
            oren.get("overlap_type"),
            ("exact_primary_overlap", "related_primary_overlap"),
            f"Unexpected overlap_type: {oren.get('overlap_type')}",
        )


class TestDirectOverlapLowScore(unittest.TestCase):
    """Test 6: direct overlap → final probability ≤ 50."""

    def test_direct_overlap_score_le_50(self) -> None:
        result = _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        score = result.get("score", 999)
        self.assertLessEqual(score, 50, f"Expected score ≤ 50, got {score}")


class TestNonOverlapHigherScore(unittest.TestCase):
    """Test 7: 보험/부동산 scores higher than 금융 (no direct overlap)."""

    def _finance_score(self) -> int:
        return _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )["score"]

    def test_insurance_higher_than_finance(self) -> None:
        finance_score = self._finance_score()
        insurance_result = _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0301"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="보험서비스업",
            specific_product="보험서비스업",
        )
        self.assertGreater(
            insurance_result["score"], finance_score,
            f"insurance ({insurance_result['score']}) should > finance ({finance_score})"
        )

    def test_realestate_higher_than_finance(self) -> None:
        finance_score = self._finance_score()
        realestate_result = _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S1212"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="부동산업",
            specific_product="부동산업",
        )
        self.assertGreater(
            realestate_result["score"], finance_score,
            f"realestate ({realestate_result['score']}) should > finance ({finance_score})"
        )


class TestZeroResultsRegressionPrevention(unittest.TestCase):
    """Test 8: '0건 → 90%' regression — direct overlap must not yield high score."""

    def test_overlapping_prior_items_cannot_produce_90_percent(self) -> None:
        """If prior marks exist with direct code overlap, score must be ≤ 60."""
        result = _eval(
            trademark_name="G트리",
            selected_class="36",
            selected_codes=["S0201"],
            prior_items=[OREN_GTREE_CLASS36],
            field_group="기타 서비스",
            field_subgroup="금융, 통화 및 은행업",
            specific_product="금융서비스업",
        )
        score = result.get("score", 999)
        filtered = result.get("filtered_prior_count", 0)
        # Prior items were injected → filtered_prior_count must be ≥ 1
        self.assertGreaterEqual(
            filtered, 1,
            f"Injected prior items should pass filter, got filtered_prior_count={filtered}"
        )
        # Score with direct overlap must not be near 90%
        self.assertLessEqual(
            score, 60,
            f"Score with direct overlap should be ≤ 60%, got {score}%. "
            f"This may be the '0건 → 90%' regression."
        )


if __name__ == "__main__":
    unittest.main()
