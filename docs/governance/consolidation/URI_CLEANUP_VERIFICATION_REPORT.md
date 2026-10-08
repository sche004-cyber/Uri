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

`tests/consolidation/test_runtime_authority_check.py`: **25 passed**. Attempts covered, each confirmed CONTAMINATED
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
| Live checker, normal mode | NO_UNAUTHORIZED_RUNTIME: 6 TRANSITIONAL_LEGACY items (task, 2 shortcuts, legacy server process tree and listener, UI binding), Ollama shared, 0 unaccounted |
| Live checker, `--strict` | CONTAMINATED (6) — expected until CONS-1..3 |
| Live end-to-end attack: dummy listener on 127.0.0.1:8077 with a `_V1\scripts\run_uri_server.py` command line | Detected as DONOR_ONLY process + listener, exit 1; clean again after it stopped |
| Start gate `scripts\uri_authorized_start.ps1 -Action validate` | **REFUSED** (strict checker found the legacy runtime); the frozen launcher was never invoked |
| Frozen C1 refusals (legacy ports 8000/8018/8021/11434/1234, foreign listener, generic health) | covered by the Phase 1 authority/full suites above (passing) |

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
