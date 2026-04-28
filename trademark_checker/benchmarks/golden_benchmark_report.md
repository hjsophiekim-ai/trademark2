# Golden Benchmark (Exact Override + Product Fallback)

- cases: 74
- passed: 74
- failed: 0

## 비교표(수정 전/후)
| id | category | expected | pre_score | post_score | pre_overlap | post_overlap | pre_prod | post_prod | pre_conf | post_conf | post_exact_override | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EXACT_SAME_CLASS_NO_SC_9 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 80 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_25 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 78 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_30 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 75 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_35 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 70 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_41 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 72 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_42 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 24 | 80 | 70 | 95 | Y | Y |
| EXACT_SAME_CLASS_NO_SC_44 | exact same mark + same class | should_be_strong_blocker | 50 | 20 | same_class_only | exact_same_mark_same_class | 12 | 78 | 70 | 95 | Y | Y |
| EXACT_RELATED_LINK_9_42 | exact same mark + related class | should_be_medium_risk | 18 | 35 | no_material_overlap | exact_same_mark_cross_class_trade_link | 58 | 58 | 88 | 88 | Y | Y |
| EXACT_UNRELATED_CLASS_NO_OVERRIDE | exact same mark + unrelated class | should_not_be_exact_override | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |
| PHON_POOKIE_POOKY | high phonetic similarity only | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON_POOKIE_FOOKY | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 44 | 44 |  | Y |
| PHON_ROCKY_LOCKY | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 47 | 47 |  | Y |
| PHON_KOOZIE_COOZY | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 41 | 41 |  | Y |
| PHON_MEETECH_MEETTEK | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 47 | 47 |  | Y |
| SAME_CLASS_ONLY_WEAK_GOODS | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
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
| EXACT_RELATED_9_35 | exact same mark + related class | should_be_medium_risk | 45 | 30 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_25_35 | exact same mark + related class | should_be_medium_risk | 45 | 30 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_30_43 | exact same mark + related class | should_be_medium_risk | 86 | 46 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_31_44 | exact same mark + related class | should_be_medium_risk | 86 | 46 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_9_42 | exact same mark + related class | should_be_medium_risk | 18 | 36 | no_material_overlap | exact_same_mark_cross_class_trade_link | 58 | 58 | 88 | 88 | Y | Y |
| EXACT_RELATED_20_35 | exact same mark + related class | should_be_medium_risk | 45 | 30 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_18_35 | exact same mark + related class | should_be_medium_risk | 45 | 30 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_31_35 | exact same mark + related class | should_be_medium_risk | 45 | 30 | class35_direct_retail_link | class35_direct_retail_link | 40 | 40 | 88 | 88 |  | Y |
| EXACT_RELATED_5_44 | exact same mark + related class | should_be_medium_risk | 86 | 46 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
| EXACT_RELATED_16_41 | exact same mark + related class | should_be_medium_risk | 86 | 46 | no_material_overlap | exact_same_mark_cross_class_trade_link | 32 | 45 | 70 | 88 | Y | Y |
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
| PHON2_NEUROAI_NEUROAY | high phonetic similarity only | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_DATAMART_DATAMARTT | high phonetic similarity only | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_CARELINE_KERELINE | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 43 | 43 |  | Y |
| PHON2_CLOUDTEK_CLOUDTECH | high phonetic similarity only | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_MEDITEC_MEDITEK | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 50 | 50 |  | Y |
| PHON2_EDULINE_EDYLINE | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 50 | 50 |  | Y |
| PHON2_APPCARE_APPCAREE | high phonetic similarity only | should_remain_same_class_only | 50 | 50 | same_class_only | same_class_only | 12 | 12 | 70 | 70 |  | Y |
| PHON2_KOFFEE_COFFEE | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 49 | 49 |  | Y |
| PHON2_TEALINE_TLINE | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 49 | 49 |  | Y |
| PHON2_FOOTWEAR_FOOTWARE | high phonetic similarity only | should_remain_same_class_only | 75 | 75 | same_class_only | same_class_only | 12 | 12 | 51 | 51 |  | Y |
| SAME_CLASS_WEAK_0 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_1 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_2 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_3 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_4 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_5 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_6 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_7 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_8 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_9 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_10 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_11 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_12 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_13 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| SAME_CLASS_WEAK_14 | same class only but weak goods overlap | should_be_class36_near_or_core | 8 | 8 | same_class_near_services | same_class_near_services | 45 | 45 | 70 | 70 |  | Y |
| CLASS36_GTREE_FINANCE_OREN | class36 same class near/core services | should_be_class36_near_or_core | 48 | 48 | same_class_core_service_link | same_class_core_service_link | 68 | 68 | 78 | 78 |  | Y |
| CLASS36_GTREE_REALESTATE_OREN | class36 same class near/core services | should_be_class36_near_or_core | 48 | 48 | same_class_core_service_link | same_class_core_service_link | 68 | 68 | 78 | 78 |  | Y |
| BLOCKER_GTREE_FINANCE_REGISTERED_INSURANCE_PRIOR | high similarity live blocker | should_be_low_due_to_blocker | 52 | 50 | same_class_near_services | same_class_near_services | 45 | 45 | 69 | 69 |  | Y |
| CLEAN_CASE_CLASS45_LEGAL_NO_PRIOR | high baseline when clean | should_be_high_when_clean | 95 | 95 |  |  | 0 | 0 | 0 | 0 |  | Y |

## 실패 케이스 요약(FP/FN 후보)
- 없음
