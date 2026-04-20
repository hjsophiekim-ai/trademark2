from __future__ import annotations

from dataclasses import dataclass

HARD_FAIL_STATUSES = {
    "transport_error",
    "parse_error",
    "blocked_or_unexpected_page",
}

SOFT_FAIL_STATUSES = {
    "detail_parse_error",
}


@dataclass(frozen=True)
class SearchHealth:
    total_queries: int
    success_queries: int
    hard_fail_queries: int
    soft_fail_queries: int
    last_error_msg: str = ""

    @property
    def any_fail(self) -> bool:
        return (self.hard_fail_queries + self.soft_fail_queries) > 0

    @property
    def should_cap_score(self) -> bool:
        return self.success_queries == 0


def classify_query(success: bool, search_status: str) -> str:
    status = str(search_status or "").strip()
    if not success:
        return "hard_fail"
    if status in HARD_FAIL_STATUSES:
        return "hard_fail"
    if status in SOFT_FAIL_STATUSES:
        return "soft_success"
    return "success"


def summarize_health(
    total_queries: int,
    success_queries: int,
    hard_fail_queries: int,
    soft_fail_queries: int,
    last_error_msg: str = "",
) -> SearchHealth:
    return SearchHealth(
        total_queries=int(total_queries),
        success_queries=int(success_queries),
        hard_fail_queries=int(hard_fail_queries),
        soft_fail_queries=int(soft_fail_queries),
        last_error_msg=str(last_error_msg or ""),
    )
