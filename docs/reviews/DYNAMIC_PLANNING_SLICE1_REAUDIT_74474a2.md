# Dynamic planning slice 1: independent re-audit of the F2 fix at `74474a2`

- **Subject:** `74474a2` on `claude/dynamic-planning-slice1-2eemmh` ("bind each adapter to its qualified implementation and fail closed (audit F2)"), on `e69df0c` / `458cbda`.
- **Auditor:** Claude, fresh thread, independent of the implementation thread and of the non-authoritative draft `14a0427` (not examined, not relied on).
- **Scope:** audit only. No slice file was changed. A throwaway prototype (§5) was applied to a scratch tree and reverted; it is evidence that a repair is small, not a repair.
- **Date:** 2026-09-30. Linux, Python 3.11.15. Windows not run.
- **Evidence:** `docs/reviews/dynamic_planning_f2_reaudit/` (probe script as `probes.py.txt`, raw outputs).

## Verdict: **REPAIRS_REQUIRED**

The demonstrated F2 path (a different callable placed under a trusted `(action_id, version)`) is closed, and every test class Chetan asked for exists and passes. But a swapped adapter built from the genuine code object with its own globals passes attestation and reaches **VERIFIED** while writing outside the workspace (F2R-1). That is still "an unqualified/swapped adapter reaching VERIFIED" through the same injection point F2 used, and it contradicts the report's claim (§6.14, §9) that a swapped adapter "cannot run or reach VERIFIED". A three-check repair confined to `attestation.py` closes it (§5). Two further bypasses (F2R-2, F2R-3) need a fix or an explicit, accurate residual entry.

## 1. Acceptance criteria (defined before inspection, from Chetan 2026-09-29 13:49)

| # | Criterion |
|---|---|
| AC1 | Qualification is bound to a stable adapter identity and an implementation integrity value (SHA-256). |
| AC2 | The runtime fails closed when the adapter differs: an unqualified or swapped adapter cannot keep trusted status or reach VERIFIED. |
| AC3 | The declared capability/workspace boundary is bound in the same record, or a reason is given why not, without widening the slice. |
| AC4 | Adversarial tests exist and pass for: same ID/different code, changed hash, missing record, malformed record, valid unchanged adapter. |
| AC5 | Audit, slice qualification and full regression rerun; only the accepted frozen-guard failure (report §4.1) on slice paths. |
| AC6 | Outside-workspace write prevention that needs containment is recorded as a separate, narrower residual, accurately. |
| AC7 | No frozen file changed (M36-M38 at `bd7c450` / `5bbf738`); `verify.py` untouched. |
| AC8 | No large plugin-security framework. |

## 2. Results against the criteria

