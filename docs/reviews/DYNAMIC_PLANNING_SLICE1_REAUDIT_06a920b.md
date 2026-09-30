# Dynamic planning slice 1: independent re-audit of F2 repair round 3 at `06a920b`

- **Subject:** `06a920b` on `claude/dynamic-planning-slice1-2eemmh` ("attest adapter globals, builtins, module references and URI class methods (re-audit F2R-1..5)"). It sits on `74474a2`, which I audited in `5eb0149` (REPAIRS_REQUIRED).
- **Auditor:** Claude, the same audit thread as `5eb0149`, independent of the implementation thread. This is an audit only: no slice file was changed. A throwaway prototype (§5) was applied to a scratch tree and then reverted.
- **Date / platform:** 2026-09-30, Linux, Python 3.11.15. Windows was not run.
- **Evidence:** `docs/reviews/dynamic_planning_f2_reaudit_06a920b/`, which holds the probe script (as `probes.py.txt`) and the raw outputs.

## Verdict: **REPAIRS_REQUIRED** (one narrow item)

F2R-1, F2R-2, F2R-4 and F2R-5 are closed, and F2R-3 is closed for function-typed members. I verified each of these with my own probes, not only with the new tests. All the reruns are clean.

One bypass of the same kind as F2R-3 remains, R3-1. A non-function descriptor object placed on a uri_v1 class that the adapter uses is invisible to class attestation. With it in place, the run reaches **VERIFIED** and writes a file outside the workspace. Report §10 says F2R-3 is "Closed, not documented", so the claim is wrong as written.

Either repair below leads to ACCEPT:
- **Fix it.** The 13-line prototype in §5 refuses the bypass and keeps 143/143 slice tests and qualification 34/34.
- **Record it in §6.16.** Add it as an in-process residual and correct §10.

## 1. Acceptance criteria

These are the same AC1-AC8 as `5eb0149` §1, from Chetan's decision of 2026-09-29 13:49, plus two more:

| # | Criterion |
|---|---|
| AC9 | Each finding F2R-1 to F2R-5 is closed as claimed, or recorded exactly as a residual. |
| AC10 | The new checks introduce no false refusal of the genuine catalog: slice tests, qualification and a fresh interpreter all attest. |

## 2. Results

| # | Result | Evidence |
|---|---|---|
| AC1 | **Met.** The record digest was re-pinned to `9975a268…`. A fresh interpreter recomputes all four adapter digests, and they equal the record (P13). | `probe_results.txt` |
| AC2 | **Met for swapped adapters.** P1, P2 (a function rebuilt from the genuine code with private builtins or globals), P7 (a `functools.wraps` wrapper) and P8 (a copy of the globals) are all refused with `NOT_MODULE_FUNCTION`. P3, a fake module placed in the real module, is refused with `FOREIGN_MODULE`. Every refused run is NOT_ATTEMPTED, and the adapter writes nothing outside the workspace. | `probe_results.txt` |
| AC3 | **Met.** The boundary is still checked: P6 cross-wiring and P10 downgrade both give `BOUNDARY_MISMATCH`. | same |
| AC4 | **Met.** 143 slice tests pass (137 plus 6 new tests covering P1-P4 and F2R-5). | `slice.txt` |
| AC5 | **Met.** Full suite: **1445 passed, 1 failed, 9 skipped**. The one failure is the accepted `test_m36_and_frozen_files_unchanged`, and I recomputed its 18 offending paths: all are slice paths. Slice qualification exits 0 at 34/34, with all six counters 0, the C33 semantic miss at 1/1 and the gate passed; the rewritten result file differs from the committed one only in latency. The review set passes 113. Anchors report ok with changed []; governance passes 37 and the validator reports VALID. M36, M37 and M38 qualification each exit 0. | `full_suite_summary.txt`, `guard_offenders.txt`, `dp_qualification.txt`, `review.txt`, `anchors.txt`, `governance.txt`, `m36_m38_qualification.txt` |
| AC6 | **Partly met.** §6.16 now lists the residual bound precisely: process-wide builtins, stdlib and `sys.modules` patching (P5 and Q6 confirm it), C-level code, re-pinning, replacing the attestation, and the effects of P3 during planning. It does not list R3-1. | report §6.16 |
| AC7 | **Met.** `git diff --name-status 5bbf738 06a920b` shows 38 additions and nothing else. `verify.py` is identical. Since `74474a2` only slice files changed. | `frozen.txt` |
| AC8 | **Met.** 140 added and 11 removed lines, all in `attestation.py`. That is larger than before, but still one module and no framework. | diff |
| AC9 | F2R-1 ✓, F2R-2 ✓, F2R-4 ✓ (§6.14 correction appended and history kept), F2R-5 ✓ (`FOREIGN_OBJECT`). F2R-3 is closed for function, property, staticmethod and classmethod members, including dataclass-generated methods (P4, Q2, Q3 and Q4 are all refused), but **not for non-function members (R3-1)**. | `probe_results.txt` |
| AC10 | **Met.** The genuine catalog attests in-process and in a fresh interpreter. The C04 rename still verifies. | P13, `dp_qualification.txt` |

## 3. Findings (most severe first)

### R3-1 (MEDIUM): a non-function descriptor on a uri_v1 class escapes class attestation

`_class_members` walks `vars(cls)`, and `_functions_of` extracts functions from functions, `property`, `staticmethod` and `classmethod`. Any other value is skipped silently: an arbitrary descriptor object, a callable instance or a builtin. Attribute lookup honours data descriptors on the class ahead of the instance `__dict__`, so such an object runs arbitrary code whenever the adapter reads that attribute.

