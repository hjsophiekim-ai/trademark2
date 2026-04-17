"""유사군코드 자동 도출 엔진 테스트.

canonical/alias/semantic/fallback 매핑 엔진의 핵심 시나리오를 검증한다.

테스트 케이스:
  1. 법률 -> S120402
  2. 법무서비스업 -> S120402  (S174599 단독 매핑 금지)
  3. 금융 -> S0201
  4. 재무상담 -> S120401
  5. 부동산중개 -> S1212
  6. 금융 또는 재무에 관한 정보제공업 -> S0201, S120401 (multi-code)
  7. 금융 또는 재무에 관한 상담업 -> S0201, S120401 (multi-code)
  8. 미매칭 36류 라벨 -> S173699 fallback
  9. 미매칭 45류 라벨 -> S174599 fallback
  10. 가상코드/무관코드 미생성
"""
from __future__ import annotations

import sys
from pathlib import Path

# 패키지 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "trademark_checker"))

import pytest
from similarity_code_db import derive_similarity_mapping


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def mapping(label: str, classes: list[int]) -> dict:
    return derive_similarity_mapping(label, seed_classes=classes)


def chosen(label: str, classes: list[int]) -> list[str]:
    return mapping(label, classes)["chosen_codes"]


def candidates(label: str, classes: list[int]) -> list[str]:
    return mapping(label, classes)["candidate_codes"]


def confidence(label: str, classes: list[int]) -> str:
    return mapping(label, classes)["match_confidence"]


def fallback_used(label: str, classes: list[int]) -> bool:
    return mapping(label, classes)["fallback_used"]


# ── 테스트 1: 법률 -> S120402 ────────────────────────────────────────────────

def test_법률_maps_to_S120402():
    codes = chosen("법률", [45])
    assert "S120402" in codes, f"법률 -> S120402 기대, 실제: {codes}"


def test_법률_no_S174599_as_primary():
    codes = chosen("법률", [45])
    assert codes != ["S174599"], "법률은 S174599 단독 매핑 금지"


# ── 테스트 2: 법무서비스업 -> S120402 (S174599 단독 금지) ────────────────────

def test_법무서비스업_maps_to_S120402():
    codes = chosen("법무서비스업", [45])
    assert "S120402" in codes, f"법무서비스업 -> S120402 기대, 실제: {codes}"


def test_법무서비스업_not_S174599_only():
    codes = chosen("법무서비스업", [45])
    assert codes != ["S174599"], "법무서비스업은 S174599 단독 매핑 금지"


def test_법무서비스업_confidence_not_fallback():
    conf = confidence("법무서비스업", [45])
    assert conf != "fallback", f"법무서비스업은 fallback이 아닌 신뢰도 기대, 실제: {conf}"


# ── 테스트 3: 금융 -> S0201 ──────────────────────────────────────────────────

def test_금융_maps_to_S0201():
    codes = chosen("금융", [36])
    assert "S0201" in codes, f"금융 -> S0201 기대, 실제: {codes}"


def test_금융통화은행업_maps_to_S0201():
    codes = chosen("금융, 통화 및 은행업", [36])
    assert "S0201" in codes, f"금융, 통화 및 은행업 -> S0201 기대, 실제: {codes}"


# ── 테스트 4: 재무상담 -> S120401 ────────────────────────────────────────────

def test_재무상담_maps_to_S120401():
    codes = chosen("재무상담", [36])
    assert "S120401" in codes, f"재무상담 -> S120401 기대, 실제: {codes}"


def test_재무관리_maps_to_S120401():
    codes = chosen("재무관리", [36])
    assert "S120401" in codes, f"재무관리 -> S120401 기대, 실제: {codes}"


# ── 테스트 5: 부동산중개 -> S1212 ────────────────────────────────────────────

def test_부동산중개_maps_to_S1212():
    codes = chosen("부동산중개", [36])
    assert "S1212" in codes, f"부동산중개 -> S1212 기대, 실제: {codes}"


def test_부동산업_maps_to_S1212():
    codes = chosen("부동산업", [36])
    assert "S1212" in codes, f"부동산업 -> S1212 기대, 실제: {codes}"


# ── 테스트 6: 금융 또는 재무에 관한 정보제공업 -> S0201 + S120401 ─────────────

def test_금융재무정보제공업_multi_code():
    codes = chosen("금융 또는 재무에 관한 정보제공업", [36])
    assert "S0201" in codes, f"S0201 기대, 실제: {codes}"
    assert "S120401" in codes, f"S120401 기대, 실제: {codes}"


def test_금융재무정보제공업_not_fallback():
    conf = confidence("금융 또는 재무에 관한 정보제공업", [36])
    assert conf != "fallback", f"fallback이 아닌 신뢰도 기대, 실제: {conf}"


# ── 테스트 7: 금융 또는 재무에 관한 상담업 -> S0201 + S120401 ───────────────

def test_금융재무상담업_multi_code():
    codes = chosen("금융 또는 재무에 관한 상담업", [36])
    assert "S0201" in codes, f"S0201 기대, 실제: {codes}"
    assert "S120401" in codes, f"S120401 기대, 실제: {codes}"


