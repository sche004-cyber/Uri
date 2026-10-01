## Configuration comparison (development corpus, n=322)

| Config | Correct | HARNESS_COMPLETE | +EDGE | +MAIN | CLARIFY | SAFE_FAILURE | False success | Bypassed S1 clarify | Underspecified executed | Wrong binding | Wrong action | Wrong extract/label accepted | Correct escalation | Main on bounded | Edge then Main | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_proxy | 262/322 (0.814) | 9 | 0 | 223 | 48 | 42 | 24 | 11 | 15 | 0 | 22 | 16 | 1.0 | 256 | 0 | 529.5 | 1215.4 |
| main_only | 253/322 (0.786) | 0 | 0 | 224 | 49 | 49 | 25 | 11 | 15 | 0 | 23 | 16 | 1.0 | 265 | 0 | 536.7 | 1224.4 |
| harness_only | 59/322 (0.183) | 38 | 0 | 0 | 23 | 261 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 | 0.8 | 1.0 |
| harness_main | 285/322 (0.885) | 38 | 0 | 193 | 53 | 38 | 13 | 1 | 7 | 0 | 13 | 16 | 1.0 | 204 | 0 | 740.5 | 1521.0 |
| harness_granite_json | 231/322 (0.717) | 38 | 156 | 59 | 43 | 26 | 53 | 1 | 13 | 0 | 55 | 30 | 0.772 | 60 | 40 | 727.3 | 1760.8 |
| harness_needle | 244/322 (0.758) | 38 | 96 | 113 | 45 | 30 | 43 | 1 | 13 | 0 | 44 | 28 | 0.877 | 114 | 100 | 793.2 | 2164.5 |

## Per task group: correct / n, and p50 latency ms

| Group | n | current_proxy | main_only | harness_only | harness_main | harness_granite_json | harness_needle |
|---|---|---|---|---|---|---|---|
| adversarial | 21 | 15 / 681.6 | 15 / 681.6 | 2 / 0.5 | 16 / 926.2 | 16 / 573.8 | 15 / 843.9 |
| ambiguity | 22 | 9 / 460.0 | 9 / 460.0 | 7 / 0.7 | 13 / 738.0 | 8 / 630.1 | 8 / 833.1 |
| deterministic | 17 | 14 / 0.2 | 5 / 909.1 | 14 / 0.2 | 17 / 0.2 | 17 / 0.2 | 17 / 0.2 |
| extract | 22 | 13 / 1165.3 | 13 / 1165.3 | 0 / 0.2 | 13 / 1521.0 | 10 / 1048.7 | 9 / 1229.4 |
| label | 30 | 28 / 408.4 | 28 / 408.4 | 0 / 0.2 | 28 / 563.5 | 16 / 244.6 | 21 / 679.8 |
| main_required | 52 | 52 / 420.0 | 52 / 420.0 | 0 / 0.9 | 52 / 773.1 | 40 / 847.2 | 45 / 852.5 |
| negation | 17 | 17 / 523.8 | 17 / 523.8 | 0 / 0.9 | 17 / 758.8 | 17 / 875.5 | 17 / 875.5 |
| reference | 32 | 21 / 749.7 | 21 / 749.7 | 9 / 0.8 | 29 / 769.8 | 29 / 808.5 | 28 / 994.4 |
| tool_action | 45 | 39 / 601.2 | 39 / 601.2 | 0 / 0.9 | 42 / 1007.1 | 39 / 909.8 | 33 / 928.1 |
| trivial | 36 | 32 / 442.5 | 32 / 442.5 | 26 / 0.2 | 36 / 0.2 | 26 / 0.2 | 36 / 0.2 |
| trivial_near_miss | 6 | 6 / 294.7 | 6 / 294.7 | 0 / 0.9 | 6 / 507.9 | 5 / 764.9 | 5 / 298.4 |
| unsupported | 22 | 16 / 289.8 | 16 / 289.8 | 1 / 0.8 | 16 / 718.9 | 8 / 722.1 | 10 / 801.0 |

## Edge evidence per job (only residues the harness admitted)

| Edge arm | Job | Invoked | Accepted by URI | Correct | Precision when accepted | Abstained | False success | Wrong accepted | p50 ms | p95 ms | Mean prompt chars |
|---|---|---|---|---|---|---|---|---|---|---|---|
| granite_json | EXTRACT | 32 | 26 | 12 | 0.46 | 0 | 0 | 14 | 599.4 | 1098.4 | 890 |
| granite_json | LABEL | 30 | 30 | 16 | 0.53 | 0 | 0 | 14 | 244.4 | 393.7 | 465 |
| granite_json | SELECT_ACTION | 135 | 101 | 49 | 0.49 | 18 | 49 | 51 | 803.1 | 1074.2 | 3152 |
| needle | EXTRACT | 32 | 15 | 5 | 0.33 | 0 | 0 | 10 | 548.4 | 760.7 | 890 |
| needle | LABEL | 30 | 10 | 3 | 0.30 | 0 | 0 | 7 | 180.6 | 396.0 | 465 |
| needle | SELECT_ACTION | 135 | 72 | 31 | 0.43 | 35 | 39 | 40 | 820.8 | 1152.5 | 3152 |