**Q1:** I set `officefile.WorkbookStructure.sheets` to a data descriptor whose `__get__` writes a file outside the workspace and then returns the real value. `inspect_structure` reads `structure.sheets`, and the result was:
- `attest` returned `None`;
- the run reached **VERIFIED**;
- the file outside the workspace was written.

This is the same precondition as P4 (in-process patching of live uri_v1 class state), which round 3 chose to close. So §10's claim "Closed, not documented" is false as it stands. Q2, the same trick on `__init__`, happens to be refused only because the dataclass-generated method set no longer matches; that refusal is an accident, not a rule.

**Repair, either:**
- **(a)** Refuse any class-dict member that is neither function-like nor known class or dataclass machinery of the expected type nor a plain value. The prototype in §5 does this in +14 lines with a `FOREIGN_MEMBER` code.
- **(b)** Record it in §6.16 and correct §10.

Q1 should become a regression test with (a), and should be cited in §6.16 with (b).

### R3-2 (LOW, latent): `__defaults__` and `__kwdefaults__` of source-defined functions are not attested

**Q5:** setting `actions.write_report.__defaults__ = (None,)` still attests. No function in today's closures has defaults, so nothing changes behaviour now. A future helper with a default argument, though, could have that default swapped without detection. The generated-method path already compares defaults. **Repair (optional):** add `repr(f.__defaults__)` and `f.__kwdefaults__` to the per-function digest part, or refuse a mismatch against a fresh compile.

### R3-3 (LOW, latent): uri_v1 functions reached through a module attribute are not in the closure

The closure follows only names that resolve to uri_v1 functions or classes in `__globals__`. A call written as `officefile.helper(...)` goes through a module global, which is fingerprinted by name and identity only, so `helper` would be neither hashed nor checked. No closure function uses a uri_v1 module global today: the only module globals are `hashlib`, `json`, `zipfile`, `posixpath` and `xml.etree.ElementTree`. **Repair (optional):** refuse a uri_v1 module as a global (`FOREIGN_MODULE`), which forces direct imports, or note the rule in the attestation docstring.

### Informational

- **I-1:** P5 (patched `builtins.open`) and Q6 (`sys.modules` entry and module global swapped together) still attest. §6.16 lists both correctly.
- **I-2:** Q7, a plain class-level value, still attests. That is benign, and it stays allowed under the §5 prototype because plain values are fingerprinted by the class source only. A plain value that shadows a field could change behaviour. Under (a), consider comparing plain members with the literals in the class source.
- **I-3:** The report's statement that record digests "do not depend on the interpreter version" is mostly right, because digests are built from source plus reprs of globals. The `repr` of a compiled `re.Pattern`, however, is part of the digest and could in principle differ across CPython versions. Any such mismatch fails closed, so this is not a false VERIFIED. It does not affect the verdict.
- **I-4 (stopping line, recommendation):** each round has closed the demonstrated bypass class. In-process patching of live module and class state has no natural end in pure Python. After R3-1, I recommend §6.16 gain one general sentence to that effect, rather than further rounds chasing individual attribute kinds: "any other in-process modification of live module or class state is outside attestation; containment is the effect guard or an OS sandbox". This is an audit recommendation, not a requirement. It is Chetan's call whether R3-1 is fixed or recorded.

## 4. What was verified, and how

- I read the full diff `74474a2..06a920b` for `attestation.py`, `actions.py`, the record, the tests and report §§6.14, 6.16 and 10.
- I reran my 13 round-1 probes and 7 new probes (Q1-Q7) through the real `PlanRunner` via the slice's `runner_env` fixture. The probe file was placed under `tests/` in a scratch tree, run, and then removed, because a probe under `tests/` trips `test_no_existing_module_imports_planning`. The suite runs above used a clean worktree without it.
- The environment needed `google-auth-oauthlib`, `openpyxl`, `google-api-python-client` and `google-auth`, as in the round-1 audit.

## 5. Prototype repair for R3-1 (evidence only; not applied to the slice)

`prototype_fix.diff.txt` (+14 lines in `attestation.py`): `_plain_member` allows only these non-function class members:
- `__module__`, `__doc__`, `__annotations__`, `__match_args__`, `__dataclass_params__` (a `dataclasses` object), `__dataclass_fields__`, `__hash__ = None`, and the `__dict__`/`__weakref__` getset descriptors;
- plain values.

Anything else is refused with `FOREIGN_MEMBER`. With the prototype applied in a scratch tree:
- Q1 and Q2 give `FOREIGN_MEMBER`, NOT_ATTEMPTED, and nothing is written outside the workspace;
- P4, Q3 and Q4 are still refused as before;
- slice tests pass 143/143;
- qualification is 34/34 with all counters 0 and the gate passed.

The prototype was reverted.

## 6. Unverified or not run

- **Windows and other CPython versions:** not run. Code-object and dataclass-regeneration comparisons are interpreter-specific. A mismatch fails closed (no run, never a false VERIFIED), but it would block runs until re-qualified. This does not affect the verdict.
- **`graphify update .`:** not run. The commit is docs only, and graphify is not installed.

## 7. Required for ACCEPT

1. R3-1: apply fix (a) and add Q1 as a regression test, or record it in §6.16 per (b). In either case, correct §10's "Closed" claim for F2R-3, keeping the history.
2. R3-2 and R3-3 are optional (latent).
3. Rerun the slice tests, the full suite (expected result: only the accepted guard, on slice paths) and the slice qualification.

For a round that only does the above, I would accept a focused re-check of R3-1 plus the reruns; a full re-audit would not be needed. The slice stays **PROVISIONAL / NOT FROZEN**.
