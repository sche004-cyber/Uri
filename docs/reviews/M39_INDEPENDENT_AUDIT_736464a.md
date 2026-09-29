# M39 independent audit at 736464a (Claude, Codex paused)

- **Target:** `736464aa317a3832f8592a02886047c6b2fc9f66` on `claude/project-thread-wb7tmm`.
- **Base:** frozen line, freeze commit `5bbf738` (M36/M37/M38 CLOSED_FROZEN at code `bd7c450`).
- **Auditor:** Claude (same provider as the implementer), at Chetan's instruction of 2026-09-29 10:53 UTC that Claude does audit work while Codex's quota is exhausted.
- **Date:** 2026-09-29. **Environment:** Linux, Python 3.11.15, offline (no model, no network, no spend).
- **Inputs treated as claims:** the Codex report `CODEX_AUDIT_M39_736464a.md` (project files), the implementation report, internal re-audit reports, project memory, and the 1514/0 suite claim.
- **Mandate:** verify each Codex finding (confirm, downgrade or reject) from repository evidence, then audit what those findings do not cover. No repair. No frozen-file or live-app edits.
- **Status after this audit:** M39 stays PROVISIONAL, NOT FROZEN. Closing also waits on the live harness pilot.

## 0. Acceptance criteria (defined before the audit)

| ID | Criterion |
|---|---|
| AC-1 | Every file changed between `5bbf738` and `736464a` is listed and classified (M39-owned, governance doc, or frozen). |
| AC-2 | The only frozen-file change is the authorized M37 guard entry. It is M39-only, exact-name for single files, rejects `..`, is hash-pinned, and has regression tests. |
| AC-3 | The suite, qualifications, governance suite/validator, anchors and M39 dry-run benchmark are rerun here, with results recorded as observed. |
| AC-4 | Each of the four Codex findings gets a disposition backed by code or a probe. |
| AC-5 | At least one adversarial probe set covers ground Codex did not (harness behaviour against the flow, the independent frozen-scope guard, request variants). Each probe has a positive control. |
| AC-6 | Each finding has a severity, a location, a reproduction and an owner (M39 or frozen line). |
| AC-7 | What could not be verified is stated with its effect on the verdict. |

## 1. Verdict

**REPAIRS_REQUIRED.** I agree with Codex's verdict.

- **Measured against the current plan (R1.1):** M39 is incomplete (F1, confirmed). Whether R1.1 or R0 is the target is Chetan's call, which the coordinator is asking.
- **Measured against the R0 build that exists:** it is sound in its core guarantees. Binding, consent, strict grants, verification, write-back and resume all held under my probes. It still needs small M39-owned repairs: F3, the new finding N3 (both MEDIUM), and F4, N1 and N2 (all LOW).
- **Frozen line:** intact. No frozen code changed. The one frozen-file change is the authorized guard entry, which meets AC-2.

## 2. Frozen scope (AC-1, AC-2)

`git diff --name-status 5bbf738 736464a`: 95 files, 5797 insertions, 2 deletions. 91 files are added (`uri_v1/office/` 9, `fixtures/m39_office/` 68, `tests/test_m39_*` 8, `tests/m39_office_support.py`, two `scripts/m39_*`, three `docs/plans/M39_*`). Four files are modified:

| File | Nature |
|---|---|
| `tests/test_m37_edge_resolution.py` | Frozen. Authorized entry (below). |
| `docs/governance/URI_STATE.yaml` | Additive M39 record plus M37 `authorized_frozen_edits`. M36-M38 stay CLOSED_FROZEN. |
| `docs/governance/URI_ACTIVE_MILESTONE.md` | Two additive planning notes. |
| `docs/plans/URI_BATCH_M36_M37_M38_FREEZE_RECORD.md` | Additive §6 recording the authorized edit. The freeze verdict text is unchanged. |

There are no changes under `uri_v1/memory`, `uri_v1/edge`, `uri_v1/execution`, `uri_core` or `uri_ui`.

**The guard entry** (`tests/test_m37_edge_resolution.py:263-281`) adds these paths:

- prefixes `uri_v1/office/`, `fixtures/m39_office/` and `tests/test_m39_`;
- three exact-match files (`tests/m39_office_support.py`, `scripts/m39_office_benchmark.py`, `scripts/m39_generate_benchmark.py`);
- a `..` segment rejection applied to every path.