# ── 테스트 8: 미매칭 36류 라벨 -> S173699 fallback ───────────────────────────

def test_미매칭_36류_fallback_to_S173699():
    label = "제36류에없는완전히새로운서비스업XYZABC123"
    result = mapping(label, [36])
    assert result["fallback_used"] is True, "fallback이 사용되어야 함"
    # fallback 코드가 S173699여야 함
    fallback_codes = [
        c["code"] for c in result["candidate_rows"] if c.get("fallback_used")
    ]
    assert "S173699" in fallback_codes, f"36류 fallback = S173699 기대, 실제: {fallback_codes}"


# ── 테스트 9: 미매칭 45류 라벨 -> S174599 fallback ───────────────────────────

def test_미매칭_45류_fallback_to_S174599():
    label = "제45류에없는완전히새로운서비스업XYZABC456"
    result = mapping(label, [45])
    assert result["fallback_used"] is True, "fallback이 사용되어야 함"
    fallback_codes = [
        c["code"] for c in result["candidate_rows"] if c.get("fallback_used")
    ]
    assert "S174599" in fallback_codes, f"45류 fallback = S174599 기대, 실제: {fallback_codes}"


# ── 테스트 10: 가상코드/무관코드 미생성 ──────────────────────────────────────

def test_가상코드_S3601_미생성():
    result = mapping("법무서비스업", [45])
    all_codes = result["candidate_codes"]
    assert "S3601" not in all_codes, f"가상코드 S3601 생성 금지, 실제: {all_codes}"
    assert "S3602" not in all_codes, f"가상코드 S3602 생성 금지"
    assert "S3603" not in all_codes, f"가상코드 S3603 생성 금지"


def test_무관코드_미생성_법무():
    """법무서비스업 검색 시 무관한 류의 코드가 섞이지 않아야 한다."""
    result = mapping("법무서비스업", [45])
    for c in result["candidate_rows"]:
        class_num = c.get("class_number")
        if class_num is not None:
            assert class_num == 45, f"45류 외 코드 포함: code={c['code']}, class={class_num}"


# ── 추가: 보험업 -> S0301 ─────────────────────────────────────────────────────

def test_보험업_maps_to_S0301():
    codes = chosen("보험서비스업", [36])
    assert "S0301" in codes, f"보험서비스업 -> S0301 기대, 실제: {codes}"


# ── 추가: 법률상담 -> S120402 ────────────────────────────────────────────────

def test_법률상담_maps_to_S120402():
    codes = chosen("법률상담", [45])
    assert "S120402" in codes, f"법률상담 -> S120402 기대, 실제: {codes}"


# ── 추가: 재무에 관한 정보제공업 -> S120401 ──────────────────────────────────

def test_재무정보제공업_includes_S120401():
    codes = chosen("재무에 관한 정보제공업", [36])
    assert "S120401" in codes, f"재무에 관한 정보제공업 -> S120401 기대, 실제: {codes}"


# ── 추가: debug_log 포함 확인 ────────────────────────────────────────────────

def test_debug_log_present():
    result = mapping("법무서비스업", [45])
    assert "debug_log" in result, "debug_log 필드가 결과에 있어야 함"
    assert isinstance(result["debug_log"], list)


def test_explicitly_chosen_field():
    result = mapping("법무서비스업", [45])
    assert "_explicitly_chosen" in result
    assert "S120402" in result["_explicitly_chosen"]


if __name__ == "__main__":
    # 직접 실행 시 요약 출력
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    test_cases = [
        ("법률", [45]),
        ("법무", [45]),
        ("법무서비스업", [45]),
        ("법률상담업", [45]),
        ("법률상담", [45]),
        ("금융", [36]),
        ("금융, 통화 및 은행업", [36]),
        ("재무상담", [36]),
        ("재무관리", [36]),
        ("재무정보", [36]),
        ("부동산중개", [36]),
        ("부동산업", [36]),
        ("보험서비스업", [36]),
        ("금융 또는 재무에 관한 정보제공업", [36]),
        ("금융 또는 재무에 관한 상담업", [36]),
        ("재무에 관한 정보제공업", [36]),
        ("제36류에없는완전히새로운서비스업XYZABC123", [36]),
        ("제45류에없는완전히새로운서비스업XYZABC456", [45]),
    ]

    print("=" * 72)
    print("유사군코드 자동 도출 검증 결과")
    print("=" * 72)
    for label, classes in test_cases:
        result = mapping(label, classes)
        chosen_c = result["chosen_codes"]
        conf = result["match_confidence"]
        reason = result["match_reason"]
        fb = result["fallback_used"]
        print(f"\n[{label}] (류: {classes})")
        print(f"  chosen_codes   : {chosen_c}")
        print(f"  confidence     : {conf}")
        print(f"  reason         : {reason}")
        print(f"  fallback_used  : {fb}")
        if result.get("debug_log"):
            print(f"  debug_log      : {result['debug_log']}")
