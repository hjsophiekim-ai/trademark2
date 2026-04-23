# Phonetic 오프라인 평가 리포트

## 데이터셋 요약
- 전체: 156
- positive(label=1): 84 (same_class 21)
- negative(label=0): 72 (same_class 18)
- pair_type 분포: {'en-en': 92, 'ko-ko': 36, 'cross': 28}

## Query expansion(오프라인 proxy) 효과
- positive recall gain(확장으로만 hit): 53/84 (63.1%)
- negative false hit gain(확장으로만 hit): 0/72 (0.0%)

## Threshold별 confusion matrix 요약 (mark_similarity 기준)
| threshold | TP | FP | TN | FN | precision | recall | f1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 50 | 70 | 48 | 24 | 14 | 0.593 | 0.833 | 0.693 |
| 60 | 68 | 28 | 44 | 16 | 0.708 | 0.810 | 0.756 |
| 70 | 43 | 1 | 71 | 41 | 0.977 | 0.512 | 0.672 |
| 75 | 16 | 1 | 71 | 68 | 0.941 | 0.190 | 0.317 |
| 80 | 1 | 1 | 71 | 83 | 0.500 | 0.012 | 0.023 |
| 85 | 0 | 0 | 72 | 84 | 0.000 | 0.000 | 0.000 |
| 90 | 0 | 0 | 72 | 84 | 0.000 | 0.000 | 0.000 |

## Best threshold(최대 F1): 60

## 오탐/누락 원인(규칙 경로 step 집계)
- FP 주요 step: [('Y->I', 14), ('CK->K', 9), ('GH->∅', 7), ('GH->G', 5), ('R->L', 4), ('TH->T', 4), ('T->D', 4), ('F->P', 4), ('L->R', 3), ('ING->IN', 3), ('OO->U', 3), ('TH->S', 2)]
- FN 주요 step: [('B->P', 1), ('P->F', 1), ('P->B', 1)]

## False Positive 예시(상위)
- ROCKY ↔ ROCKET | label=0 | appearance=73 phonetic=73 mark=62 | best_path=['CK->K', 'CK->K']
- MARK ↔ MARKET | label=0 | appearance=86 phonetic=80 mark=80 | best_path=[]
- LIVER ↔ LIVELY | label=0 | appearance=73 phonetic=73 mark=62 | best_path=[]
- LIGHT ↔ RIGHT | label=0 | appearance=80 phonetic=80 mark=68 | best_path=['GH->∅', 'GH->∅', 'R->L']
- NIGHT ↔ EIGHT | label=0 | appearance=80 phonetic=80 mark=68 | best_path=['GH->G', 'GH->G']
- THING ↔ THINK | label=0 | appearance=80 phonetic=80 mark=68 | best_path=['TH->T', 'ING->IN', 'TH->T']
- TARI ↔ TAXI | label=0 | appearance=75 phonetic=75 mark=64 | best_path=['X->Z']
- SOFTY ↔ SAFETY | label=0 | appearance=73 phonetic=73 mark=62 | best_path=[]
- AUNTY ↔ UNITY | label=0 | appearance=80 phonetic=80 mark=68 | best_path=[]
- CUTY ↔ CITY | label=0 | appearance=75 phonetic=75 mark=64 | best_path=[]
- HOKY ↔ HOCKEY | label=0 | appearance=80 phonetic=82 mark=69 | best_path=['CK->K']
- FOOKY ↔ FUNKY | label=0 | appearance=60 phonetic=76 mark=61 | best_path=['OO->U']
- 쿠키 ↔ 쿠폰 | label=0 | appearance=50 phonetic=78 mark=61 | best_path=[]
- 쿠키 ↔ 쿠션 | label=0 | appearance=50 phonetic=78 mark=61 | best_path=[]
- 로키 ↔ 로봇 | label=0 | appearance=50 phonetic=78 mark=61 | best_path=[]

## False Negative 예시(상위)
- PAPA ↔ BABA | label=1 | appearance=50 phonetic=53 mark=44 | best_path=['B->P']
- FOOKY ↔ 후키 | label=1 | appearance=0 phonetic=90 mark=58 | best_path=[]
- QUICK ↔ 퀵 | label=1 | appearance=0 phonetic=24 mark=16 | best_path=[]
- PHONE ↔ 폰 | label=1 | appearance=0 phonetic=24 mark=16 | best_path=[]
- FONE ↔ 폰 | label=1 | appearance=0 phonetic=53 mark=34 | best_path=[]
- ROCKY ↔ 로키 | label=1 | appearance=0 phonetic=43 mark=28 | best_path=[]
- LOCKY ↔ 로키 | label=1 | appearance=0 phonetic=43 mark=28 | best_path=[]
- PARK ↔ 파크 | label=1 | appearance=0 phonetic=25 mark=16 | best_path=[]
- MARK ↔ 마크 | label=1 | appearance=0 phonetic=25 mark=16 | best_path=[]
- LUNA ↔ 루나 | label=1 | appearance=0 phonetic=66 mark=43 | best_path=[]
- RUNA ↔ 루나 | label=1 | appearance=0 phonetic=66 mark=43 | best_path=[]
- TONE ↔ 톤 | label=1 | appearance=0 phonetic=53 mark=34 | best_path=[]
- DONE ↔ 돈 | label=1 | appearance=0 phonetic=45 mark=29 | best_path=[]
- 마크 ↔ 막 | label=1 | appearance=0 phonetic=75 mark=49 | best_path=[]
- 퀵 ↔ 쿠익 | label=1 | appearance=0 phonetic=65 mark=42 | best_path=[]