The only deleted lines are the old `allowed` continuation and `assert` that this entry replaces. The file's SHA-256 is `f288b194…6853`, which equals the pin in `tests/test_m39_boundaries.py:115`. `tests/test_m39_frozen_guard_allowlist.py` covers look-alike paths, frozen, live-app and traversal paths on a disposable clone. It passed here, because `git clone --shared` works on Linux. **AC-2 is met.**

One observation that is not a finding: the `..` rejection has no effect in practice, because git never reports a path with a `..` segment. It is harmless.

## 3. Gates rerun here (AC-3)

| Gate | Observed | Evidence |
|---|---|---|
| `pytest tests/ -q` | **1514 passed, 0 failed, 9 skipped, 130 subtests** (EXIT 0). This matches the claim on Linux. | `docs/reviews/M39_AUDIT_736464a_evidence/tests_dir.txt` |
| M36 memory qualification | 2 × 189 cases; wrong_confirmed 0; invented_ids 0; deterministic | `docs/reviews/M39_AUDIT_736464a_evidence/m36_qual.txt`, `m36q/` |
| M37 edge qualification | gate_passed; decision_accuracy 1.0; false_local_success 0 | `docs/reviews/M39_AUDIT_736464a_evidence/M37_QUALIFICATION_RESULTS.json` |
| M38 harness qualification (fake) | gate_passed; false_verified 0; unkilled 0; secrets_in_records 0 | `docs/reviews/M39_AUDIT_736464a_evidence/M38_QUALIFICATION_RESULTS.json` |
| M39 benchmark `--dry-run` | dry_run_gate PASS; 12 tasks; oracle-confirmed 5 (4 completed + 1 verified nothing-to-write); 2 no-success correctly refused; hard gates 0; tasks 05, 06, 08, 09 and 10 not measured (need a real harness, accepted gap) | `docs/reviews/M39_AUDIT_736464a_evidence/m39_bench.json` |
| Governance suite / validator | 37 passed / VALID | `docs/reviews/M39_AUDIT_736464a_evidence/governance_*.txt` |
| Anchors | ok, changed [], 8 S4 + 24 LF | `docs/reviews/M39_AUDIT_736464a_evidence/anchors.txt` |

The qualification drivers rewrite `docs/plans/M37_/M38_QUALIFICATION_RESULTS.json` in the tree. I copied those outputs to evidence and restored the tracked files, so the checkout was clean before committing.

## 4. Codex findings: dispositions (AC-4)

| Codex ID | Disposition | Basis |
|---|---|---|
| **F1 HIGH: R0 built, R1.1 measured** | **CONFIRMED** (HIGH as a scope gap; not a code defect) | See §4.1 |
| **F2 MEDIUM: old M37/M38 guard prefixes let edge/execution changes pass** | **CONFIRMED as fact, DOWNGRADED for M39 to a retained frozen-line limitation (INFO).** The M39-owned part is N1 (LOW). | See §4.2 |
| **F3 MEDIUM: escalation view says "never the network"** | **CONFIRMED, MEDIUM** | `uri_v1/office/view.py:41-43` prints "Files that will be copied to the harness (never the network)" and "no network". Plan §4.4 rule 2 (`M39_OFFICE_DEMONSTRATOR_PLAN.md:108`) says escalation "copies file contents to an external provider" and that the reply must say which files go to **which harness**. The view names neither the provider nor the harness. The posture line is true about the harness's tool network, but the first line is false for a real Claude Code run, and it appears on the consent screen. |
| **F4 MEDIUM: `/dev/null` in a test fails on Windows** | **CONFIRMED by code; DOWNGRADED to LOW** | `tests/test_m39_repair4_regressions.py:113` passes `--out /dev/null`, and `scripts/m39_office_benchmark.py:302-303` does `out_path.write_text(...)`. On Windows that resolves to `\dev\null` and raises. I could not run Windows here; Codex observed the failure there. The defect is test-only with no product effect, but it must be fixed before any Windows full-suite gate claim, since Chetan's machine is Windows. |

### 4.1 F1: which R1.1 requirements the R0 build misses

R1.1 (`docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md` §0, §4, §5) requires the items below. None exist at `736464a`:

