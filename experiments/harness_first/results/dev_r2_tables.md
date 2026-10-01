## Configuration comparison (development corpus, n=322)

| Config | Correct | HARNESS_COMPLETE | +EDGE | +MAIN | CLARIFY | SAFE_FAILURE | False success | Bypassed S1 clarify | Underspecified executed | Wrong binding | Wrong action | Wrong extract/label accepted | Correct escalation | Main on bounded | Edge then Main | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_proxy | 262/322 (0.814) | 9 | 0 | 222 | 48 | 43 | 23 | 11 | 14 | 0 | 21 | 16 | 1.0 | 256 | 0 | 533.9 | 1199.8 |
| main_only | 253/322 (0.786) | 0 | 0 | 223 | 49 | 50 | 24 | 11 | 14 | 0 | 22 | 16 | 1.0 | 265 | 0 | 538.1 | 1208.7 |
| harness_only | 61/322 (0.189) | 38 | 0 | 0 | 25 | 259 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 | 0.9 | 1.2 |
| harness_main | 287/322 (0.891) | 38 | 0 | 191 | 55 | 38 | 11 | 0 | 5 | 0 | 11 | 16 | 1.0 | 202 | 0 | 738.2 | 1397.1 |
| harness_granite_json | 229/322 (0.711) | 38 | 159 | 55 | 45 | 25 | 53 | 0 | 11 | 0 | 55 | 32 | 0.754 | 56 | 36 | 184.5 | 1213.5 |
| harness_needle | 249/322 (0.773) | 38 | 94 | 114 | 48 | 28 | 38 | 0 | 11 | 0 | 39 | 28 | 0.912 | 113 | 102 | 839.6 | 2020.5 |
| harness_granite_json@REPLIED | 288/322 (0.894) | 38 | 1 | 190 | 55 | 38 | 10 | 0 | 5 | 0 | 10 | 16 | 1.0 | 201 | 195 | 867.4 | 1616.0 |
| harness_needle@REPLIED | 286/322 (0.888) | 38 | 1 | 191 | 55 | 37 | 11 | 0 | 5 | 0 | 11 | 16 | 0.982 | 202 | 195 | 988.7 | 2323.1 |

## Per task group: correct / n, and p50 latency ms

| Group | n | current_proxy | main_only | harness_only | harness_main | harness_granite_json | harness_needle | harness_granite_json@REPLIED | harness_needle@REPLIED |
|---|---|---|---|---|---|---|---|---|---|
| adversarial | 21 | 15 / 696.0 | 15 / 696.0 | 2 / 0.6 | 16 / 922.5 | 16 / 152.0 | 15 / 849.1 | 16 / 1018.8 | 16 / 1247.3 |
| ambiguity | 22 | 9 / 456.7 | 9 / 456.7 | 9 / 0.8 | 15 / 592.7 | 10 / 144.4 | 10 / 801.0 | 15 / 757.4 | 15 / 1433.6 |
| deterministic | 17 | 14 / 0.2 | 5 / 936.3 | 14 / 0.2 | 17 / 0.2 | 16 / 0.2 | 17 / 0.2 | 17 / 0.2 | 17 / 0.2 |
| extract | 22 | 13 / 1147.2 | 13 / 1147.2 | 0 / 0.2 | 13 / 1387.9 | 9 / 235.5 | 9 / 1212.8 | 13 / 1616.0 | 13 / 1957.9 |
| label | 30 | 28 / 409.2 | 28 / 409.2 | 0 / 0.2 | 28 / 559.2 | 15 / 63.8 | 21 / 670.2 | 28 / 622.8 | 28 / 707.1 |
| main_required | 52 | 52 / 414.4 | 52 / 414.4 | 0 / 1.0 | 52 / 763.4 | 40 / 737.3 | 47 / 875.4 | 52 / 852.1 | 51 / 878.4 |
| negation | 17 | 17 / 520.9 | 17 / 520.9 | 0 / 1.1 | 17 / 728.8 | 17 / 884.7 | 16 / 913.9 | 17 / 884.7 | 17 / 913.9 |
| reference | 32 | 21 / 740.9 | 21 / 740.9 | 9 / 1.0 | 29 / 779.2 | 28 / 199.0 | 28 / 935.6 | 29 / 957.0 | 29 / 1539.3 |
| tool_action | 45 | 39 / 616.2 | 39 / 616.2 | 0 / 1.0 | 42 / 1009.6 | 38 / 223.7 | 35 / 1000.8 | 42 / 1205.9 | 42 / 1952.5 |
| trivial | 36 | 32 / 448.6 | 32 / 448.6 | 26 / 0.2 | 36 / 0.2 | 26 / 0.2 | 36 / 0.2 | 36 / 0.2 | 36 / 0.2 |
| trivial_near_miss | 6 | 6 / 286.1 | 6 / 286.1 | 0 / 1.0 | 6 / 512.4 | 5 / 128.1 | 5 / 286.6 | 6 / 633.1 | 6 / 797.4 |
| unsupported | 22 | 16 / 302.1 | 16 / 302.1 | 1 / 0.9 | 16 / 726.0 | 9 / 192.1 | 10 / 1007.4 | 17 / 891.9 | 16 / 1545.2 |

