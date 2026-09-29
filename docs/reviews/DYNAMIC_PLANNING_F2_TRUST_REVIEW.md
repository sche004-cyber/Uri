# Dynamic Planning Slice 1: F2 Trust Review (swapped trusted adapter)

Status: research and architecture review only. **No slice code was changed**; the prototypes live in `docs/reviews/dynamic_planning_f2/` as evidence. The slice stays PROVISIONAL / NOT FROZEN. Same-provider internal review.
Target: `458cbda` on `claude/dynamic-planning-slice1-2eemmh` (Linux, Python 3.11.15). Requested by Chetan, 2026-09-29 13:47.

## 1. The defect, restated from the code

`PlanRunner(adapters=...)` takes a caller-supplied dict `{(action_id, version): callable}`. Before each node the runner checks the *contract* (id, version, qualification digest, verifier coverage) against the live snapshot, then calls whatever callable sits under that key (`runner.py`, `_execute`). Nothing binds the callable to the qualified code, and nothing bounds what the callable does to the host. The verifier checks the workspace (`only_changed` + independent recompute), not the host, so an adapter that returns the right output but also writes outside the workspace is `VERIFIED` (audit probe F2, reproduced here as row `none / O_dict_swap_only`).

Two separable failures: **(a) identity**: an unqualified callable can run under a qualified key; **(b) effect**: any in-process callable can write outside the workspace, and nothing records it.

## 2. Acceptance criteria (set before the probes)

| # | A mechanism is acceptable only if |
|---|---|
| T1 | The F2 reproduction can no longer end `VERIFIED`, and preferably the outside write does not happen. |
| T2 | It stays inside the slice's own files: no frozen file, no `verify.py`, no battery/gate change. |
| T3 | The frozen battery still gives 34/34 with all six counters at 0, and honest runs still verify. |
| T4 | It is small (about 150 lines or less), adds no dependency, and changes nothing in the process outside a node's execution. |
| T5 | Its residuals are stated exactly, so the limitation that remains is narrower and named. |
| T6 | No live wiring. |

## 3. Options considered

| Option | Verdict |
|---|---|
| Accept as limitation (current §6.14) | Meets T2-T6 but not T1. |
| OS sandbox / separate process per node (seccomp, AppArmor, Windows job objects, a locked-down subprocess) | Would close (b) properly, but is platform-specific, heavy, and the same scope as the "no OS sandbox" limitation retained at the M36-M38 freeze. Fails T4. Not recommended for slice 1. |
| **M1 adapter identity pinning** | Closes (a) for everything done after import. Prototype in `proto.pin_check`. |
| **M2 effect guard (Python audit hook, PEP 578)** | Blocks (b) for every Python-level vector probed. Prototype in `proto.guarded`. |

**M1 (identity).** At import the planning package captures each qualified adapter's function object and code object. Before a node runs, the callable must be that same object with that same code, and the module attribute must still point at it (`IDENTITY` / `MODULE_ATTR`). Optionally the qualification record also pins `module:qualname` and the LF sha256 of `actions.py`, so an on-disk edit requires re-qualification.

**M2 (effect guard).** One `sys.addaudithook` is installed when the runner module loads. It does nothing unless a node is running. While one is, it refuses:
- writes outside the node's `files/` directory: `open` with a write mode or flags, remove, rename, mkdir, chmod, link, symlink, truncate, utime, xattr, and the shutil copy and move family (paths resolved with realpath);
- process creation, sockets, `ctypes` loading, `sys.settrace`/`setprofile`/`_getframe`, `gc` referrer walks, and class attribute patching.

Any refusal is recorded even if the adapter catches the exception, and threads that are still alive when the node returns count as a violation. Either way the node aborts `UNAUTHORIZED_EFFECT`. The enter/leave pair is token-bound, so an adapter cannot simply switch the guard off.

## 4. Evidence (all COMPLETED_WITH_RESULT)

`probes.py` runs the real C01 plan through the real runner, verifier, ledger and run store. It puts each attack in the inspect adapter, and each attack then calls the real action so the output stays correct. The script runs each attack under four configurations. Raw rows: `probe_results.json`.

