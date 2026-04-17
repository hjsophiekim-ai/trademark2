# 니스분류 기반 상품류/상품군 UI 설계

## 1. 사용자 입력 원칙
- 사용자는 상품군만 선택한다.
- 유사군코드 직접 선택 UI는 노출하지 않는다.
- 입력 단계는 아래만 유지한다.
  - 분류 1: goods / services
  - 분류 2: 그룹
  - 상품군 또는 서비스군
  - 필요 시 구체 상품명

## 2. 시스템 자동 도출
상품군 선택 후 시스템이 자동으로 아래를 계산한다.
- `derived_nice_classes`
- `selected_primary_codes`
- `selected_related_codes`
- `selected_retail_codes`
- `candidate_similarity_codes`

기본 원칙:
- UI에는 코드 선택 단계를 만들지 않는다.
- 내부 엔진만 primary / related / retail code를 자동 도출한다.
- 상품군 기본 코드는 primary 위주로 유지하고, related / retail은 후보 코드로 분리한다.

## 3. 검색 단계
검색은 넓게, 평가는 좁게 한다.

### 3.1 KIPRIS recall
- 1차: `TN + class + primary SC`
- 2차: `TN + class only`
- 2차 보조: `TN + related SC`
- 2차 보조: `TN + retail/service SC`
- 마지막: `TN` broad fallback

### 3.2 평가 기준
- 검색 결과를 그대로 direct conflict로 보지 않는다.
- prior mark 비교는 반드시 prior designated item의 item-level SC 기준으로 한다.
- 검색식에 사용한 SC는 recall metadata로만 남긴다.

## 4. item-level 비교 엔진
각 selected subgroup와 prior designated item 쌍마다 아래를 계산한다.
- `selected_primary_codes`
- `selected_related_codes`
- `selected_retail_codes`
- `prior_similarity_codes`
- `overlap_type`
- `overlap_confidence`
- `strongest prior item`
- `strongest prior codes`

overlap_type:
- `exact_primary_overlap`
- `related_primary_overlap`
- `retail_overlap_only`
- `same_class_only`
- `no_material_overlap`

## 5. 사용자 설명 원칙
사용자에게는 코드 체계보다 결과 이유를 보여준다.

표시 예:
- 금융
  - `오렌G트리의 지정항목 중 금융 또는 재무에 관한 정보제공업이 S0201/S120401로 직접 겹쳐 실질 충돌 위험이 높습니다.`
- 보험
  - `같은 36류이지만 prior item에 S0301 직접 겹침이 없어 보조 검토군으로만 반영했습니다.`
- 부동산
  - `같은 36류이지만 prior item에 S1212 직접 겹침이 없어 보조 검토군으로만 반영했습니다.`
- 법무
  - `45류 S120402와 직접 겹치는 prior item이 없어 상대적 거절사유 위험이 낮습니다.`

## 6. 판매업 코드
- 판매업 코드는 별도 계층으로 저장한다.
- 판매업 코드만 같다고 자동 유사로 올리지 않는다.
- underlying goods relation이 있으면 `related_primary_overlap`으로 승격할 수 있다.
- underlying goods relation이 없으면 `retail_overlap_only` 약신호로만 반영한다.

## 7. 점수 반영 원칙
- direct overlap이 있으면 final probability cap을 강하게 건다.
- same-class-only와 exact overlap을 같은 밴드로 처리하지 않는다.
- direct overlap인데도 75가 유지되면 실패다.
- UI는 단순하게 유지하되, 내부 평가는 item-level SC 기준으로 엄격하게 수행한다.

## 8. 상품군 선택 → 코드 자동 도출 규칙

### 8.1 subgroup → primary code 도출
- 사용자가 상품군(subgroup)을 선택하면 시스템이 자동으로 primary code를 결정한다.
- `nice_group_catalog.json`의 `similarity_codes` 필드가 primary codes다.
- `candidate_similarity_codes` 필드는 후보 목록이며, 일부만 primary로 승격된다.

주요 매핑 기준값:
| 상품군 | primary code |
|---|---|
| 금융, 통화 및 은행업 | S0201 |
| 보험서비스업 | S0301 |
| 부동산업 | S1212 |
| 법무서비스업 | S120402 |

### 8.2 코드 도출 실패 → 검색은 계속된다
- `similarity_codes`가 없거나 도출에 실패해도 검색을 중단하지 않는다.
- `mapping_failed_reason`에 실패 사유를 기록하고, class_only fallback으로 계속 진행한다.
- SC 없이 `TN + class`만으로도 유의미한 prior candidates를 회수할 수 있다.

### 8.3 코드 도출 → 검색 → 파싱 → overlap 평가 파이프라인
```
사용자 subgroup 선택
  → similarity_codes (primary) 도출
  → build_kipris_search_plan (항상 class_only + text_fallback 포함)
  → KIPRIS 검색 실행
  → enrich_search_results_with_item_details (prior designated items 파싱)
  → normalize_selected_input (primary/related/retail codes 확정)
  → overlap_type 계산 (per prior item × per selected code)
  → Stage 2 score cap 결정
  → min(Stage 1 cap, Stage 2) → 최종 점수
```

## 9. 검색 파이프라인 디버그 정보 표시

개발/검증 모드에서 아래 정보를 반드시 표시한다:
- `selected_subgroup`: 사용자가 선택한 상품군 이름
- `selected_primary_codes`: 도출된 primary 유사군코드
- `selected_related_codes`: 도출된 related 유사군코드
- `selected_retail_codes`: 도출된 retail 유사군코드
- `mapping_failed_reason`: 코드 도출 실패 사유 (있을 경우)
- `search_queries_attempted`: 실행된 검색 쿼리 목록
- `search_hits_per_query`: 각 쿼리의 결과 건수
- `detail_parse_count`: item-level 파싱 성공 건수
- `strongest_prior_item`: 가장 강한 충돌 prior item label
- `strongest_prior_codes`: 해당 item의 SC codes
- `overlap_type`: 최종 결정된 overlap 유형

앱 UI에서는 "검색 파이프라인 디버그" 접기 섹션으로 표시하며, PDF 보고서에서는 "Search Debug" 섹션으로 출력한다.