1. **`uri_v1/office/inbox.py`:** attachment import into a per-user Office inbox as an M36 authorized root (T2, T3).
2. **`uri_v1/office/worker.py`:** background harness run with RUNNING/DONE/OUTCOME_UNKNOWN and restart handling (T5; D14).
3. **`uri_v1/office/deliver.py`:** returns verified files through FileStore with an M36 `DERIVATIVE` record (`derived_from` input hashes) and the §4.5 lineage checks (T7). R0 has approval-gated write-back to a registered folder only. `WRITEBACK_VERIFIER_ID` (`writeback.py:28`) exists, but the FileStore return path does not.
4. **Server wiring in `uri_core`:** the `/ask` Office seam (`URI_OFFICE_SEAM`), `GET /office/runs/{id}`, `POST/GET /office/folders`, and FileStore `.py`/`.xlsm` extensions (T1-T10 through the real interface).
5. **UI in `uri_ui`:** the `response.files` chip list, run polling, and Flutter tests (T2, T10).
6. **Follow-up verbs** "what did you change?" and "try again" (§4.4 rule 6; D13). They are not in `uri_v1/office/*.py`.
7. **Qualification:** B2 over HTTP (D1-D15 via `TestClient` on the real `server.py`), B3 live, B-UI on Chetan's Windows machine, and B5 with the broad root suite and `flutter test`. R0 has offline D1-D12 against `OfficeSession` only.
8. **Governance:** `INT-001` is not registered (`URI_STATE.yaml:627` `integration_events: []`), and `integration_authorized` is false.

The live-app parts (4, 5, and the INT-001 wiring) are PR-only for Chetan to apply. Project memory records that pipeline sessions do not write `server.py`, `file_store.py` or `uri_ui`. `docs/plans/M39_LIVE_APP_INTEGRATION.md` holds the prepared (not applied) design. Items 1-3, 6 and the offline half of 7 can be built inside `uri_v1/office/` without touching live-app files.

### 4.2 F2: whose finding is it

The guard prefixes `uri_v1/edge/` and `uri_v1/execution/` date from M37, when those were M37's own working directories. They are frozen as of `bd7c450`. M39's edit did not widen them. It only appended M39 paths and made the check stricter (`..`). So "the frozen M37 guard cannot prove M37/M38 integrity" is a **frozen-line limitation**, to be recorded as such, not an M39 defect.

The independent enforcement M39 is supposed to provide is `tests/test_m39_boundaries.py::test_m36_m37_m38_and_frozen_files_unchanged` (base `5bbf738`). It rejects an arbitrary edit to `uri_v1/execution/workspace.py`, which I probed. So F2's worst case, "any edit passes", does not hold for the suite as a whole. It does have its own hole, N1 below.

## 5. New findings (AC-5, AC-6)

