from search_health import classify_query, summarize_health


def test_classify_query_success_zero_hits_is_success() -> None:
    assert classify_query(True, "success_zero_hits") == "success"


def test_classify_query_detail_parse_error_is_soft_fail() -> None:
    assert classify_query(True, "detail_parse_error") == "soft_success"


def test_should_cap_only_when_no_success_queries() -> None:
    health = summarize_health(
        total_queries=6,
        success_queries=1,
        hard_fail_queries=5,
        soft_fail_queries=0,
        last_error_msg="",
    )
    assert health.any_fail is True
    assert health.should_cap_score is False

    health2 = summarize_health(
        total_queries=6,
        success_queries=0,
        hard_fail_queries=6,
        soft_fail_queries=0,
        last_error_msg="",
    )
    assert health2.any_fail is True
    assert health2.should_cap_score is True
