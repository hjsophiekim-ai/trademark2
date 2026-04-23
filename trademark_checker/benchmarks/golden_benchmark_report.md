# Golden Benchmark (Exact Override + Product Fallback)

- cases: 70
- passed: 60
- failed: 10

## 비교표(수정 전/후)
| id | category | expected | pre_score | post_score | pre_overlap | post_overlap | pre_prod | post_prod | pre_conf | post_conf | post_exact_override | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXACT_SAME_CLASS_NO_SC_9 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 70 | 70 | 92 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_25 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 68 | 70 | 92 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_30 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 65 | 70 | 92 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_35 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 62 | 70 | 92 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_41 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 62 | 70 | 92 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_42 | exact same mark + same class | should_be_strong_blocker | 50 | 28 | same_class_only | exact_same_mark_same_class | 24 | 80 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_44 | exact same mark + same class | should_be_strong_blocker | 50 | 35 | same_class_only | exact_same_mark_same_class_near_goods | 12 | 68 | 70 | 92 | Y | Y |
| EXACT_RELATED_LINK_9_42 | exact same mark + related class | should_be_medium_risk | 18 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 58 | 58 | 88 | 88 | Y | Y |
| EXACT_UNRELATED_CLASS_NO_OVERRIDE | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| PHON_POOKIE_POOKY | high phonetic similarity only | should_be_medium_risk | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON_POOKIE_FOOKY | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 44 | 44 |  |  |
| PHON_ROCKY_LOCKY | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 47 | 47 |  |  |
| PHON_KOOZIE_COOZY | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 41 | 41 |  |  |
| PHON_MEETECH_MEETTEK | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 47 | 47 |  |  |
| SAME_CLASS_ONLY_WEAK_GOODS | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 55 | 55 |  | Y |
| SC_MISSING_0 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_1 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_2 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_3 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_4 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_5 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_6 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_7 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_8 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| SC_MISSING_9 | SC code missing cases | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| EXACT_RELATED_9_35 | exact same mark + related class | should_be_medium_risk | 45 | 45 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_25_35 | exact same mark + related class | should_be_medium_risk | 45 | 45 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_30_43 | exact same mark + related class | should_be_medium_risk | 86 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_31_44 | exact same mark + related class | should_be_medium_risk | 86 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_9_42 | exact same mark + related class | should_be_medium_risk | 18 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 58 | 58 | 88 | 88 | Y | Y |
| EXACT_RELATED_20_35 | exact same mark + related class | should_be_medium_risk | 45 | 45 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_18_35 | exact same mark + related class | should_be_medium_risk | 45 | 45 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_31_35 | exact same mark + related class | should_be_medium_risk | 45 | 45 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_5_44 | exact same mark + related class | should_be_medium_risk | 86 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_16_41 | exact same mark + related class | should_be_medium_risk | 86 | 55 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_UNRELATED_9_20 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_25_1 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_30_9 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_44_30 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_41_1 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_42_25 | exact same mark + unrelated class | should_not_be_exact_override | 18 | 18 | no_material_overlap | no_material_overlap | 58 | 58 | 88 | 88 |  | Y |
| EXACT_UNRELATED_35_1 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_20_44 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_18_30 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| EXACT_UNRELATED_31_9 | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| PHON2_NEUROAI_NEUROAY | high phonetic similarity only | should_be_medium_risk | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_DATAMART_DATAMARTT | high phonetic similarity only | should_be_medium_risk | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_CARELINE_KERELINE | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 43 | 43 |  |  |
| PHON2_CLOUDTEK_CLOUDTECH | high phonetic similarity only | should_be_medium_risk | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_MEDITEC_MEDITEK | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 50 | 50 |  |  |
| PHON2_EDULINE_EDYLINE | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 50 | 50 |  |  |
| PHON2_APPCARE_APPCAREE | high phonetic similarity only | should_be_medium_risk | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_KOFFEE_COFFEE | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 49 | 49 |  |  |
| PHON2_TEALINE_TLINE | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 49 | 49 |  |  |
| PHON2_FOOTWEAR_FOOTWARE | high phonetic similarity only | should_be_medium_risk | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 51 | 51 |  |  |
| SAME_CLASS_WEAK_0 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_1 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_2 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_3 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_4 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_5 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_6 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_7 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_8 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_9 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_10 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_11 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_12 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_13 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |
| SAME_CLASS_WEAK_14 | same class only but weak goods overlap | should_remain_same_class_only | 8 | 8 | same_class_only | same_class_only | 12 | 12 | 57 | 57 |  | Y |

## 실패 케이스 요약(FP/FN 후보)
- FN(과소평가) 10건 / FP(과대평가) 0건

### FN 상위(과소평가)
- PHON_POOKIE_FOOKY (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=44
- PHON_ROCKY_LOCKY (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=47
- PHON_KOOZIE_COOZY (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=41
- PHON_MEETECH_MEETTEK (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=47
- PHON2_CARELINE_KERELINE (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=43
- PHON2_MEDITEC_MEDITEK (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=50
- PHON2_EDULINE_EDYLINE (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=50
- PHON2_KOFFEE_COFFEE (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=49
- PHON2_TEALINE_TLINE (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=49
- PHON2_FOOTWEAR_FOOTWARE (high phonetic similarity only, expected=should_be_medium_risk): post overlap=same_class_only, post score=75, post prod=12, post conf=51

### FP 상위(과대평가)
- 없음
