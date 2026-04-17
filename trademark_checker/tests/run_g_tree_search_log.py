import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from trademark_checker.kipris_api import (  # noqa: E402
    build_kipris_search_plan,
    dedupe_search_candidates,
    search_all_pages,
)


def run():
    name = "G트리"
    scenarios = [
        ("금융, 통화 및 은행업", [36], ["S0201"], [], []),
        ("보험서비스업", [36], ["S0301"], [], []),
        ("부동산업", [36], ["S1212"], [], []),
        ("법무서비스업", [45], ["S120402"], [], []),
    ]
    for title, classes, primary, related, retail in scenarios:
        print(f"\n=== {title} ===")
        plan = build_kipris_search_plan(name, classes, primary, related_codes=related, retail_codes=retail)
        print("search_plan_modes", [step["query_mode"] for step in plan])
        merged = []
        for step in plan:
            for code in (step.get("codes") or [""]):
                result = search_all_pages(
                    name,
                    similar_goods_code=code,
                    class_no=step.get("class_no"),
                    max_pages=step.get("max_pages", 2),
                    query_mode=step.get("query_mode", ""),
                )
                merged.extend(result.get("items", []))
                print(
                    f"[{result.get('search_status')}] "
                    f"[{step.get('query_mode')}] "
                    f"[{step.get('search_mode')}] "
                    f"class={step.get('class_no')} code={code or '-'} "
                    f"hits={len(result.get('items', []))} "
                    f"extracted={result.get('extracted_total_count', 0)} "
                    f"detail_parse={result.get('detail_parse_count', 0)}"
                )
        print("merged_candidates", len(merged), "deduped_candidates", len(dedupe_search_candidates(merged)))


if __name__ == "__main__":
    run()
