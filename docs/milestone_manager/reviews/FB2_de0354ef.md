# Fallback review FB2 — Milestone Manager @ de0354ef16558afe26045e7c69e02f86ebaa1b1e

Basis: driver run MILESTONE-MANAGER-d3 BLOCKED NO_INDEPENDENT_REVIEWER on de0354ef (codex_cli QUOTA, claude_cli AUTH).
Reviewer: fresh isolated Claude subagent (SUBAGENT), COMPLETED_WITH_RESULT. Verdict: REJECT, BLOCKING_OPEN 4, FINDINGS_TOTAL 7.
Tests by reviewer: 352 passed. N3: rebuild 0.153 s, CLI status 0.441 s. Stress: 0 alarms. P0 import: 0 rows skipped.
Prior: all d1/d2/FB ids FIXED; R23-01..03 open LOW.

| ID | Sev | Defect |
|---|---|---|
| FB2-01 | HIGH | command-line flag credentials (--password=x, --password x) not matched |
| FB2-02 | MEDIUM | markdown keys, YAML block values, table rows, quoted keys with spaces bypassed |
| FB2-03 | MEDIUM | any upper-case underscore word containing a credential word exempt as env name |
| FB2-04 | MEDIUM | keys ending in a descriptive word (password_reset, password_hint, password_file) never checked |
| FB2-05 | LOW | Basic auth, passcode, session_key, prose, XML, homoglyphs |
| FB2-06 | LOW | 7-digit codes under token keys, value cut at ; or |, xXx.X mask, leaf key with placeholder value |
| FB2-07 | LOW | usability false positives (prose after a credential word) |

Owner decision 2026-10-22: F16 bounded to an explicit contract. Repair 4aa3d40b: FB2-01..04 and in-contract parts of
FB2-05/06 fixed; prose/XML/homoglyphs and FB2-07 documented limitations. 44 new tests fail on de0354ef.
Experiments: FB2_de0354ef_experiments/.