| # | Result | Evidence |
|---|---|---|
| AC1 | **Met.** Record schema v2 carries `adapter {module, qualname, implementation_sha256}` per capability; the record digest `a91af8bb…` is pinned in `actions.py`. A fresh interpreter recomputes all four digests equal to the record (probe P13). | `fixtures/dynamic_planning/capability_qualification.json`, `attestation.py`, `probe_results.txt` |
| AC2 | **Not met.** The dict swap, name spoofing, `__code__` swap, patched uri_v1 helper, patched constant, shadowed builtin in module globals, replaced class and non-function callables are refused before the node runs. But crafted function objects with the genuine code (P1, P2) and a replaced module global (P3) attest and reach VERIFIED with an outside write. See F2R-1, F2R-2. | `probe_results.txt` |
| AC3 | **Met.** `boundary {effect, verifier_coverage, workspace_writes}` is in the record and compared with the contract before every node. Cross-wiring one qualified adapter under another action is refused (P6, `BOUNDARY_MISMATCH`, because verifier coverage is unique per action), as is a writer downgraded to READ_ONLY in the record (P10). In-workspace enforcement stays with the verifier's `only_changed` check, which is correct for this slice. | P6, P10; `attestation.py` `_refusal` |
| AC4 | **Met.** `tests/test_dynamic_planning_attestation.py` has 21 tests covering all five classes; they pass. They do not cover the F2R-1/2/3 shapes. | 137/137 slice tests |
| AC5 | **Met.** Full suite **1439 passed, 1 failed, 9 skipped**; the one failure is `test_m36_and_frozen_files_unchanged`, and I recomputed its 18 offending paths: all are `tests/test_dynamic_planning_*`, `scripts/dynamic_planning_*` or `fixtures/dynamic_planning/`. Slice qualification exit 0, 34/34, six counters 0, C33 semantic miss 1/1, gate passed; the rewritten result file differs from the committed one only in latency values. C26-C29 tamper cases still end `FAILED` at the verifier, so moving the driver from wrapped adapters to `sys.setprofile` kept those cases live. Review set 113 passed; anchors ok, changed []; governance 37 passed, VALID; M36/M37/M38 qualification exit 0 each (their rewritten result files reverted). | `full_suite_summary.txt`, `guard_offenders.txt`, `dp_qualification.txt`, `review.txt`, `anchors.txt`, `governance.txt`, `m36_m38_qualification.txt` |
| AC6 | **Partly met.** §6.16 correctly records that a qualified adapter's own outside writes need containment and that process-wide builtin/stdlib patching is out of scope (confirmed by P5). It does not record F2R-3 (patched methods of uri_v1 classes, including frozen `officefile`), and §6.14/§9 overclaim (F2R-4). | report §6.14, §6.16, §9 |
| AC7 | **Met.** `git diff --name-status 5bbf738 74474a2` is 38 additions and no modifications or deletions; `uri_v1/execution/verify.py` is identical. Since `458cbda`, only slice files changed. | commands in §6 |
| AC8 | **Met.** One 200-line module and a runner hook; no framework. | `attestation.py` |

## 3. Findings (most severe first)

### F2R-1 (HIGH): a swapped adapter built from the genuine code object passes attestation and reaches VERIFIED

`attestation.py` identifies a function by `__module__`/`__qualname__` and hashes its source, the code of the uri_v1 functions it reaches, and a fingerprint of its globals. It never checks that the function object **is** the module's function, that its `__globals__` is that module's namespace, or that its `__builtins__` are the real builtins. Names absent from `fn.__globals__` are skipped as "a real builtin", so a function's private builtins are never looked at.

- **P1:** `types.FunctionType(actions.write_report.__code__, g)` where `g` is a copy of the module globals whose `__builtins__` has an `open` that also writes a file outside the workspace. Passed in the `adapters` mapping under `(uri.plan.report.write, "1")`: `attest` returns `None`, the run is **VERIFIED**, the outside file exists.
- **P2:** same, with `g["hashlib"]` a fake `ModuleType("hashlib")` whose `sha256` writes outside. Modules are fingerprinted by name only. **VERIFIED**, outside file written.

