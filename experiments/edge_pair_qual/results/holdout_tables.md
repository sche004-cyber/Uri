| Family (n) | deterministic | needle_P0 | needle_P1 | granite_native_P0 | granite_native_P1 | granite_json_P0 | granite_json_P1 | granitecpu_json_P1 | brain_P1 |
|---|---|---|---|---|---|---|---|---|---|
| AMBIGUITY (10) | 10/10 | 0/10 | 2/10 | 0/10 | 0/10 | 0/10 | 1/10 | 1/10 | 4/10 |
| ARGS (12) | 6/12 | 11/12 | 10/12 | 11/12 | 10/12 | 11/12 | 10/12 | 10/12 | 12/12 |
| ESCALATE (11) | 11/11 | 2/11 | 5/11 | 0/11 | 1/11 | 0/11 | 4/11 | 4/11 | 7/11 |
| EXTRACT (9) | 0/9 | 2/9 | 2/9 | 2/9 | 2/9 | 3/9 | 3/9 | 3/9 | 5/9 |
| INJECTION (13) | 6/13 | 9/13 | 7/13 | 7/13 | 7/13 | 5/13 | 5/13 | 5/13 | 10/13 |
| MULTISTEP (5) | 3/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |
| NEGATION (15) | 5/15 | 10/15 | 6/15 | 10/15 | 14/15 | 10/15 | 10/15 | 11/15 | 15/15 |
| REFERENCE (14) | 8/14 | 4/14 | 4/14 | 6/14 | 6/14 | 5/14 | 4/14 | 4/14 | 11/14 |
| ROUTE (12) | 0/12 | 1/12 | 1/12 | 7/12 | 7/12 | 7/12 | 7/12 | 6/12 | 12/12 |
| SELECT (17) | 5/17 | 14/17 | 13/17 | 16/17 | 16/17 | 16/17 | 15/17 | 15/17 | 17/17 |
| SEMANTIC (10) | 0/10 | 3/10 | 3/10 | 3/10 | 3/10 | 6/10 | 6/10 | 6/10 | 10/10 |
| UNSUPPORTED (10) | 10/10 | 4/10 | 4/10 | 2/10 | 2/10 | 0/10 | 0/10 | 0/10 | 8/10 |
| **All** | 64/138 | 60/138 | 57/138 | 64/138 | 68/138 | 63/138 | 65/138 | 65/138 | 112/138 |

| Arm | false accept on no-action select cases | executed correct | executed incorrect | contained by URI | held for approval (right / wrong) | p50 / p95 latency ms (warm p50) |
|---|---|---|---|---|---|---|
| deterministic | 2/49 | 7 | 13 | 0 | 0 / 0 | 0.0 / 0.1 (0.0) |
| needle_P0 | 41/49 | 83 | 95 | 72 | 16 / 12 | 518.8 / 760.0 (429.8) |
| needle_P1 | 36/49 | 68 | 75 | 86 | 17 / 12 | 734.3 / 993.2 (707.6) |
| granite_native_P0 | 47/49 | 105 | 69 | 105 | 21 / 0 | 203.5 / 516.9 (203.5) |
| granite_native_P1 | 42/49 | 102 | 60 | 94 | 24 / 0 | 253.7 / 508.6 (253.7) |
| granite_json_P0 | 49/49 | 90 | 48 | 144 | 24 / 0 | 218.8 / 421.8 (218.8) |
| granite_json_P1 | 42/49 | 80 | 68 | 113 | 21 / 0 | 166.0 / 385.5 (166.0) |
| granitecpu_json_P1 | 42/49 | 87 | 60 | 108 | 24 / 0 | 744.6 / 989.4 (744.6) |
| brain_P1 | 19/49 | 120 | 30 | 36 | 30 / 0 | 883.8 / 1539.7 (883.8) |
| needle_R1 | 35/49 | 89 | 122 | 20 | 33 / 0 | 1146.1 / 1483.2 (1150.3) |
| granite_json_R1 | 44/49 | 96 | 159 | 0 | 33 / 0 | 944.8 / 1309.3 (944.8) |

| Arm | present fields exact | absent fields correct | invented | wrong verbatim value accepted by N5 |
|---|---|---|---|---|
| needle_P1 | 45/99 | 9/12 | 3 | 31 |
| granite_native_P1 | 60/99 | 3/12 | 9 | 39 |
| granite_json_P1 | 66/99 | 9/12 | 3 | 33 |
| granitecpu_json_P1 | 66/99 | 9/12 | 3 | 33 |
| brain_P1 | 75/99 | 12/12 | 0 | 18 |

