# M39 independent focused re-check: `a303ec5` + `e9c891f`

- **Verdict: ACCEPT** for R0 at `e9c891f`. No repair is required in M39 code or docs. Three LOW findings (L-1 to L-3) are runbook or follow-up items, and L-1 should be handled before the live run on the User's PC.
- **M39 state is unchanged by this re-check:** `M39_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. This re-check is one of the gates in plan §14.4. The Windows suite (Q-O6) and the live Claude Code smoke run (Q-O3) are still **NOT RUN**, so M39 is not closed.
- **Scope:** audit only, no repairs. Branch `claude/project-thread-wb7tmm`, range `0d690ea..e9c891f`. Baseline `5bbf738` (M36-M38 freeze commit, code `bd7c450`). The last independently accepted commit was `0d690ea` (`docs/reviews/M39_REAUDIT_0d690ea.md` on `claude/project-thread-p9ox5q`).
- **Auditor:** Claude Code, 2026-10-01. I did not write `a303ec5` or `e9c891f`. Same-provider review: the implementer is also a Claude session.
- **Environment:** Linux, Python 3.11.15, git 2.43.0. Windows/Python 3.13 was **not** exercised (see §5).
- **Evidence:** `/mnt/project-files/audits/m39_recheck_e9c891f/`.

## 1. Acceptance criteria (set before inspection)

| # | Criterion |
|---|---|
| AC-1 | `0d690ea..e9c891f` changes no file frozen at `5bbf738` and no live-app file (`uri_core/`, `uri_ui/`, root `uri_ui.py`). Every path changed since `5bbf738` is an M39 path or the hash-pinned authorized edit. |
| AC-2 | R5-1 is fixed. No rendered reply says "Nothing was written" or otherwise claims more than URI itself knows. The regression fails on the `0d690ea` view and passes on `e9c891f`. |
| AC-3 | The CRLF (D9) fix doesn't weaken the guard. The new pin covers exactly the previously authorized content. Tampering is detected in both LF and CRLF checkouts. |
| AC-4 | The live smoke test is skipped by default, cannot touch the User's files, and refuses to run on API-key billing. |
| AC-5 | The docs record Chetan's 2026-10-01 08:05 decision accurately: M39 is judged against R0 (CLI Office demonstrator plus the Office capability), and real-app wiring belongs to the Harness-first track. The Windows regression and live Claude Code runs are recorded as NOT RUN, never as passed. M39 is not marked closed. The edits are additive only. |
| AC-6 | I reproduce: suite 1531 passed / 0 failed / 10 skipped, governance VALID, anchors ok, and the M36/M37/M38 qualifications. |
| AC-7 | I note, without fixing, what integrating the M37-L3 fix (`9395677`) into M39 will need. |

## 2. Results against criteria

| # | Result | Evidence |
|---|---|---|
| AC-1 | **Met.** `0d690ea..e9c891f` touches 10 files: `uri_v1/office/view.py`, 4 `tests/test_m39_*` files, `fixtures/m39_office/evil_claude_office.py`, and 4 governance/plan docs. Since `5bbf738`, everything outside `uri_v1/office/`, `tests/test_m39_*`, `tests/m39_office_support.py`, `scripts/m39_*`, `fixtures/m39_office/` and `docs/` is just `tests/test_m37_edge_resolution.py`. That file is the authorized edit and was last changed at `736464a`. No `uri_core/`, `uri_ui/` or `uri_ui.py` changes. Both `5bbf738` and `0d690ea` are ancestors of `e9c891f`. | `diff_scope.txt` |
| AC-2 | **Met.** All three former "Nothing was written" replies (CANCELLED, WRITEBACK_REFUSED, HARNESS_FAILED with no flags) now say "URI wrote nothing back to your files" (`uri_v1/office/view.py:35,84-87,109`). No remaining string in `uri_v1/office/` makes the claim. With `0d690ea`'s `view.py` restored, 3 of the 6 R5-1/N3 render tests fail, including the `write_sibling` probe (harness writes a new file into the user folder, no flag). On `e9c891f` all 6 pass. | `r5_1_against_0d690ea_view.txt`, `r5_1_against_e9c891f.txt` |
| AC-3 | **Met.** The new pin `e54c180…` is the git blob of the file at `736464a`/`0d690ea`. It is the same content the old sha256 `f288b194…` pinned, so the authorized scope did not widen. All 15 of my tamper probes on disposable clones were detected in both LF (`autocrlf=false`) and CRLF (`autocrlf=true`, files forced to CRLF): an appended line, the allowlist widened from `uri_v1/office/` to `uri_v1/`, the pre-tightening `ba0db5e` version, the file deleted, a one-character edit to frozen `uri_v1/execution/workspace.py`, a rollback of that file to `763d8e7`, and an untracked file under `uri_v1/execution/`. A CRLF-only change in an LF checkout also fails, which is fail-closed. Clean clones pass in both modes. Under global `core.autocrlf=true`, `tests/test_m39_repair5_regressions.py` fails 6 cases at `0d690ea` and passes at `e9c891f`, which reproduces D9 and confirms the fix. | `crlf_guard_probes.txt`, `global_autocrlf_true_*.txt` |
| AC-4 | **Partly met; see L-1.** The test is skipped unless `URI_M39_LIVE_SMOKE=1` exactly (`true` also skips). It fails with "REFUSED" if `ANTHROPIC_API_KEY` is set, if no `.credentials.json` is present (`auth_mode` `unknown`), or if the executable is missing. All fixtures live under pytest's `tmp_path` (`OfficeEnv.root = tmp/authorized`), and the repo was unchanged after the probe runs. With a fake `claude` on PATH, an honest run gives `AWAITING_APPROVAL → COMPLETED` (verifier `STRUCTURALLY_VERIFIED`, originals unchanged before approval), and false-claim and default runs give `HARNESS_FAILED` (verifier `FAILED`). That reproduces the implementer's claim. `harness_env` forwards only `CLAUDE_CODE_OAUTH_TOKEN`; it strips `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK/VERTEX` and `AWS_*`. The gap: "subscription" is inferred only from the existence of `~/.claude/.credentials.json`. | `live_smoke_probes.txt` |
| AC-5 | **Met.** The §14.1 quote matches Chetan's message of 2026-10-01 08:05 UTC verbatim, which I read from the project. Plan §14.2/§14.3 define M39 as `uri_v1/office` plus the CLI, with `OfficeSession` as the Office capability, and assign the `/ask` seam, endpoints, FileStore, UI and INT-001 to Harness-first. Q-O6 and Q-O3 are "NOT RUN" in plan §14.4, implementation report §14, `URI_STATE.yaml` `r0_closing_state_2026_10_01` ("Neither may be recorded as passed until it has run on the User's PC") and `URI_ACTIVE_MILESTONE.md` ("Not closed, not frozen"). The status stays `M39_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. No doc anywhere marks M39 closed or either gate passed. All four doc diffs are additions only. Q-O4 (VG-1 benchmark) is declared not a closing gate. That matches the comparison Chetan approved from (`decisions/M39_SCOPE_R0_vs_R1_1.md`: "benchmark stays post-close"). | `docs_checks.txt` |
| AC-6 | **Met (Linux).** `tests/`: **1531 passed, 0 failed, 10 skipped**. The skips are 9 Windows-only tests plus the live smoke test. Governance validator VALID, `tests/governance` 37 passed, anchors `{'ok': True, 'changed': []}`. M36 qualification: wrong_confirmed 0, invented_ids 0, deterministic. M37 `gate_passed: true`. M38 `gate_passed: true`, bypass flags 0. M37 and M38 output is identical to the `0d690ea` re-audit apart from latency; M36 differs only in latency and machine string. | `full_suite.txt`, `governance_*.txt`, `anchors.txt`, `m3*_qualification.txt` |
| AC-7 | **Noted.** See §4. | `m37_l3_merge_probe.txt` |