This is the F2 injection point (the runner's `adapters` mapping), needs no patching of any module, stdlib or builtin, and is not covered by §6.16's residual list. It violates AC2 and Chetan's bar that a swapped adapter "must not retain trusted status or reach VERIFIED".

**Repair (small, attestation-only):** for every function in the closure require `sys.modules[f.__module__]` to exist, `f.__globals__ is vars(that module)`, `f.__builtins__ is vars(builtins)`, and `getattr(module, f.__qualname__) is f`. A prototype of exactly this (§5) refuses P1 and P2 with the node never called, keeps qualification 34/34 with counters 0, and changes one existing test's expected refusal code (spoofed name: `NOT_MODULE_FUNCTION` instead of `IMPLEMENTATION_CHANGED`; still refused). Add P1/P2 as tests.

### F2R-2 (MEDIUM): a module-typed global is fingerprinted by name only

- **P3:** the real, unmodified `actions.write_report`, with `actions.hashlib` replaced by a fake module named `hashlib`. Attests; **VERIFIED**; outside file written.

The report says patched helpers and constants are refused; a replaced module reference in the same globals is the same kind of edit (a uri_v1 module attribute, not stdlib code). **Repair:** in `_fingerprint`, require `sys.modules.get(ref.__name__) is ref` (included in the §5 prototype, which refuses P3 with `FOREIGN_MODULE`). Replacing the `sys.modules` entry itself is then stdlib-level patching and belongs to §6.16.

Note on P3's evidence: under the prototype, P3's outside file is still written, but by the fake module being called during plan compilation (`actions._qualified` uses `hashlib`), not by the adapter; the node is refused and the run is NOT_ATTEMPTED.

### F2R-3 (MEDIUM): methods of uri_v1 classes in the implementation are not attested

Classes are fingerprinted by module and qualname, and must still be their module's attribute, but their methods are not hashed. The implementation uses `officefile.SheetStructure`, `WorkbookStructure` and `WorkbookReadError` (frozen code) and `actions.ActionError`.

- **P4:** `officefile.SheetStructure.__init__` replaced by a wrapper that writes outside. `inspect_structure` attests; **VERIFIED**; outside file written. The §5 prototype does not close this.

This is in-process patching of uri_v1 code, which §9 describes as refused ("helper-patched") and §6.16 does not list (it names only standard-library and builtin code). **Repair, either:** (a) attest uri_v1 classes by their source plus a check that each method defined in source runs its compiled code (dataclass-generated methods need care), or (b) record it in §6.16 as a named residual ("methods of uri_v1 classes the implementation instantiates are not attested; patching them in-process is not detected") and state that the attacker needs to modify live module state, the same precondition as the stdlib case. Given Chetan's preference to close gaps, (a) is preferable if it stays small; (b) is acceptable under AC6 because it needs process-wide patching rather than a swapped adapter.

### F2R-4 (LOW): the report overclaims

- §6.14: "a swapped, spoofed, code-swapped or helper-patched adapter is refused and cannot run or reach VERIFIED" is false at `74474a2` (P1-P4).
- §9 lists "a patched helper" and "a shadowed builtin" as refused. Both are true only for the shapes tested: a helper function replaced in module globals and a builtin shadowed by a module global. They are not true for a private `__builtins__`, a replaced module or a patched class method.
- §6.16 should name, precisely, what remains after the repair: process-wide builtin, stdlib and `sys.modules` patching (P5 confirms it), C-level code, re-pinned source plus record, replacing `attestation` itself, and F2R-3 if option (b) is taken.

Preserve the history per the evidence-integrity rules: add a correction line, don't rewrite the old text.

### F2R-5 (LOW, latent): an "object" global is fingerprinted by type only

`_fingerprint` falls back to `["object", module, qualname-of-type]`. No global in today's four closures takes this branch (dumped in the audit), so nothing is exploitable now. A future adapter referencing, say, a `Path` or a dataclass instance would attest regardless of the value. Either refuse unknown objects (`FOREIGN_OBJECT`) or fingerprint by `repr` where it's deterministic.

### Informational (no action needed)

- **I-1:** P5 (process-wide `builtins.open` patched) attests and verifies with an outside write. §6.16 records this correctly.
- **I-2:** `functools.wraps` wrappers, `partial` and lambdas are refused (P7, P9). A copy of the module globals, left unmodified, attests (P8); it becomes refused after the F2R-1 repair, which is harmless.
- **I-3:** A CRLF copy of the record verifies under the committed pin (P12), because `_record` normalises line endings before hashing. That is intended for Windows checkouts, and it is safe because the normalised bytes must still match the pin.
- **I-4:** Attestation runs per node immediately before the call; the attested digest is recorded per node in the RUN_RESULT executor claim (`adapters`), which the valid-adapter test checks.
- **I-5:** The record's `action_id` is not compared with the contract. That's safe today because verifier coverage is unique per action (P6), and the report says renamed actions intentionally attest (C04). If two actions ever share a coverage ID, cross-wiring would attest.
- **I-6 (probe placement):** a probe file under `tests/` that imports `uri_v1.execution.planning` trips the slice's own `test_no_existing_module_imports_planning`. So the probe script is committed as `probes.py.txt`, and the full-suite run above was taken in a clean worktree without it.

## 4. What was verified, and how

- The diff `458cbda..74474a2` was read in full for `attestation.py`, `runner.py`, `actions.py`, the qualification driver, the record and the attestation tests. The report's §6.14, §6.16 and §9 were read.
- 13 independent probes (`probes.py.txt`), run through the real `PlanRunner` with the slice's own `runner_env` fixture where a run outcome matters. Results are in `probe_results.txt`: P1-P5 VERIFIED with outside write; P6, P7, P9, P10 and P11 refused; P8 and P12 attest (benign); P13 digests reproduced in a fresh interpreter.
- Full suite in a clean worktree at `74474a2`. The environment first needed `google-auth-oauthlib` in addition to the known `openpyxl` / `google-api-python-client` / `google-auth`: without it two `uri_core` test modules fail to import. That's an environment gap, not a defect of this commit.
- Guard offenders recomputed with the frozen test's own diff and allowlist logic (`guard_offenders.txt`).

## 5. Prototype repair (evidence only; not applied to the slice)

`prototype_fix.diff.txt` (+8/-1 lines in `attestation.py`): the three identity checks from F2R-1 and the module identity check from F2R-2. With it applied in a scratch tree:

- P1, P2 → `NOT_MODULE_FUNCTION`, NOT_ATTEMPTED, no outside write by the adapter;
- P3 → `FOREIGN_MODULE`, NOT_ATTEMPTED;
- P4 and P5 → unchanged (F2R-3 / residual);
- slice tests 136/137: the one failure is the expected-code change in `test_adapter_spoofing_the_qualified_name_is_refused`;
- slice qualification 34/34, counters 0, gate passed.

The prototype was reverted; the slice branch is untouched.

## 6. Unverified or not run

- **Windows:** not run. The attestation compiles module files and compares code objects, so a Windows run should confirm that the digests match the record there too. Source is LF-normalised before hashing; `_runs_its_source` compiles the raw file bytes, and CRLF source compiles to equal code objects in CPython, but this was not observed. It doesn't change the verdict.
- **Other Python versions:** code-object equality and `inspect.getsource` behaviour are version-sensitive, so a different CPython minor version may produce different digests or a `CODE_MISMATCH`. That would fail closed (safe) but would block runs. It's not observed here and doesn't change the verdict.
- **`graphify update .`:** not run (docs-only commit; graphify not installed).

Commands (all COMPLETED_WITH_RESULT):
`python -m pytest -q -p no:cacheprovider tests/` · `tests/test_dynamic_planning_*.py` · `python -B scripts/dynamic_planning_qualification.py` · review-set pytest line from report §3 · `python scripts/m33_3_r_anchors.py` · `pytest tests/governance` + `scripts/governance/uri_state_validator.py` · `python scripts/m3{6_memory,7_edge,8_harness}_qualification.py` · `git diff --name-status 5bbf738 74474a2` · `git diff --quiet 5bbf738 74474a2 -- uri_v1/execution/verify.py`.

## 7. Required for ACCEPT

1. Fix F2R-1 and F2R-2 in `attestation.py` (for example, as in §5), with P1-P3 added as tests.
2. F2R-3: attest uri_v1 class methods, or record the residual precisely in §6.16.
3. F2R-4: correct §6.14 and §9, preserving the history.
4. F2R-5 is optional (latent).
5. Rerun the slice tests, the full suite (expected: only the accepted guard, slice paths only), and the slice qualification; then run a fresh re-audit.

The slice stays **PROVISIONAL / NOT FROZEN**.