| Configuration | success | incorrect | safe fail | Brain call share | model calls / case | p50 / p95 ms |
|---|---|---|---|---|---|---|
| C0_deterministic_only | 14/138 (0.1014, lb 0.0624) | 13 | 111 | 0.0 | 0.0 | 0.0 / 0.1 |
| C1_needle_alone | 47/138 (0.3406, lb 0.2737) | 39 | 52 | 0.0 | 0.877 | 670.8 / 955.0 |
| C2_granite_alone | 56/138 (0.4058, lb 0.3355) | 34 | 48 | 0.0 | 0.877 | 179.1 / 491.4 |
| C3_pair_selective_by_kind | 56/138 (0.4058, lb 0.3355) | 34 | 48 | 0.0 | 0.877 | 179.1 / 491.4 |
| C3o_pair_selective_by_family_ORACLE_UPPER_BOUND | 59/138 (0.4275, lb 0.3563) | 39 | 40 | 0.0 | 0.877 | 266.7 / 790.1 |
| C4_pair_sequential_needle_then_granite | 59/138 (0.4275, lb 0.3563) | 51 | 28 | 0.0 | 1.167 | 679.9 / 1338.2 |
| C4b_pair_sequential_granite_then_needle | 69/138 (0.5, lb 0.4269) | 41 | 28 | 0.0 | 1.138 | 278.8 / 1123.8 |
| C5_main_brain_alone | 109/138 (0.7899, lb 0.7247) | 17 | 12 | 1.0 | 1.0 | 907.5 / 1794.2 |
| C6_hybrid_det_selective_by_kind_then_brain | 86/138 (0.6232, lb 0.5502) | 45 | 7 | 0.3188 | 1.036 | 272.7 / 1493.1 |
| C6o_hybrid_det_selective_by_family_ORACLE_then_brain | 85/138 (0.6159, lb 0.5428) | 50 | 3 | 0.2536 | 0.971 | 285.9 / 1619.0 |
| C6b_hybrid_det_granite_then_brain | 86/138 (0.6232, lb 0.5502) | 45 | 7 | 0.3188 | 1.036 | 272.7 / 1493.1 |
| C6c_hybrid_det_needle_then_brain | 82/138 (0.5942, lb 0.5208) | 54 | 2 | 0.3261 | 1.043 | 703.1 / 2074.2 |
| C7_det_then_brain | 100/138 (0.7246, lb 0.6552) | 27 | 11 | 0.8043 | 0.804 | 742.8 / 1620.5 |

| Configuration | success | incorrect | safe fail | Brain call share | model calls / case | p50 / p95 ms |
|---|---|---|---|---|---|---|
| C0_deterministic_only | 24/138 (0.1739, lb 0.1229) | 3 | 111 | 0.0 | 0.0 | 0.0 / 0.0 |
| C1_needle_alone | 47/138 (0.3406, lb 0.2737) | 39 | 52 | 0.0 | 0.877 | 670.8 / 955.0 |
| C2_granite_alone | 56/138 (0.4058, lb 0.3355) | 34 | 48 | 0.0 | 0.877 | 179.1 / 491.4 |
| C3_pair_selective_by_kind | 56/138 (0.4058, lb 0.3355) | 34 | 48 | 0.0 | 0.877 | 179.1 / 491.4 |
| C3o_pair_selective_by_family_ORACLE_UPPER_BOUND | 59/138 (0.4275, lb 0.3563) | 39 | 40 | 0.0 | 0.877 | 266.7 / 790.1 |
| C4_pair_sequential_needle_then_granite | 59/138 (0.4275, lb 0.3563) | 51 | 28 | 0.0 | 1.167 | 679.9 / 1338.2 |
| C4b_pair_sequential_granite_then_needle | 69/138 (0.5, lb 0.4269) | 41 | 28 | 0.0 | 1.138 | 278.8 / 1123.8 |
| C5_main_brain_alone | 109/138 (0.7899, lb 0.7247) | 17 | 12 | 1.0 | 1.0 | 907.5 / 1794.2 |
| C6_hybrid_det_selective_by_kind_then_brain | 96/138 (0.6957, lb 0.6248) | 35 | 7 | 0.3188 | 1.036 | 272.7 / 1493.1 |
| C6o_hybrid_det_selective_by_family_ORACLE_then_brain | 95/138 (0.6884, lb 0.6173) | 40 | 3 | 0.2536 | 0.971 | 285.9 / 1619.0 |
| C6b_hybrid_det_granite_then_brain | 96/138 (0.6957, lb 0.6248) | 35 | 7 | 0.3188 | 1.036 | 272.7 / 1493.1 |
| C6c_hybrid_det_needle_then_brain | 92/138 (0.6667, lb 0.5948) | 44 | 2 | 0.3261 | 1.043 | 703.1 / 2074.2 |
| C7_det_then_brain | 110/138 (0.7971, lb 0.7326) | 17 | 11 | 0.8043 | 0.804 | 742.8 / 1620.5 |
