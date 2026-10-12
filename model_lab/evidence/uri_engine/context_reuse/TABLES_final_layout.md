| run | layout | extra flags | binary | load s | peak VRAM MiB | peak RSS MiB | min free RAM MiB | A_fresh prefill tok/s (30k) |
|---|---|---|---|---|---|---|---|---|
| ctx_rel_final | final | `-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16` | release | 84.94 | 15754.8 | 3296.5 | 7396.9 | 1830 |
| ctx_sb2_final | final | `-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16` | stock self-built (SDK glslc) | 84.45 | 15754.8 | 3325.1 | 7497.9 | 1822 |
| ctx_ux2_final | final | `-b 2048 -ub 2048 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 16` | patched self-built (SDK glslc) | 86.83 | 15124.5 | 4467.0 | 6082.3 | 1784 |
| ctx_ux2_final_ub1024 | final | `-b 1024 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 32` | patched self-built (SDK glslc) | 83.61 | 15768.1 | 4088.6 | 6106.7 | 1753 |

Cells: prompt_n recomputed / excess over the logical change / TTFT s (median of the two sequences per size).

| size : scenario | logical new | ctx_rel_final | ctx_sb2_final | ctx_ux2_final | ctx_ux2_final_ub1024 |
|---|---|---|---|---|---|
| 4k : A_fresh | 0 | 2541 / 2541 / 1.59 | 2541 / 2541 / 1.80 | 2541 / 2541 / 2.33 | 2541 / 2541 / 1.63 |
| 4k : B_repeat | 0 | 4 / 4 / 0.45 | 4 / 4 / 0.42 | 4 / 4 / 0.46 | 4 / 4 / 0.50 |
| 4k : C_new_turn | 26 | 49 / 23 / 0.40 | 49 / 23 / 0.41 | 49 / 23 / 0.42 | 49 / 23 / 0.50 |
| 4k : A_reprime | 0 | 4 / 4 / 0.49 | 4 / 4 / 0.45 | 4 / 4 / 0.50 | 4 / 4 / 0.51 |
| 4k : D_evidence_changed | 127 | 367 / 240 / 0.69 | 367 / 240 / 0.69 | 367 / 240 / 0.71 | 367 / 240 / 0.67 |
| 4k : A_reprime2 | 0 | 4 / 4 / 0.46 | 4 / 4 / 0.45 | 4 / 4 / 0.49 | 4 / 4 / 0.50 |
| 4k : E_permission_changed | 664 | 1047 / 383 / 1.11 | 1047 / 383 / 1.12 | 2067 / 1403 / 1.53 | 1043 / 379 / 1.19 |
| 4k : A_after_E | 0 | 4 / 4 / 0.44 | 4 / 4 / 0.45 | 4 / 4 / 0.48 | 4 / 4 / 0.53 |
| 16k : A_fresh | 0 | 11944 / 11944 / 6.28 | 11944 / 11944 / 6.31 | 11944 / 11944 / 6.28 | 12179 / 12179 / 6.66 |
| 16k : B_repeat | 0 | 4 / 4 / 0.52 | 4 / 4 / 0.50 | 4 / 4 / 0.55 | 4 / 4 / 0.57 |
| 16k : C_new_turn | 26 | 49 / 23 / 0.43 | 49 / 23 / 0.43 | 49 / 23 / 0.50 | 49 / 23 / 0.43 |
| 16k : A_reprime | 0 | 4 / 4 / 0.56 | 4 / 4 / 0.53 | 4 / 4 / 0.58 | 52 / 52 / 0.73 |
| 16k : D_evidence_changed | 3229 | 3398 / 169 / 2.32 | 3398 / 169 / 2.35 | 3902 / 673 / 2.62 | 3418 / 189 / 2.54 |
| 16k : A_reprime2 | 0 | 4 / 4 / 0.55 | 4 / 4 / 0.54 | 4 / 4 / 0.59 | 3444 / 3444 / 2.58 |
| 16k : E_permission_changed | 12035 | 12418 / 383 / 6.45 | 12418 / 383 / 6.49 | 13438 / 1403 / 6.96 | 12414 / 379 / 6.82 |
| 16k : A_after_E | 0 | 4 / 4 / 0.52 | 4 / 4 / 0.52 | 4 / 4 / 0.58 | 12414 / 12414 / 6.85 |
| 30k : A_fresh | 0 | 25821 / 25821 / 14.54 | 25821 / 25821 / 14.60 | 25837 / 25837 / 14.97 | 26291 / 26291 / 15.40 |
| 30k : B_repeat | 0 | 4 / 4 / 0.52 | 4 / 4 / 0.54 | 4 / 4 / 0.64 | 4 / 4 / 0.37 |
| 30k : C_new_turn | 26 | 49 / 23 / 0.44 | 49 / 23 / 0.45 | 49 / 23 / 0.46 | 49 / 23 / 0.46 |
| 30k : A_reprime | 0 | 4 / 4 / 0.62 | 4 / 4 / 0.62 | 52 / 52 / 0.74 | 52 / 52 / 0.45 |
| 30k : D_evidence_changed | 6633 | 6965 / 332 / 5.01 | 6965 / 332 / 5.04 | 7720 / 1087 / 5.68 | 6965 / 332 / 5.00 |
| 30k : A_reprime2 | 0 | 4 / 4 / 0.62 | 4 / 4 / 0.63 | 7722 / 7722 / 5.72 | 6967 / 6967 / 5.02 |
| 30k : E_permission_changed | 25912 | 26295 / 383 / 14.79 | 26295 / 383 / 14.83 | 27902 / 1990 / 15.90 | 26291 / 379 / 15.24 |
| 30k : A_after_E | 0 | 4 / 4 / 0.62 | 4 / 4 / 0.61 | 27902 / 27902 / 15.94 | 26291 / 26291 / 15.25 |
