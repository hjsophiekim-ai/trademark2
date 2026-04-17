from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trademark_checker"))

from kipris_api import build_kipris_search_plan


def test_kipris_search_plan_uses_tn_class_sc_layers() -> None:
    plan = build_kipris_search_plan(
        "G트리",
        [36],
        ["S0201"],
        related_codes=["S120401"],
        retail_codes=["S2099"],
    )
    modes = [step["query_mode"] for step in plan]
    assert modes[:4] == ["primary_sc", "class_only", "related_sc", "retail_sc"]
    assert modes[-1] == "text_fallback"
    assert plan[0]["search_formula"] == "TN=G트리 AND CLASS=36 AND SC=S0201"
    assert plan[1]["search_formula"] == "TN=G트리 AND CLASS=36"
