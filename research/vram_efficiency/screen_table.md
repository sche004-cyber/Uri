| run | valid | extra args | requested device / host-visible MiB (llama.cpp log, peak) | local / non-local MiB (end) | load s | decode tok/s p50 | MTP accept | decision s p50 | prefill tok/s 1k / 8k / 30k | TTFT 30k s | vision s p50 | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vS_base | yes | `(frozen)` | 15698 / 900 | 15689 / 1149 | 18.25 | 117.66 | 0.6 | 1.35 | 2124 / 2302 / 1807 | 17.1651 | 1.84 | 0 |
| vS_draftexp | yes | `-otd blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU` | 15370 / 1403 | 15287 / 1721 | 9.17 | 97.53 | 0.61 | 1.72 | 2001 / 1828 / 1436 | 21.5619 | 0.86 | 0 |
| vS_draftexpout | yes | `-otd blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU,output\.weight=CPU` | 14971 / 1802 | 15211 / 1802 | 9.81 | 48.76 | 0.613 | 2.58 | 1808 / 2116 / 1669 | 18.5605 | 1.01 | 0 |
| vS_kvq4_draftexp | yes | `-otd blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU -ctk q4_0 -ctv q4_0` | 15145 / 1403 | 15388 / 1399 | 10.53 | 98.72 | 0.624 | 1.57 | 1398 / 2080 / 1582 | 19.5853 | 0.86 | 0 |
| vS_ncmoe1_draftexp | yes | `-otd blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU --n-cpu-moe 1` | 15165 / 1669 | 15393 / 1674 | 9.0 | 74.57 | 0.622 | 1.86 | 1771 / 2000 / 1612 | 19.2212 | 0.98 | 0 |
| vS_visioncpu_draftexp | yes | `-otd blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU --no-mmproj-offload` | 14264 / 1403 | 14498 / 1399 | 9.86 | 98.93 | 0.61 | 1.57 | 1896 / 2120 / 1676 | 18.5165 | 4.94 | 0 |