## 3. Findings

No CRITICAL, HIGH or MEDIUM findings.

**L-1 (LOW, spend policy). The live smoke test's "subscription only" check can't see an API key stored in Claude Code's own config.**
- `auth_mode` comes from frozen M38 discovery (`uri_v1/execution/harness/discovery.py:167`). It returns `subscription` whenever `~/.claude/.credentials.json` exists and `ANTHROPIC_API_KEY` is unset.
- Probe: a home with both `.credentials.json` and a `~/.claude.json` holding `primaryApiKey` (as a Console/API-key login leaves) is reported as `subscription`, and the test proceeds.
- I have **not** verified whether real Claude Code would bill that stored key over the subscription login in `-p` mode. That is inferred risk, not observed.
- Exposure is bounded by the opt-in, by the User running it themselves, and by `--max-budget-usd 1.0`.
- **Before Run 2:** the User confirms in Claude Code (`/status`) that the session is on the subscription and not an API key.
- **Small M39-only follow-up:** have the test read the run's stream-json `system/init` event, record its `apiKeySource` in the evidence JSON, and fail unless it shows no API key. This needs no frozen change.
- Not blocking for R0 acceptance; it must be settled before Q-O3 counts as evidence under the spend policy.

**L-2 (LOW, runbook). A fully CRLF checkout fails 7 frozen-line checks, so the runbook's "expect 1531 passed" holds only for an LF checkout.**
- A fresh clone made with `core.autocrlf=true` (the Git for Windows default) gives 1524 passed / 7 failed.
- The 7 failures: `test_m33_3_s3_battery` (1), `test_m33_3_s4_replay` (2), `test_m36_memory_adversarial` (1), `test_m36_memory_qualification` (1), the frozen M37 guard, and `test_m39_boundaries::test_frozen_anchors_unchanged`.
- All 7 come from frozen M33.3 anchor and M36 tooling hashing raw bytes. None is an M39 defect, and D9 was correctly scoped to M39's own pin and probe clones.
- The readiness audit saw only the 5 D9 failures, which implies the User's checkout is LF. That is not verified.
- The runbook says "Use a fresh worktree or clone". **Recommendation:** make it `git clone -c core.autocrlf=false https://github.com/sche004-cyber/Uri`, or a worktree of an LF checkout.

