# Independent audit package — Memory → Edge → Harness (M36, M37, M38)

- **Prepared:** 2026-09-28 by Claude Code (implementer of M37 and M38; independent auditor of M36 `be4451c`).
- **Requested auditor:** Codex (User, 2026-09-28). Codex implemented M36 `be4451c`, so for M36 this package asks Codex to audit only the *integration* of M36 into the chain and Claude's M36 repair commit `405db1f`, not to re-close its own M36 build (see §6).
- **Status of every milestone in scope:** PROVISIONAL / NOT FROZEN. Nothing here is closed, frozen, released or integrated. This package does not authorize repair; the auditor reports findings and the User decides.

## 1. Where the code is

| Item | Value |
|---|---|
| Repository for this batch | `https://github.com/sche004-cyber/Uri`, branch `claude/edge-harness-minimum-0oj7fe` |
| History origin | `sche004-cyber/uri-agent`, branch `m35-uri-v1-parallel-architecture` (the Uri repository was empty; the batch branch carries the full history) |
| Frozen M33.3 baseline | `291c9daa48435200c4b56857d0e3bc630016e82a` |
| M36 (Codex build) | `be4451c6fda7803a742e0ad48c7fec63140ec30b` |
| M36 repair (Claude, after Claude's closing audit returned REPAIRS_REQUIRED) | `405db1ff21f11f6927fe1b74990ff6b88a97a28d` |
| M37 Edge minimum (Claude) | `5460d64` |
| M38 Harness Execution minimum (Claude) | `3501f85` |

## 2. Dependency chain (recorded)

```
M33.3 (CLOSED_FROZEN: S1 binding, S7 events, S11 result ledger, anchors)
  └─ M36 Memory (be4451c → 405db1f)  PROVISIONAL
       ├─ used by M37: MemoryContextPackage/build_context, Recorder.outcome, Recorder.invoke_verifier,
       │               _bootstrap_verifiers, SourceRegistry, TrustedInput, negated
       └─ M37 Edge + uri_v1/execution (5460d64)  PROVISIONAL
            ├─ uses frozen S11 ResultVersionLedger.record_generated
            └─ M38 Harness (uri_v1/execution/harness)  PROVISIONAL
                 uses M37 Workspace, AcceptanceCriteria, verifier, record_and_verify, EscalationRequest (by value)
```

M38 changed two M37 files additively (`uri_v1/execution/lineage.py`: optional `uri_observations`; `uri_v1/execution/verify.py`: `FAILED` when URI recorded safety flags). No M36 or frozen file changed after `405db1f`.

## 3. Claims to verify independently (do not trust the reports)

| # | Claim | Where to look |
|---|---|---|
| C1 | No file under `uri_v1/memory`, `uri_v1/reference_clarification`, `uri_v1/turn`, `uri_v1/results`, `uri_v1/evaluation`, `uri_core`, `uri_ui`, or any M36/M33.3 test/script/fixture differs between `405db1f` and HEAD. | `git diff --stat 405db1f HEAD`; `python scripts/m33_3_r_anchors.py` |
| C2 | `uri_v1/edge` and `uri_v1/execution` never import `uri_core` or network clients. | `tests/test_m37_edge_resolution.py::test_edge_and_execution_import_boundaries`, `tests/test_m38_harness.py::test_harness_import_boundaries` |
| C3 | Only a registered URI verifier can produce `VERIFIED`; every local or harness completion is first recorded `CLAIMED_ONLY` (or `FAILED`). | `uri_v1/execution/lineage.py`, `uri_v1/execution/verify.py:make_memory_verifier`, M36 `Recorder.invoke_verifier` |
| C4 | The verifier cannot be re-pointed: it checks claim task, inputs, outputs, manifest hash, acceptance hash and the live workspace diff against the run record before running acceptance. | `verify.py` lines around `make_memory_verifier` |
| C5 | The Edge completes locally only with a digest-pinned QUALIFIED capability, and a local attempt counts as complete only on `VERIFIED`; otherwise it escalates with evidence. | `uri_v1/edge/registry.py`, `resolver.py`, `local_runner.py`; battery E10/E11 |
| C6 | Edge consumes the real M36 `MemoryContextPackage` unchanged (E-5) and clarifies on conflict, stale binding and user correction. | `tests/test_m37_edge_resolution.py::test_e5_*`; battery E16–E20 |
| C7 | The copy-in workspace never modifies originals; write-back needs a VERIFIED run, a trusted non-negated approval from the same user, and an unchanged original. | `uri_v1/execution/workspace.py`; `tests/test_m37_edge_execution.py` |
| C8 | Harness default posture is restrictive and no bypass flag can be emitted; elevation and capability grants need explicit trusted, named, non-negated user input. | `uri_v1/execution/harness/adapters.py`, `contracts.py` |
| C9 | Capability discovery is read-only and redacted; credential files are never opened. | `uri_v1/execution/harness/discovery.py`; `test_discovery_is_complete_and_redacted` |
| C10 | Granted capabilities are injected per run only (per-run `mcp.json` 0600 removed after the run; per-run plugin dir for skills; `--plugin-dir` for plugins); nothing global changes. | `adapters.py:_inject`, `runner.py` |
| C11 | Timeout, inactivity and cancel kill the whole process group and never yield success. | `process.py`, fake-harness scenarios `hang_*` |
| C12 | Harness session ids and transcripts never enter Memory. | `test_session_ids_and_transcripts_never_enter_memory` |
| C13 | Harness writes to originals or symlink escapes can never verify. | scenarios `write_original`, `symlink_escape` |

## 4. Commands to reproduce (Windows and Linux)

```
pip install -r requirements.txt pytest httpx google-api-python-client google-auth-oauthlib
python -m pytest tests/ -q                     # includes M36, frozen M33.3, governance, M37, M38
python scripts/m37_edge_qualification.py       # rewrites docs/plans/M37_QUALIFICATION_RESULTS.json
python scripts/m38_harness_qualification.py    # rewrites docs/plans/M38_QUALIFICATION_RESULTS.json
python scripts/m38_live_pilot.py 2             # optional; spends real Claude Code usage (~$0.1–0.2 per run)
python scripts/m33_3_r_anchors.py
python -m pytest test_*.py -q                  # broad legacy suite (root-level tests)
```

Before the auditor re-runs the drivers, note that they overwrite the recorded results files; compare with `git diff` afterwards.

## 5. Results recorded by the implementer (self-run, not independent)

| Check | Result |
|---|---|
| `tests/` (Linux, Python 3.11.15) | 786 passed, 1 skipped, **1 failed** (the disclosed M36 scope guard, §7.1) |
| M37 battery (20 cases × 2) | gate passed; decision accuracy 1.0; false local success 0; unsafe local on ambiguous/dynamic 0; stale/corrected/conflict not clarified 0; originals modified 0; avoidance 0.40 |
| M38 fake-harness gate (10 scenarios × 2) | gate passed; false verified 0; undetected original writes 0; unkilled processes 0; bypass flags 0; secrets in records 0; session ids in Memory 0 |
| M38 live pilot (Claude Code 2.1.283, n = 2 per arm) | both arms 2/2 verified; URI-mediated arm ≈ half the input-side tokens and ≈ half the mean reported cost; indicative only |
| Broad root suite (`test_*.py`) | 2,639 passed, 66 skipped, **15 failed**, all also failing at `405db1f` (§8) |
| Governance validator | 37 passed |
| Frozen anchors | `ok=True`, `changed=[]` |

## 6. Auditor independence

- M36 `be4451c` was built by Codex and audited by Claude (`docs/plans/M36_INDEPENDENT_CLOSING_AUDIT_REPORT.md`); Claude's repairs (`405db1f`) were re-verified by the same session and are **not** independently verified. Codex is independent of `405db1f`, M37 and M38.
- Codex should not issue the closing verdict on its own `be4451c` code. For M36, please audit `405db1f` (the repairs), and the M36 interfaces M37/M38 rely on (§2), and state that limitation in the verdict.

## 7. Known failures, limitations and open items

1. **M36 scope-guard test fails by design.** `tests/test_m36_memory_adversarial.py::test_core_adapter_import_boundaries_and_frozen_scope` asserts that every path changed since `291c9da` is an M36 path, so any successor milestone fails it. By User decision ("Leave and disclose", 2026-09-28) M36 was not edited. It passes at `405db1f`; M37's `test_m36_and_frozen_files_unchanged` performs the equivalent check against `405db1f`.
2. **Broad-suite failures.** 15 root-level tests fail on this Linux container. All 15 also fail at `405db1f` (§8), so they pre-date M37/M38. M36's own report recorded 11 failures on the User's Windows machine; the difference is environment (Linux, packages, no Tesseract, network).
3. **Same-author qualification.** Batteries, scenarios and gates for M37/M38 were written by the implementer and passed first time. Independent cases are the most valuable audit addition.
4. **Windows not exercised** for M37/M38 (locks, process groups, `taskkill`). The User's environment is Windows.
5. **No OS sandbox** for URI's own verification runs or for Claude Code; "no network" is tool-level for Claude Code.
6. **Codex adapter unexecuted** (Codex not installed here).
7. **No local model qualified** for the Edge.
8. Open design questions for the User, not decided here: whether a scratch workspace should become a temporary M36 authorized root (M36 §16.1); whether `harness_run_ref` should be added to M36 v2 now that a run record exists (M36 §16.2); when to route "needs a harness" automatically (outside frozen S6).

## 8. Broad-suite failure comparison

All 15 root-level failures at HEAD also fail when the same node IDs are run in a clean worktree at `405db1f`, so none is attributable to M37 or M38 in this environment. Node IDs, method and caveats: `docs/plans/URI_BATCH_BROAD_REGRESSION.md`. The auditor should repeat the comparison, preferably on Windows.

## 9. Exact prompt for the independent Codex audit

> You are the independent auditor for the URI v1 batch Memory → Edge → Harness. Work in the repository `sche004-cyber/Uri`, branch `claude/edge-harness-minimum-0oj7fe` (history from `sche004-cyber/uri-agent` `m35-uri-v1-parallel-architecture`). The frozen M33.3 baseline is `291c9da`. In scope: Claude's M36 repair commit `405db1f` and the M36 interfaces that later milestones use; M37 Edge minimum (`5460d64`); and M38 Harness Execution minimum (`3501f85`). You built M36 `be4451c`, so do not issue a closing verdict on your own M36 code beyond `405db1f` and those interfaces, and say so in your report. Read `docs/plans/URI_BATCH_M36_M37_M38_AUDIT_PACKAGE.md`, the M37 and M38 plans and implementation reports, `docs/plans/URI_EXTERNAL_HARNESS_VIABILITY_GATE.md`, and the rulings in `docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` §24. Treat every report, test count and Project memory entry as a claim. Independently verify claims C1–C13 from the code, and re-run `python -m pytest tests/`, both qualification drivers, the frozen-anchor script and the broad root suite, on Windows if possible. Try to break it: add your own battery cases (other openpyxl/pandas/csv access patterns, Unicode names, large or malformed workbooks), your own harness scenarios (claims that edit acceptance-relevant outputs, a harness that deletes inputs, that writes into `bundle/`, that races the verifier, that emits malformed stream-json), and any path by which a claim becomes `VERIFIED` without the URI verifier, an original changes without write-back approval, a secret reaches a record, or a bypass flag is emitted. Classify the disclosed M36 scope-guard failure and the broad-suite failures against the `405db1f` baseline. Report concrete findings with file:line and reproduction, a disposition for each claim, preserved boundaries, limitations, and a verdict per milestone: ACCEPT, ACCEPT_WITH_DOCUMENTED_LIMITATIONS, or REPAIRS_REQUIRED. Do not repair, freeze, commit, push or integrate anything; return the verdict for the User's decision.