## Edge evidence per job (only residues the harness admitted)

| Edge arm | Job | Invoked | Accepted by URI | Correct | Precision when accepted | Abstained | False success | Wrong accepted | p50 ms | p95 ms | Mean prompt chars |
|---|---|---|---|---|---|---|---|---|---|---|---|
| granite_json | EXTRACT | 32 | 27 | 12 | 0.44 | 0 | 0 | 15 | 191.5 | 299.3 | 890 |
| granite_json | LABEL | 30 | 30 | 15 | 0.50 | 0 | 0 | 15 | 63.6 | 94.2 | 465 |
| granite_json | SELECT_ACTION | 134 | 103 | 49 | 0.48 | 15 | 51 | 53 | 179.8 | 240.3 | 3154 |
| needle | EXTRACT | 32 | 15 | 5 | 0.33 | 0 | 0 | 10 | 493.3 | 673.6 | 890 |
| needle | LABEL | 30 | 10 | 3 | 0.30 | 0 | 0 | 7 | 156.8 | 317.4 | 465 |
| needle | SELECT_ACTION | 134 | 69 | 32 | 0.46 | 35 | 35 | 36 | 857.8 | 1360.4 | 3154 |

## Trivial and bounded turns: latency by configuration (ms)

| Config | Trivial p50 | Trivial p95 | Trivial max | Trivial correct | Trivial n | Deterministic p50 | Deterministic p95 |
|---|---|---|---|---|---|---|---|
| current_proxy | 448.6 | 1246.5 | 3258.217099995818 | 32 | 36 | 0.2 | 1014.4 |
| main_only | 448.6 | 1246.5 | 3258.217099995818 | 32 | 36 | 936.3 | 1141.3 |
| harness_only | 0.2 | 0.9 | 1.0621999972499907 | 26 | 36 | 0.2 | 1.0 |
| harness_main | 0.2 | 581.8 | 2223.466200004623 | 36 | 36 | 0.2 | 974.4 |
| harness_granite_json | 0.2 | 127.2 | 159.91640000720508 | 26 | 36 | 0.2 | 974.4 |
| harness_needle | 0.2 | 816.1 | 2416.033300003619 | 36 | 36 | 0.2 | 1239.2 |
| harness_granite_json@REPLIED | 0.2 | 701.5 | 2345.388300003833 | 36 | 36 | 0.2 | 996.6 |
| harness_needle@REPLIED | 0.2 | 816.1 | 2416.033300003619 | 36 | 36 | 0.2 | 1239.2 |

## Real app /ask latency (preserved app, Needle pre-route bypassed, local qwen3.5:9b)

| Turn | Runs | Median ms | Max ms | Status |
|---|---|---|---|---|
| hello | 3 | 19279 | 50011 | success |
| Hi URI | 3 | 19228 | 19395 | success |
| thanks | 3 | 18694 | 19389 | success |
| Thank you! | 3 | 18497 | 18789 | success |
| good night | 3 | 19067 | 19201 | success |
| What can you do? | 3 | 22954 | 23572 | success |
| ok | 3 | 18471 | 19354 | success |
| hey there | 3 | 18456 | 18923 | success |
| hello, how are you? | 3 | 18829 | 19346 | success |
| How much memory is this computer using right now? | 3 | 19455 | 20123 | unavailable |
| Search the web for NAAC criterion 3 guidelines. | 3 | 19830 | 19979 | unavailable |

## Reproducibility (run 1 vs run 2, same corpus)

| Config | Cases | Outcome flips | Correct in both | Correct run 2 |
|---|---|---|---|---|
| current_proxy | 322 | 1 | 262 | 262 |
| main_only | 322 | 1 | 253 | 253 |
| harness_only | 322 | 2 | 59 | 59 |
| harness_main | 322 | 2 | 285 | 285 |
| harness_granite_json | 322 | 10 | 225 | 231 |
| harness_needle | 322 | 9 | 243 | 244 |
| harness_granite_json@REPLIED | 322 | 3 | 285 | 285 |
| harness_needle@REPLIED | 322 | 3 | 284 | 285 |

