# Repairs after review R2 (findings in R2_findings.md)

| Finding | Action | Where |
|---|---|---|
| R1-12 leftover (`-Baked` in usage) | Repaired | `uri_ui/tool/capture/run_ember_perf_v21.ps1` |
| R2-01 panel variance understated | Repaired: cross-round comparisons declared unreliable; only within-round differences used; waiver evidence restated | FINAL sections 3, 10 and 11; Q2_RESULTS; protocol C-5 |
| R2-02 T2 worst 79 / 0.31 | Repaired to 73 / 0.29 | 07, FINAL, `expressions.json` comment |
| R2-03 live run 3 undocumented, stale file, only depleted seen live | Repaired / disclosed: run 3 section with commit and atlas hashes; stale `returning-brain_host.json` flagged; glow-only clips not seen in the full app | 06 |
| R2-04 test gaps | T0 "painted" guard added to `transparency_check.py` (re-run: ALL PASS); T4/T5 scope and the render test's frame-0 scope disclosed; missing console output of the failing baseline disclosed | `transparency_check.py`, 07 |
| R2-05 depleted haze area | B2 carries the same owner sign-off qualifier as B4 | 07 |
| R2-06 "44/44 existing" | Restated as 36 existing + 8 new | 07, FINAL |
| R2-07 two rounds after Q1 | Recorded as deviation C-5; Q1_RESULTS mentions P3 | protocol, Q1_RESULTS |
| R2-08 "made no difference" | Restated as "reviewers did not distinguish" | P3_RESULTS, protocol C-5 |
| R2-09 diag script | Reads the V2 atlas from git (`b73bd26c`), has `--out`; re-run gives the same 0.0022 | `diag_v21.py`, `diag_v21.json` |
| R2-10 housekeeping | Bundled-asset byte check committed; missing census_before noted; boundary-check wording corrected; `visualV2` condition added | perf_transparent, 05, FINAL, 07 |

Not re-reviewed after these repairs: they are wording, disclosure and tooling changes with re-run outputs. They do
not change any verdict. Formal lifecycle acceptance of the exact final commit remains BLOCKED (Claude CLI logged
out).
