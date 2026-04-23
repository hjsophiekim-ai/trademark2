# 최종 QA 리포트(15개 대표 케이스)

- 총 케이스: 15
- 통과: 15
- 실패: 0

## 케이스 결과표
| case | trademark_name | prior | context | expected | actual_score | overlap_type | mark_similarity | product_similarity_score | confusion_score | exact_override | phonetic_similarity | pass | fail_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | LexAI | LexAI | 9류/goods: 소프트웨어 | 강한 blocker | 35 | exact_same_mark_same_class_near_goods | 100 | 70 | 92 | Y | 100 | Y |  |
| A2 | 꽃순이 | 꽃순이 | 25류/goods: 의류 | 강한 blocker | 28 | exact_same_mark_same_class | 100 | 78 | 95 | Y | 100 | Y |  |
| A3 | 서울병원 | 서울병원 | 44류/services: 의료서비스 | 강한 blocker(Stage2) + Stage1/2 구분 | 8 | exact_same_mark_same_class_near_goods | 100 | 68 | 92 | Y | 100 | Y |  |
| B4 | LexAI | LexAI | 42류/services: SaaS | related goods/services strong~medium-high | 55 | exact_same_mark_cross_class_trade_link | 100 | 58 | 88 | Y | 100 | Y |  |
| B5 | 동일상표 | 동일상표 | 25류/goods: 의류 | class35 direct retail link | 45 | class35_direct_retail_link | 100 | 40 | 88 |  | 100 | Y |  |
| B6 | 동일상표 | 동일상표 | 9류/goods: 소프트웨어 | class35 strong linkage | 45 | class35_direct_retail_link | 100 | 40 | 88 |  | 100 | Y |  |
| C7 | 동일상표 | 동일상표 | 44류/services: 의료서비스 | 광고업은 과대평가 금지(weak/none) | 94 | no_material_overlap | 0 | 0 | 0 |  | 0 | Y |  |
| C8 | 동일상표 | 동일상표 | 1류/goods: 산업용 화학품 | 자문업은 과대평가 금지(none) | 94 | no_material_overlap | 0 | 0 | 0 |  | 0 | Y |  |
| D9 | pookie | pooky | 9류/goods: 소프트웨어 | high phonetic + strong warning | 40 | exact_primary_overlap | 76 | 96 | 90 |  | 94 | Y |  |
| D10 | pookie | fooky | 9류/goods: 소프트웨어 | medium+ phonetic, pooky보다 약함 | 40 | exact_primary_overlap | 64 | 96 | 80 |  | 82 | Y |  |
| D11 | pookie | booky | 9류/goods: 소프트웨어 | P/B weak, fooky보다 과대평가 금지 | 40 | exact_primary_overlap | 62 | 96 | 80 |  | 79 | Y |  |
| D12 | rocky | locky | 9류/goods: 소프트웨어 | R/L medium | 40 | exact_primary_overlap | 68 | 96 | 80 |  | 80 | Y |  |
| E13 | 유반하지 | - | 44류/services: 의료업 | Stage1 high/fatal 자동판정 금지 | 87 |  | 0 | 0 | 0 |  | 0 | Y |  |
| E14 | 꽃순이 | 꽃순이 | 25류/goods: 의류 | Stage1 cap 금지 + Stage2에서만 검토 | 45 | class35_direct_retail_link | 100 | 40 | 88 |  | 100 | Y |  |
| E15 | 서울병원 | - | 44류/services: 의료업 | 지명+서비스 직접표시이면 Stage1 강한 거절 유지 | 8 |  | 0 | 0 | 0 |  | 0 | Y |  |

## 요약
- 전체 통과율: 15/15 (100%)

### 가장 위험한 오탐 3개(과대평가)
- D9: expected=high phonetic + strong warning / actual score=40 / overlap=exact_primary_overlap
- D11: expected=P/B weak, fooky보다 과대평가 금지 / actual score=40 / overlap=exact_primary_overlap
- D10: expected=medium+ phonetic, pooky보다 약함 / actual score=40 / overlap=exact_primary_overlap

### 가장 위험한 과소탐지 3개(과소평가)
- 없음

## 마지막 미세조정이 필요한 규칙 3개(제안)
- exact override floor 정책(류별 near/strong 구간)을 케이스별 오버슈트/언더슈트에 맞춰 재조정
- class35_general_market_link의 cap/penalty 정책을 업종별로 더 분리(광고/자문은 더 약하게)
- same_class_only 구간에서 phonetic>=92 조건의 confusion 하한/상한을 업종(상품/서비스)별로 분리