## Failures of the best harness+Edge configuration

Configuration: harness_needle

| Case | Group | Expected | Class | Final | Flags | ms |
|---|---|---|---|---|---|---|
| E-SL003 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 871 |
| E-SL005 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 2015 |
| E-SL021 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 859 |
| E-SL023 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 998 |
| E-SL035 | tool_action | ACTION | HARNESS_PLUS_EDGE | HELD | wrong_action | 1998 |
| E-AR002 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1076 |
| E-AR013 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1266 |
| E-AR019 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 898 |
| E-AR020 | tool_action | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 949 |
| E-AR026 | tool_action | ACTION | SAFE_FAILURE | SAFE_FAILURE |  | 2356 |
| E-NG020 | negation | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 920 |
| E-RF002 | reference | ACTION | CLARIFY | CLARIFY |  | 2503 |
| E-RF007 | reference | ACTION | CLARIFY | CLARIFY |  | 1 |
| E-RF024 | reference | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 861 |
| E-AM001 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 826 |
| E-AM004 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 807 |
| E-AM008 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 857 |
| E-AM011 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 801 |
| E-AM012 | ambiguity | CLARIFY | HARNESS_PLUS_MAIN | EXECUTED | false_success,underspecified_executed,wrong_action | 1862 |
| E-AM018 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 797 |
| E-AM019 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 847 |
| E-AM020 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 825 |
| E-AM022 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 841 |
| E-AM026 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 840 |
| E-AM027 | ambiguity | CLARIFY | HARNESS_PLUS_EDGE | EXECUTED | false_success,underspecified_executed,wrong_action | 815 |
| E-AM029 | ambiguity | CLARIFY | SAFE_FAILURE | UNRESOLVED |  | 1583 |
| E-ES005 | main_required | ESCALATE | HARNESS_PLUS_EDGE | REPLIED |  | 840 |
| E-ES012 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 978 |
| E-ES025 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 940 |
| E-ES026 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 978 |
| E-UN001 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1022 |
| E-UN004 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 840 |
| E-UN006 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 875 |
| E-UN010 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 1007 |
| E-UN011 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 855 |
| E-UN014 | unsupported | DECLINE | HARNESS_PLUS_MAIN | EXECUTED | false_success,wrong_action | 1746 |
| E-UN018 | unsupported | DECLINE | HARNESS_PLUS_MAIN | EXECUTED | false_success,wrong_action | 1729 |
| E-UN021 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 858 |
| E-UN022 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 967 |
| E-UN030 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 858 |
| E-UN031 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 857 |
| E-UN032 | unsupported | DECLINE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 804 |
| E-IX005 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 439 |
| E-IX007 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 339 |
| E-IX009 | adversarial | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1541 |
| E-IX010 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 286 |
| E-IX011 | adversarial | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1336 |
| E-IX015 | adversarial | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 375 |
| E-EX004 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 2225 |
| E-EX005 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 674 |
| E-EX007 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 712 |
| E-EX010 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1708 |
| E-EX013 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 494 |
| E-EX014 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1958 |
| E-EX015 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 493 |
| E-EX019 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 2111 |
| E-EX020 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 583 |
| E-EX022 | extract | EXTRACT | HARNESS_PLUS_EDGE | EXTRACTED | wrong_extraction_accepted | 610 |
| E-EX025 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1630 |
| E-XE005 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1051 |
| E-XE006 | extract | EXTRACT | HARNESS_PLUS_MAIN | EXTRACTED | wrong_extraction_accepted | 1087 |
| E-SP005 | label | LABEL | HARNESS_PLUS_MAIN | LABELLED | wrong_label_accepted | 691 |
| E-SG001 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 575 |
| E-SG002 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 160 |
| E-SY004 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 147 |
| E-SY006 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 146 |
| E-SN003 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 171 |
| E-SN005 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 169 |
| E-SN006 | label | LABEL | HARNESS_PLUS_EDGE | LABELLED | wrong_label_accepted | 158 |
| E-SR001 | label | LABEL | HARNESS_PLUS_MAIN | LABELLED | wrong_label_accepted | 785 |
| TN01 | trivial_near_miss | ACTION | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 286 |
| RF10 | reference | ACTION | CLARIFY | CLARIFY |  | 0 |
| MB07 | main_required | ESCALATE | HARNESS_PLUS_EDGE | EXECUTED | false_success,wrong_action | 404 |
