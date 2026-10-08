# URI Cleanup Verification Report — 2026-10-08

Verifier: consolidation session (Claude). Evidence folder: `C:\Users\cheta\Development\uri-canonical-evidence\`
(gate logs in `gates_runtime\`, live checker reports `live_report_*.json`, ACL backups `acl\`).
Only `COMPLETED_WITH_RESULT` runs are used as evidence below.

## Verdict

**CLEAN WITH LIMITATIONS for the repository; NOT CLEAN for the live PC runtime.**

- Repository: one canonical candidate line exists. It is reproducible from a fresh GitHub clone, its runtime
  checkout passes every accepted regression gate (differences fully explained below), and its tooling detects every
  obsolete-runtime activation attempt tried.
- Live PC: the active URI server is still the legacy dirty master started by scheduled task `\URIServer`. Every UI
  build binds to it through a shared preferences file. It is fully accounted for and the authoritative start gate
  refuses to run beside it, but removing it from the execution path needs owner approval (CONS-1..CONS-3).

## 1. Gates on the materialized runtime candidate

Checkout `C:\Users\cheta\Development\uri-canonical-runtime-candidate` (fresh clone; `HEAD = e8e3b65`; overlay from
`2325ad7`). Byte checks before testing: 121/121 frozen Phase 1 files identical to zip `31a34dcb…`; 134/137 Phase 2
closure files identical to zip `fcd0d72e…`, the other 3 being the documented post-acceptance documents (A9).
Interpreter: copy of the accepted Phase 1 `.venv` (Python 3.13.15). Run at below-normal CPU priority.

| Gate | Accepted baseline (closure run9) | Candidate result | Comparison |
|---|---|---|---|
| Phase 2 suites (`phase2d_regression.py phase2`) | 452 passed, 2 skipped | **452 passed, 2 skipped** (exit 0) | identical |
| Phase 1 authority suites | 134 passed | **134 passed** (exit 0) | identical |
| Phase 1 full repository suite | 11 failed, 2675 passed, 12 skipped | 18 failed, 2675 passed, 5 skipped | 11 baseline failure IDs present, none fixed or changed; 7 differences explained in §1.1 |
| Flutter `uri_ui` | 195 passed, 2 skipped | **195 passed, 2 skipped** (exit 0) | identical |
| Live UI bridge ×10, native Codex | run9 PASS | **not run** | needs a provisioned server/client and a live Codex login; owner-environment gate, not re-run here |

### 1.1 The seven Phase 1 differences

| Test | Cause | Code regression? |
|---|---|---|
| 6 live Ollama tests (`test_ollama_provider_live` ×2, `test_ollama_reasoning_adapter_live` ×3, `test_m21_context_window_live` ×1) | During run9 Ollama was not running, so they skipped. During this run Ollama was running (started outside URI, shared tool) without the configured model: `ModelNotFoundError: Model 'qwen3:14b' was not found`. The 7 extra skips in the baseline are exactly these environment-gated tests | No. The tested source files are byte-identical to the accepted checkpoints |
| `test_phase1_offline_components::test_offline_checkpoint_restore_hashes_and_no_application_start` | Reads git-ignored provisional checkpoints from `work/c1/checkpoints/`, which exist only in the Phase 1 integration worktree. After copying that folder (11 MB, read-only source) into the runtime candidate: **1 passed** | No. **Reproducibility gap R-2:** these checkpoints are not on GitHub |

### 1.2 Committed-branch run (diagnostic)

Running the same suites directly on the committed branch checkout (`uri-canonical-candidate`) fails 85 Phase 2
and 70 authority tests with `SOURCE_CHECKPOINT_MISMATCH` plus 2 frozen-core base checks. This is the designed
behaviour of frozen `runtime_identity.py` (`HEAD` must equal `e8e3b65`), and it is why the runtime is materialized
(`URI_CANONICAL_BRANCH_DECISION.md` §3, TODO CONS-7). That run overlapped the Phase 2 session's chain and was
stopped by me; its results are used only for this diagnosis.

## 2. Runtime authority and adversarial tests

`tests/consolidation/test_runtime_authority_check.py`: **45 passed** (25 original + 9, 7, 3 and 1 added after Codex rounds 1-4). Attempts covered, each confirmed CONTAMINATED
or refused:
- the donor desktop server, the `_V1` launcher, the Phase 2 dev worktree server and the Phase 1 integration launcher
  each run as URI;
- a legacy entrypoint run from inside the authoritative root;
- a copy of the legacy checkout elsewhere, a lookalike root `_V1-evil`, and a lookalike `…-runtime-candidate-copy`;
- a scheduled task or startup shortcut pointing at a donor;
- an unknown listener on a URI port;
- the UI bound to a port with no accounted listener, or to a donor server;
- the authorized binary started with a quarantined model;
- the authorized launcher pointed at a legacy state root (no laundering through an authorized prefix);
- anything launched from the canonical development checkout;
- manifests with conflicting or unknown classifications, which are rejected with exit code 2.

Shared Ollama and test runners/agent shells are correctly not flagged.

Live checks on this PC (10:18 IST):

| Check | Result |
|---|---|
| Live checker, normal mode | NO_UNAUTHORIZED_RUNTIME: 8 TRANSITIONAL_LEGACY findings (task, 2 shortcuts, 3 legacy server processes, listener, UI binding), of which 6 are active or auto-starting (the two shortcuts are not startup items); Ollama shared; 0 unaccounted |
| Live checker, `--strict` | CONTAMINATED (6 active transitional findings) — expected until CONS-1..3 |
| Live end-to-end attack: dummy listener on 127.0.0.1:8077 with a `_V1\scripts\run_uri_server.py` command line | Detected as DONOR_ONLY process + listener, exit 1; clean again after it stopped |
| Start gate `scripts\uri_authorized_start.ps1 -Action validate` | **REFUSED** (strict checker found the legacy runtime); the frozen launcher was never invoked |
| Frozen C1 refusals (legacy ports 8000/8018/8021/11434/1234, foreign listener, generic health) | covered by the Phase 1 authority/full suites above (passing) |

## 2a. Independent adversarial review (Codex CLI, gpt-6-sol, read-only)

Round 1 (2026-10-08): **REJECT.** Findings, each confirmed by me against the code before repair:

| ID | Sev | Finding | Repair |
|---|---|---|---|
| X-1 | High | A shared-dependency name anywhere in the command (`--label "LM Studio"`) hid a URI server | Shared dependencies match only the launch target, and never a URI-looking command |
| X-2 | High | An authorized path given as an argument laundered an unknown executable; a legacy path given as an argument made a donor transitional | Classification now uses the parsed launch target (script for interpreters, `-File` for PowerShell, inner command for `cmd /c`, module for `-m`). Any donor or quarantined root referenced anywhere outranks an authorized or transitional target |
| X-3 | High | `pythonw -m uvicorn` on an off-range port or `0.0.0.0`, and `-EncodedCommand` autostarts, were not reported | Every interpreter/uvicorn-owned listener on any port is evaluated. Interpreter-launched and encoded autostarts are evaluated, and encoded commands are decoded |
| X-4 | Med | The UI binding matched by port only | The listener address must serve the URL host (or be a wildcard) |
| X-5 | Med | The start gate can be bypassed by invoking the frozen launcher directly | **Accepted limitation:** the frozen launcher cannot be changed. The frozen launcher still enforces its own identity, port and source checks. Containment makes the gate the only shortcut/task path at cutover |
| X-6 | Med | Restore re-enabled a task that was already disabled; task lookup ignored the task path | Restore honours the recorded previous state; all task calls use task path `\` |
| X-7 | Med | Task, Run-key and shortcut text was stored verbatim (possible secrets) | Secret-looking argument values are redacted in snapshots and findings |
| X-8 | Low | The report said 6 transitional findings where the live report had 8 | Corrected above (8 findings, 6 active) |

Repairs are covered by 9 new tests (34 total, all passing). A negative control ran the new tests against the
pre-repair checker: 8 failed there, which proves they test the repaired behaviour. The ninth test, for the
`cmd /c`-wrapped legacy task, guards against regression. Round 2 result: see §2b.

## 2b. Codex review round 2: REJECT, then repaired

Round 2 confirmed X-1, X-3, X-4, X-6 and X-8 repaired and X-5 accepted as a limitation. It reported these new gaps,
each confirmed before repair:

| ID | Sev | Finding | Repair |
|---|---|---|---|
| Y-1 | High | `cmd /c A & B` (also `&&`, `||`, `|`, `;`) classified only A, so an authorized or legacy first command hid a second server | Every chained command is parsed and classified. The most severe result wins (QUARANTINED > DONOR > UNACCOUNTED > TRANSITIONAL > SHARED > AUTHORIZED). Redirections such as `2>&1` are not treated as separators |
| Y-2 | Med | `Authorization: Bearer x` and secrets inside `-EncodedCommand` payloads survived redaction | Bearer/Basic values are redacted. Encoded payloads are replaced by their decoded, redacted text |
| Y-3 | Med | Shared dependencies matched by substring (`C:\Tools\LM Studio Evil\server.exe`) | Shared dependencies are exact install directories with path-boundary matching |
| Y-4 | Med | PowerShell `-Command "& 'script'"` and its encoded form were not recognised as the authorized launcher | `-Command` content and decoded payloads are parsed as commands (call operator `&` handled) |
| Y-5 | Low | Relative targets with `[wd=...]` and `\\?\` paths misclassified (fail-closed) | Resolved against the working directory; `\\?\` stripped. UNC admin-share and 8.3 short-name forms remain fail-closed (reported UNACCOUNTED), which is safe but can over-report |

7 new tests (41 total, all passing). Negative control: 6 of them fail on the round-1 checker. The seventh, a
redirection guard, passes on both. Live run after the repair matched the earlier live run: normal mode found 0
contamination, and strict mode found 6 active transitional findings. Round 3 result: see §2c.

## 2c. Codex review round 3: REJECT, then repaired

Round 3 confirmed Y-2..Y-5 repaired, and confirmed the live legacy server and the authorized launcher are still
classified correctly. It found:

| ID | Sev | Finding | Repair |
|---|---|---|---|
| Z-1 (Y-1 residual) | High | `1& cmd` was not split, because a digit before `&` was treated as a redirection | Only `>&` and `<&` are redirections; every other `&` separates commands |
| Z-2 | High | `..` traversal (`…/LM Studio/../../URI-preservation/server.exe`, `…/Ollama/../../…/uri-model-lab-nvme/…`) laundered donor or quarantined binaries through a shared or authorized prefix | Path normalization collapses `.` and `..` before any prefix or root test |
| Z-3 | Low | `redact` raised on non-string input | Bytes are decoded; other types become strings |

3 new tests (44 total, all passing). Negative control: all 3 fail on the round-2 checker. Live run: unchanged (0
contamination in normal mode; 6 active transitional findings in strict mode). Round 4 result: see §2d.

## 2d. Codex review round 4: REJECT, then repaired

Round 4 confirmed Z-1..Z-3 repaired. It confirmed no regression: the live legacy task and processes stay
TRANSITIONAL_LEGACY, and the authorized `-File`, `-Command`, encoded and relative forms stay AUTHORIZED. A `..`
traversal out of the authorized root classifies QUARANTINED. One new finding:

| ID | Sev | Finding | Repair |
|---|---|---|---|
| W-1 | High | An executable inside a donor root with no URI-looking name (`D:/URI-preservation/server.exe --port 9100`) was filtered out before classification, in tasks, Run keys, startup shortcuts, processes and off-range listeners | Anything that launches from or mentions any manifest root is always evaluated. Listeners are evaluated on owner command line and image path. A process is reported when it owns an evaluated listener |

1 new test (45 total, all passing); it fails on the round-3 checker (negative control). Live run unchanged. Round 5
result: see §2e.

## 3. Integrity and recoverability

| Item | Result |
|---|---|
| Frozen Phase 1 zip | `31a34dcb…f7` re-hashed: match |
| Phase 2 ops r6 / closure -f zips | `9a0be52c…0a` / `fcd0d72e…98`: match |
| Runtime v1 `llama-server.exe` | `4fdc1a67…0306`: matches freeze record |
| Fresh GitHub clone reproducibility | Clone of `uri-repo integration/git-sync-20261008` (`f8de153`) → candidate; materialized runtime byte-matches all accepted checkpoints; gates as §1. Gap R-2: `work/c1/checkpoints` needed by one test is not on GitHub |
| Secrets in Git | Full-history search for session/key/account/identity/secret files: none. All new consolidation files scanned: 0 findings |
| Secret exposure on PC | 33 files were readable by `CodexSandboxUsers`; now 0 (ACL backups saved). Live legacy server health still `ok` after the change |
| Frozen Core | No frozen file modified; candidate commits add documents, the manifest, a checker, two PowerShell scripts and a test only |
| Active Phase 2 session | Its worktree, processes and evidence were only read. My gate run overlapped its `chain2` at below-normal priority; tests use random IDs for named mutexes (checked); no shared fixed ports found |

## 4. Remaining limitations (honest list)

| ID | Limitation | Effect |
|---|---|---|
| L-1 | Legacy server, its logon task and both `URI.lnk` shortcuts are still active | Live runtime is not the authoritative one; owner approval needed (CONS-1..3) |
| L-2 | All `uri_ui` builds share one preferences file with session tokens | Any UI build follows port 8000; fix is per-installation client storage (CONS-5) |
| L-3 | Canonical branch is not directly runnable by the frozen launcher | Materialization procedure required (CONS-7) |
| R-2 | Phase 1 provisional checkpoints (`work/c1/checkpoints`) exist only on this PC | One regression test needs them; preserve them on GitHub with owner approval |
| L-4 | Live UI-bridge and native Codex gates not re-run | Require provisioned server/client and owner login |
| L-5 | Canonical Core lacks desktop-line features (Google/Gmail/Drive/PPT, M36 memory, M37 Edge, M39 Office, dynamic planning, dictation, harness console, voice) | Cutover before C6 parity would regress the owner's daily desktop; donors preserved and tagged |
| R-3 | Longest committed path is 151 characters (`docs/evidence/phase2/phase2d_review/round3/probe_state/...`). A clone into a long base directory fails checkout on Windows (`Filename too long`); observed in a scratch clone | Clone with `git -c core.longpaths=true clone ...` or into a short directory. With longpaths, the fresh clone of `canonical/candidate-20261008` checked out cleanly and its 25 consolidation tests passed |
| L-6 | Encrypted vault restore not re-tested | Vault predates Phase 1 freeze; GitHub backup is the tested recovery path |