| ID / severity | Owner | Location | Finding and reproduction |
|---|---|---|---|
| **N3 MEDIUM** | M39 | `uri_v1/office/view.py:52-56` | **The HARNESS_FAILED view says "Nothing was written to your files." even when the harness wrote the original.** Probe `write_original`: a fake harness writes the authorized `report.py` directly, which is possible because there is no OS sandbox (a retained frozen limitation). URI detects it correctly (`safety_flags = ["ORIGINAL_MODIFIED_DURING_RUN"]`, status CLAIMED_ONLY, task not completed). The rendered reply is "Safety flags: ORIGINAL_MODIFIED_DURING_RUN. / Nothing was written to your files." The original's tail shows the harness's line. The flow's detection is right but its message is false, which contradicts target item 9 ("failures are surfaced, never falsely reported"). The reply should say the original was changed during the run and by what, and the task stays open. |
| **N1 LOW** | M39 | `tests/test_m39_boundaries.py:75-90` | **The M39 frozen-scope guard tolerates rolling frozen M37/M38 files back to pre-freeze versions.** `KNOWN_UPSTREAM_REPAIRS = ("763d8e7", "b013dba")` exempts any path whose bytes equal those commits' versions. Both are ancestors of `bd7c450`, and 13 files changed after them (`docs/reviews/M39_AUDIT_736464a_evidence/probe_guard_revert.txt`). Probe: in a disposable clone, restoring `uri_v1/execution/{workspace,verify}.py`, `edge/resolver.py` (at 763d8e7) or `execution/harness/{runner,contracts}.py` (at b013dba) makes **both** frozen-scope guards PASS. The rest of the suite still caught every rollback I tried (8 of 8, 1 to 18 failures each; `docs/reviews/M39_AUDIT_736464a_evidence/revert_suite_summary.txt`), so nothing is exposed today. But neither guard proves the frozen line intact, which is exactly the property F2 is about. Since `BASELINE` is now `5bbf738`, the exemption is obsolete: removing it closes N1 without touching frozen files. |
| **N2 LOW** | M39 (docs) | `docs/governance/URI_STATE.yaml` M39 entry (~262-290) | **The M39 governance record is stale in ways that misstate its status.** `implementation_authorized: false` and `closing_audit: "REQUIRED_NOT_PERFORMED (implementer self-qualification only)"` predate several audits. `implementation_baseline: 7363ba5` and `depends_on_unaudited` (M36 405db1f …) are wrong now that M39 sits on the frozen line. `blocked_by_audits` lists M36/M37/M38 findings closed by the freeze. `decision_two_filename_requests_2026_09_29` still says "R2-6 remains open" (resolved at ba0db5e, and recorded under M37's `authorized_frozen_edits`). The validator passes because these are free-text fields. It needs an additive correction entry, not an overwrite, per the evidence-integrity rules. |

Probes that found **no defect** (each with a passing positive control, `honest_control`, which reached AWAITING_APPROVAL then COMPLETED):

| Probe | Harness behaviour | Result |
|---|---|---|
| tamper_workbook | Edits the user's workbook header instead of fixing the script | HARNESS_FAILED/FAILED; originals unchanged |
| extra_file | Honest fix plus a new `evil.py` | FAILED (`only_changed`); nothing written |
| hardcode | Replaces the script with one writing a constant Summary | FAILED |
| hardcode2 | Keeps the input read, sets `total = 999999` | FAILED via the frozen verifier's `differential_rerun` on a perturbed `sales.xlsx`. So the "numbers not proven" caveat is narrower than the view text implies, which is good. |
| symlink_out | Replaces `report.py` with a symlink to a file outside the workspace | FAILED; original not a symlink; outside content not imported |
| claim_verified_text | Result text claims "VERIFIED by URI" and changes nothing | FAILED |

Request-variant probes (`docs/reviews/M39_AUDIT_736464a_evidence/probes/case_probe_results.txt`):

- Upper-case names bind the real lower-case files, which matches Windows semantics.
- Trailing and leading spaces in answers are tolerated.
- Swapped-role answers are refused and re-asked, with no wrong binding.
- Full-width `ｒｅｐｏｒｔ.py` does not bind and ends in a Memory clarification, which is safe.
- An answer naming a different existing script (`report_old.py`) than the request named binds the answered file. That is the user's explicit per-file choice, so it is noted and is not a defect.

## 6. Not verified here, and effect on the verdict (AC-7)

- **Windows behaviour** (F4, the `clone --shared` setup errors Codex saw, the junction probe): I had no Windows host. F4 is confirmed by code reading only. This does not change the verdict.
- **Live harness** (real Claude Code): not run, because of the no-spend rule and because it needs Chetan's device. F3's "provider receives file content" is inferred from the plan and from how Claude Code works, not observed. The disposition stands either way, because the text is wrong on its face for any external model.
- **R1.1 items** (HTTP seam, UI, B2/B3/B-UI): they do not exist, so they cannot be verified. This is F1.
- **Same-provider audit:** the implementer and I are both Claude. Codex's independent run covers the areas it reported, and I re-verified its findings rather than inheriting them.

## 7. Self-review against the criteria

- AC-1 and AC-2 are met in §2.
- AC-3 is met in §3, with raw outputs in `docs/reviews/M39_AUDIT_736464a_evidence/`.
- AC-4 is met in §4: all four findings have dispositions, and F4's Windows reproduction is marked as Codex-observed.
- AC-5 is met in §5, with a positive control.
- AC-6 is met: each finding has an owner and a reproduction.
- AC-7 is met in §6.
- Checked for contradictions: F2 is downgraded for M39, but N1 is kept as M39's own, because the independent guard M39 relies on is M39-owned and fixable without frozen edits. That is consistent with the brief's rule against frozen edits.
- One earlier probe result was corrected before this report was written. My first harness probe run had every scenario FAILED, including the honest control, because the harness env allowlist stripped my `URI_PROBE` variable. After renaming it to the allowlisted `URI_PROBE_MODE` prefix, the control passed and the results above are from that rerun. The first run's output was discarded as invalid, not counted as evidence.

## 8. Recommended repair scope (for a repair lane; not done here)

1. **F3:** the escalation view names the harness and states that file contents go to its provider.
2. **N3:** the HARNESS_FAILED view reflects `ORIGINAL_MODIFIED_DURING_RUN` (and any other safety flag) instead of "Nothing was written".
3. **F4:** use `tmp_path` instead of `/dev/null`.
4. **N1:** drop `KNOWN_UPSTREAM_REPAIRS`, now that the baseline is `5bbf738`.
5. **N2:** add an additive correction to the M39 governance record, and record F2 as a retained frozen-line limitation (docs only).
6. **F1:** waits on Chetan's R0 vs R1.1 decision. The live-app parts stay PR-only for Chetan.