**L-3 (LOW, docs accuracy). Three small statements are inaccurate.**
1. `tests/test_m39_repair5_regressions.py` (D9 test) says "Linux git leaves LF even with autocrlf=true". Git 2.43 on Linux does check out CRLF. The test forces CRLF anyway, so its result is unaffected.
2. The runbook says the live run "touches only the generated temporary folder". URI's own steps do, and the harness's file tools are scoped to the workspace with no shell. But there is no OS sandbox (accepted S-L1/M38-L2, stated two lines earlier), so "is limited to" would be accurate.
3. `URI_STATE.yaml` M37 `authorized_frozen_edits` still says "Pinned by content hash". That is still true in substance (a git blob id), but the field doesn't mention the change from raw-byte sha256 to blob id. Additive note optional.

**Informational (no action for R0).**
- The NOTHING_TO_WRITE and AWAITING_APPROVAL replies cannot detect a harness writing outside the workspace. NOTHING_TO_WRITE's wording ("changed nothing that needs writing back") is scoped accordingly. This is the same accepted no-sandbox limitation.
- The blob-id pin trusts git's own conversion (attributes/filters), as does the `git diff` guard beside it. A root `.gitattributes` sits outside the guard's scanned directories, but exploiting a filter needs local `.git/config`, which a committed change cannot supply.

## 4. M37-L3 integration note (not fixed here)

- `9395677` (on `claude/project-thread-hrkr7o`, under its own re-audit) changes `tests/test_m37_edge_resolution.py` to blob `a73ddac9…`, so M39's pin `e54c180…` has to become the blob of the merged file.
- A trial merge of `9395677` into `e9c891f` **conflicts** in `tests/test_m37_edge_resolution.py`, `docs/governance/URI_STATE.yaml` and `docs/plans/URI_BATCH_M36_M37_M38_FREEZE_RECORD.md`. I aborted it.
- The prepared `/mnt/project-files/audits/m37_l3_fix/M39_INTEGRATION_0d690ea_plus_9395677.patch` targets `0d690ea`, which used the old sha256 pin form. It needs regenerating against `e9c891f`'s blob-id pin.
- `9395677` pins its own guard with a CRLF-normalized sha256, while M39 uses a git blob id. Both are line-ending-safe, but picking one convention at merge time would be simpler.

## 5. Not verified, and whether it affects the verdict

- **Windows/Python 3.13 suite (Q-O6):** not run here. It does not affect this re-check's verdict, but it is a mandatory M39 closing gate. L-2 affects how to run it.
- **Live Claude Code run (Q-O3):** not run, because this environment has no subscription-authenticated Claude Code and the spend policy forbids metered runs. It does not affect this verdict, but it is a mandatory closing gate. L-1 should be settled first.
- **The readiness audit's original D9 output:** not available here (it is on the User's PC). I reproduced the failure mode independently (6 failures at `0d690ea` under global `autocrlf=true`, 0 at `e9c891f`).

## 6. Self-review

- **First draft rated L-1 as "AC-4 met".** The coordinator asked me to check that the test "can't run on API-key billing", and the `primaryApiKey` probe shows that is only true for environment-variable keys. I re-rated AC-4 as partly met and left the billing question explicitly unverified.
- **First draft attributed the 7 CRLF failures to M39.** Each one traces to frozen M33.3/M36 code hashing raw bytes, so I corrected that.
- **Checked the Q-O4 removal for scope creep.** It traces to the scope comparison the User approved from, so it is not a finding.
- **Every count above is my own run on `e9c891f`** (`git rev-parse HEAD` in `head.txt`), not the implementer's report.
