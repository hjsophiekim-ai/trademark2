
import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from trademark_checker.kipris_api import (
    dedupe_search_candidates,
    search_trademark, 
    search_all_pages, 
    build_kipris_search_plan,
    STATUS_DETAIL_PARSE_ERROR,
    STATUS_SUCCESS_HITS,
    STATUS_SUCCESS_ZERO,
    STATUS_PARSE_ERROR
)

def test_query_builder():
    print("\n--- Testing Query Builder ---")
    plan = build_kipris_search_plan(
        "G트리",
        [36],
        ["S0201"],
        related_codes=["S120401"],
        retail_codes=["S2001"],
    )
    modes = [p["query_mode"] for p in plan]
    print(f"Modes created: {modes}")
    
    assert "text_fallback" in modes
    assert "class_only" in modes
    assert "primary_sc_only" in modes
    assert "primary_sc" in modes
    assert "related_sc_only" in modes
    assert "retail_sc_only" in modes
    
    for p in plan:
        print(f"Mode: {p['query_mode']}, Formula: {p['search_formula']}")
        assert "[" not in p["search_formula"]
        assert "]" not in p["search_formula"]

def test_union_dedup():
    print("\n--- Testing Union/Dedup ---")
    rows = [
        {"applicationNumber": "1", "registrationNumber": "", "trademarkName": "A"},
        {"applicationNumber": "1", "registrationNumber": "", "trademarkName": "A"},
        {"applicationNumber": "2", "registrationNumber": "R2", "trademarkName": "B"},
    ]
    deduped = dedupe_search_candidates(rows)
    assert len(deduped) == 2

def test_actual_search_g_tree():
    print("\n--- Testing Actual Search: G트리 ---")
    # TN broad fallback (Query A)
    result = search_all_pages("G트리", query_mode="text_fallback")
    print(f"Status: {result['search_status']}")
    print(f"Hits: {len(result['items'])}")
    assert result["search_status"] in [STATUS_SUCCESS_HITS, STATUS_DETAIL_PARSE_ERROR]
    assert len(result["items"]) > 0
    
    # TN + Class 36 (Query B)
    result = search_all_pages("G트리", class_no=36, query_mode="class_only")
    print(f"Status: {result['search_status']}")
    print(f"Hits: {len(result['items'])}")
    assert result["search_status"] in [STATUS_SUCCESS_HITS, STATUS_DETAIL_PARSE_ERROR]
    
    # Check hits
    names = [item.get("trademarkName", "") for item in result["items"]]
    print(f"Found names: {names}")
    found_orange = any("오렌" in name or "G트리" in name for name in names)
    print(f"Found 'G트리' or similar: {found_orange}")

def test_error_handling():
    print("\n--- Testing Error Handling (Simulated) ---")
    # KIPRIS usually errors on empty search or invalid formula
    # Our new builder avoids invalid formula, but let's test a very long query
    result = search_trademark("A" * 1000)
    print(f"Status for long query: {result['search_status']}")
    assert result["search_status"] != STATUS_SUCCESS_HITS

if __name__ == "__main__":
    try:
        test_query_builder()
        test_union_dedup()
        test_actual_search_g_tree()
        test_error_handling()
        print("\n✅ All reliability tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
