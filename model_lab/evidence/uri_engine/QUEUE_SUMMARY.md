| id | group | status | attempts | start | elapsed s | rc | peak VRAM MiB | min free RAM MiB | outputs |
|---|---|---|---|---|---|---|---|---|---|
| freeze_start | safety | done | 1 | 14:07:49 | 2.2 | 0 | - | - | freeze_check_recovery_start.json |
| determinism_probe | correctness | done | 1 | 14:07:55 | 227.8 | 0 | - | - | determinism_probe.json |
| ctx_control | context_reuse | done | 1 | 14:11:48 | 484.1 | 0 | - | - | ctx_control_20261006-141151.json |
| ctx_prod | context_reuse | done | 1 | 14:19:56 | 285.5 | 0 | - | - | ctx_prod_20261006-141959.json |
| ctx_prod_split | context_reuse | done | 2 | 18:35:14 | 410.4 | 0 | 15553.2 | 9033.0 | ctx_prod_split_20261006-183518.json |
| ctx_ckpt1024 | context_reuse | done | 1 | 18:42:09 | 374.0 | 0 | 15573.4 | 9526.0 | ctx_ckpt1024_20261006-184213.json |
| ctx_cache4096 | context_reuse | done | 1 | 18:48:28 | 329.9 | 0 | 15573.4 | 7625.0 | ctx_cache4096_20261006-184831.json |
| ctx_prod_multi | context_reuse | done | 1 | 20:09:30 | 363.6 | 0 | 15754.8 | 7696.0 | ctx_prod_multi_20261006-200933.json |
| ctx_prod_multi_ms512 | context_reuse | done | 1 | 20:59:34 | 266.2 | 0 | 15752.6 | 5801.0 | ctx_prod_multi_ms512_20261006-205937.json |
| ctx_sim0_cache4096 | context_reuse | done | 1 | 20:15:38 | 280.8 | 0 | 15754.6 | 5926.0 | ctx_sim0_cache4096_20261006-201541.json |
| ctx_ux_best_split | context_reuse | done | 1 | 20:20:23 | 541.6 | 0 | 15785.9 | 5526.0 | ctx_ux_best_split_20261006-202026.json |
| ctx_ux_best2_split | context_reuse | done | 1 | 21:04:05 | 480.6 | 0 | 15152.0 | 3836.0 | ctx_ux_best2_split_20261006-210408.json |
| ctx_sb_prod | context_reuse | done | 1 | 18:54:02 | 828.9 | 0 | 15661.3 | 7983.0 | ctx_sb_prod_20261006-185406.json |
| ctx_ux_fine1024 | context_reuse | done | 1 | 19:07:55 | 839.7 | 0 | 16078.5 | 6878.0 | ctx_ux_fine1024_20261006-190759.json |
| ctx_ux_fine512 | context_reuse | done | 1 | 19:22:00 | 717.5 | 0 | 15736.2 | 7953.0 | ctx_ux_fine512_20261006-192203.json |
| determinism_probe2 | correctness | done | 1 | 19:34:02 | 474.3 | 0 | 15718.8 | 8740.0 | determinism_probe2.json |
| uri_base_16k | bench_uri | done | 1 | 19:42:00 | 184.8 | 0 | 15515.2 | 8929.0 | uri_base_16k_20261006-194205.json |
| uri_mtp3_16k | bench_uri | done | 1 | 19:45:09 | 179.5 | 0 | 15953.2 | 7461.0 | uri_mtp3_16k_20261006-194513.json |
| ue_base16k | correctness | done | 1 | 19:48:13 | 669.0 | 0 | 15566.2 | 6757.0 | summary.json |
| ue_mtp3_16k | correctness | done | 1 | 19:59:27 | 570.1 | 0 | 16176.4 | 5066.0 | summary.json |
| ue_base16k_rep | correctness | done | 1 | 20:29:29 | 620.6 | 0 | 15533.3 | 8517.0 | summary.json |
| mtp2_32k_vision | bench_spec | done | 1 | 20:39:54 | 119.3 | 0 | 15859.5 | 7241.0 | mtp2_32k_vision.json |
| mtp3_24k_vision | bench_spec | done | 1 | 20:41:57 | 117.7 | 0 | 15787.4 | 7702.0 | mtp3_24k_vision.json |
| mtp2_16k_vision | bench_spec | done | 1 | 20:43:59 | 119.3 | 0 | 15856.7 | 7814.0 | mtp2_16k_vision.json |
| mtp4_16k_vision | bench_spec | done | 1 | 20:46:03 | 119.2 | 0 | 15764.9 | 7703.0 | mtp4_16k_vision.json |
| stream_overhead | overhead | done | 1 | 20:48:06 | 96.2 | 0 | 15642.8 | 9977.0 | stream_overhead.json |
| stream_probe2 | overhead | done | 1 | 21:12:10 | 99.6 | 0 | 15635.6 | 8509.0 | stream_probe2.json |
| sb_prod_canon | bench_uri | done | 1 | 20:49:46 | 179.0 | 0 | 15736.4 | 9013.0 | sb_prod_canon_20261006-204951.json |
| ux_prod_canon | bench_uri | done | 1 | 20:52:50 | 177.1 | 0 | 15734.6 | 8925.0 | ux_prod_canon_20261006-205253.json |
| uri_ngram_simple | bench_uri | done | 1 | 20:55:51 | 173.0 | 0 | 15704.1 | 9088.0 | uri_ngram_simple_20261006-205555.json |
| uri_ngram_mod16 | bench_uri | rejected_superseded | 0 |  | - | - | - | - | identical settings to the run in progress at the crash (stock ngram-mod on a hybrid model); needs user decision |
| ux_ngram_mod8 | bench_spec | rejected_superseded | 0 |  | - | - | - | - | n-gram speculation on the hybrid model (patched rs-seq path); crash-adjacent class, needs user decision |
| freeze_end | safety | done | 1 | 20:58:48 | 2.7 | 0 | None | 11268.0 | freeze_check_recovery_end.json |
| ctx_sb2_prod | context_reuse | done | 2 | 00:15:30 | 368.5 | 0 | 15733.3 | 8086.0 | ctx_sb2_prod_20261007-001533.json |
| ctx_rel_final | context_reuse | done | 1 | 21:52:14 | 338.0 | 0 | 15754.8 | 7349.0 | ctx_rel_final_20261006-215217.json |
| ctx_sb2_final | context_reuse | done | 1 | 21:57:56 | 314.0 | 0 | 15754.8 | 7461.0 | ctx_sb2_final_20261006-215759.json |
| ctx_ux2_final | context_reuse | done | 1 | 22:03:14 | 398.5 | 0 | 15124.5 | 5974.0 | ctx_ux2_final_20261006-220318.json |
| ctx_ux2_final_ub1024 | context_reuse | done | 1 | 22:09:58 | 417.0 | 0 | 15756.1 | 6073.0 | ctx_ux2_final_ub1024_20261006-221001.json |
| ue_cand | correctness | done | 1 | 22:16:59 | 834.3 | 0 | 15758.8 | 7539.0 | summary.json |
| ue_cand_mtp2 | correctness | done | 1 | 22:30:57 | 734.7 | 0 | 15907.0 | 5601.0 | summary.json |
| ue_cand_normal | correctness | done | 1 | 22:43:16 | 349.1 | 0 | 15651.8 | 7575.0 | summary.json |
| ue_cand_mtp2_normal | correctness | done | 1 | 22:49:10 | 297.9 | 0 | 15796.7 | 6174.0 | summary.json |
| uri_cand_mtp2 | bench_uri | done | 1 | 22:54:12 | 175.4 | 0 | 15827.8 | 5949.0 | uri_cand_mtp2_20261006-225415.json |
| soak_final | stability | done | 1 | 22:57:11 | 4639.8 | 0 | 15865.5 | 4883.0 | soak_final.json |
| freeze_final_v1 | safety | done | 1 | 00:14:35 | 2.5 | 0 | None | 10255.0 | freeze_check_runtime_v1.json |