## Trivial and bounded turns: latency by configuration (ms)

| Config | Trivial p50 | Trivial p95 | Trivial max | Trivial correct | Trivial n | Deterministic p50 | Deterministic p95 |
|---|---|---|---|---|---|---|---|
| current_proxy | 442.5 | 1244.4 | 3804.480999999214 | 32 | 36 | 0.2 | 985.1 |
| main_only | 442.5 | 1244.4 | 3804.480999999214 | 32 | 36 | 909.1 | 1158.6 |
| harness_only | 0.2 | 0.8 | 1.6289999985019676 | 26 | 36 | 0.2 | 0.8 |
| harness_main | 0.2 | 580.8 | 2204.6301000009407 | 36 | 36 | 0.2 | 1004.4 |
| harness_granite_json | 0.2 | 741.9 | 819.1069000095013 | 26 | 36 | 0.2 | 1219.1 |
| harness_needle | 0.2 | 798.5 | 2393.714200006798 | 36 | 36 | 0.2 | 1219.1 |

## Failures of the best harness+Edge configuration

Configuration: harness_needle

| Case | Group | Expected | Class | Final | Flags | ms |
|---|---|---|---|---|---|---|
| E-SL003 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 758 |
| E-SL005 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1834 |
| E-SL012 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 876 |
| E-SL021 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 754 |
| E-SL023 | tool_action | ACTION | SAFE_FAILURE | SAFE_FAILURE |  | 2271 |
| E-SL035 | tool_action | ACTION | HARNESS_PLUS_EDGE | HELD | wrong_action | 1769 |
| E-AR001 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 990 |
| E-AR002 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 915 |
| E-AR013 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1091 |
| E-AR019 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 700 |
| E-AR020 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 812 |
| E-AR026 | tool_action | ACTION | SAFE_FAILURE | SAFE_FAILURE |  | 2247 |
| E-RF002 | reference | ACTION | CLARIFY | CLARIFY |  | 1051 |
| E-RF007 | reference | ACTION | CLARIFY | CLARIFY |  | 1 |
| E-RF024 | reference | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 896 |
| E-AM001 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 835 |
| E-AM004 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 816 |
| E-AM008 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 851 |
| E-AM011 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 817 |
| E-AM012 | ambiguity | CLARIFY | HARNESS_PLUS_MAIN | EXECUTED | false_success,underspecified_executed,wrong_action | 1885 |
| E-AM014 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 1017 |
| E-AM018 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 824 |
| E-AM019 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 866 |
| E-AM020 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 844 |
| E-AM021 | ambiguity | CLARIFY | HARNESS_PLUS_MAIN | EXECUTED | bypassed_clarification,false_success,underspecified_executed,wrong_action | 984 |
| E-AM022 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 905 |
| E-AM026 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 843 |
| E-AM027 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 833 |
| E-AM029 | ambiguity | CLARIFY | SAFE_FAILURE | UNRESOLVED |  | 1661 |
| E-ES005 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 785 |
| E-ES009 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 828 |
| E-ES012 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 867 |
| E-ES025 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 802 |
| E-ES026 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 763 |
| E-UN001 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 801 |
| E-UN004 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 792 |
| E-UN006 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 707 |
| E-UN010 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 995 |
| E-UN011 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 712 |
| E-UN014 | unsupported | DECLINE | HARNESS_PLUS_MAIN | EXECUTED | false_success,wrong_action | 1584 |
| E-UN018 | unsupported | DECLINE | HARNESS_PLUS_MAIN | EXECUTED | false_success,wrong_action | 1561 |
| E-UN021 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 690 |
| E-UN022 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 790 |
| E-UN030 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 705 |
| E-UN031 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 686 |
| E-UN032 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 707 |
| E-IX005 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 397 |
| E-IX007 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 350 |
| E-IX009 | adversarial | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1642 |
| E-IX010 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 322 |
| E-IX011 | adversarial | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1418 |
| E-IX015 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 418 |
| E-MS023 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 860 |
| E-EX004 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 2987 |
| E-EX005 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 657 |
| E-EX007 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 761 |
| E-EX010 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1740 |
| E-EX013 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 559 |
| E-EX014 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 2165 |
| E-EX015 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 549 |
| E-EX019 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 2356 |
| E-EX020 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 595 |
| E-EX022 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 614 |
| E-EX025 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1627 |
| E-XE005 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1034 |
| E-XE006 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1086 |
| E-SP005 | label | LABEL | HARNESS_PLUS_MAIN | LABELLED | wrong_label_accepted | 698 |
| E-SG001 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 567 |
| E-SG002 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 203 |
| E-SY004 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 156 |
| E-SY006 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 141 |
| E-SN003 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 173 |
| E-SN005 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 184 |
| E-SN006 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 221 |
| E-SR001 | label | LABEL | HARNESS_PLUS_MAIN | LABELLED | wrong_label_accepted | 794 |
| TN01 | trivial_near_miss | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 247 |
| RF10 | reference | ACTION | CLARIFY | CLARIFY |  | 0 |
| MB07 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 418 |