| Attack (swapped adapter does this, then returns correct output) | none | M1 | M2 | M1+M2 |
|---|---|---|---|---|
| A `open(...,"w")` outside | VERIFIED, **written** | refused, not written | aborted, not written | refused |
| B `os.open(O_CREAT)` outside | VERIFIED, written | refused | aborted, not written | refused |
| C `Path.touch` outside | VERIFIED, written | refused | aborted, not written | refused |
| D `shutil.copy` of the source outside | VERIFIED, written | refused | aborted, not written | refused |
| E `subprocess.run(["touch", ...])` | VERIFIED, written | refused | aborted, not written | refused |
| F `os.system("touch ...")` | VERIFIED, written | refused | aborted, not written | refused |
| G thread writes outside, joined | VERIFIED, written | refused | aborted, not written | refused |
| H daemon thread writes *after* the node returns | VERIFIED, written | refused | aborted, **written later** | refused |
| I `ctypes` libc `fopen` | VERIFIED, written | refused | aborted, not written | refused |
| L adapter tries to reach the guard via `gc`, then writes | VERIFIED, written | refused | aborted, not written | refused |
| P extra file inside the workspace | NOT_VERIFIED (verifier) | refused | NOT_VERIFIED (verifier) | refused |
| Q write through a file handle opened *before* the node | VERIFIED, written | refused | **VERIFIED, written** | refused |
| M module attribute `actions.inspect_structure` patched at run time | VERIFIED, written | refused | aborted, not written | refused |
| N real function's `__code__` swapped after import | VERIFIED, written | refused | aborted, not written | refused |
| O the plain F2 dict swap | VERIFIED, written | refused | aborted, not written | refused |
| N' `__code__` swapped *before* the pins are captured (`early.py`) | n/a | **accepted** | blocked, not written | blocked |
| R honest run x20 | VERIFIED | VERIFIED | VERIFIED | VERIFIED |

- **Battery with M2 on** (`qual_guard.py`, the real driver with the guard wrapped around every adapter; C-1 stubbed because M2 does not touch the Edge path): 34/34, all six counters 0 (`qual_guard.json`). One case changes *why* it fails. C29 (`tamper_plan`) is now stopped by the guard, because the driver's tamper writes `bundle/plan.json` from inside the writer adapter. The expected status NOT_VERIFIED still holds, but the verifier's plan check is no longer what catches it. The driver should do that tamper just before verification instead, so C29 keeps testing the verifier.
- **Battery with M1 on:** not run as-is. The driver wraps *every* adapter to count calls and to inject tampering, so strict M1 refuses every case. The unit tests that inject misbehaving adapters are refused the same way.
- **Overhead:** within noise (about 44 to 49 ms per honest C01 run in all four configurations).

## 5. Self-review: gaps found and repaired before returning

1. *First M probe was invalid*: the patched function called itself, so the run crashed with a RecursionError instead of showing the effect. Repaired, and rerun (rows above are the repaired run).
2. *M1 looked complete* until the pre-capture case: capturing at import cannot see code patched before import. Added probe N' and listed it as a residual.
3. *M2 looked complete* until H and Q: a late thread and a pre-opened handle escape prevention. H still stops the run from verifying. Q does not.
4. *Strict M1 breaks the qualification harness and tests*, which a first draft missed. §6 therefore recommends a variant that records identity and caps the verdict, and does not refuse up front.
5. *Python's own documentation says audit hooks are not a sandbox.* Code written specifically to defeat this hook can do so, because it runs in the same process. The claim here is narrower. The guard blocks every probed Python-level effect from adapter code that was not written against the guard. It does not claim containment against a deliberate in-process adversary.

## 6. Recommendation

Adopt **M2 + M1-attest** in the slice's own files. The estimate is about 90 lines in a new `uri_v1/execution/planning/guard.py`, about 25 in `runner.py`, about 30 in the driver, plus tests. No frozen file changes.

- **M2 as prototyped.** A violation aborts the node `UNAUTHORIZED_EFFECT`. Scope is the adapter call only; the runner's own bundle writes and verification run outside it.
- **M1-attest instead of strict M1.** `RUN_STARTED` records, for each node, whether its adapter is the catalog's own captured function (`module:qualname` plus a code match). If any is not, the runner still runs and still calls the verifier, but the outcome is capped at `NOT_VERIFIED`, reason `ADAPTER_NOT_QUALIFIED`, and the verifier's own `verification_status` is kept. This closes T1 for every row, including Q and H. The harness keeps working if the driver counts calls with `sys.setprofile` instead of wrappers, and the scorer requires the verifier's status to be FAILED for the tamper cases, so the cap cannot hide a broken verifier.
- **Result for F2:** a swapped adapter can no longer end `VERIFIED` (M1-attest). Its Python-level writes outside the workspace are blocked before they happen (M2).

**What would remain (a narrower §6.14):**
- code patched in memory *before* the planning package is imported;
- writes through file handles opened before the node;
- native extension code that calls the OS directly without ctypes;
- code written deliberately to defeat an in-process audit hook.

All four need an attacker who already controls the process. That is the "no OS sandbox" class retained at the M36-M38 freeze, and OS-level containment would close them.

**Costs and decisions for Chetan:**
- **Process-wide hook.** The hook is permanent for the life of the process, and it is inert unless a node is running.
- **Windows unverified.** The design needs `os.path.normcase` on Windows paths. It must be probed on Windows before any freeze; it has not been run there.
- **Harness changes.** The harness stops injecting wrapped adapters for honest cases, and C29's tamper moves to just before verification. The battery JSON is unchanged.

**Unverified:** Windows behaviour (not run); Python 3.12+ audit event names (only 3.11.15 was probed); the M1-attest variant itself. M1-attest was not prototyped end to end; its effect is inferred from the strict M1 rows plus the unchanged verifier path. None of these change the recommendation, but each would have to be checked if it is adopted.
