# URI Scheduler — canonical development integration receipt

Date: 2026-10-09 (Asia/Kolkata). Recorded by Claude from the primary evidence in `evidence/` next to this file.
Mandate: owner brief "URI — Scheduler Closure, Integration & URI-Wide A2UI Development", Part 1 §5: integrate the
scheduler into the canonical development branch once the ws-hardening dependency is accepted and all gates pass; real
Claude authentication must not block a safe development-branch integration while execution stays disabled.
**No production cutover. Nothing activated:** no Windows task registered, festival schedule not activated, live Claude
not logged in (scheduled real-Claude runs stay BLOCKED by the harness gate).

## 1. Commits

| role | commit |
|---|---|
| Canonical branch before integration | `integration/git-sync-20261008` = `f24d57ab197bf84d890e5032662ec230a8caecf7` (contains ws-hardening `522939c`, its Codex-accepted code `9ae28f4`, and the companion-settings integration) |
| Scheduler branch (accepted) | `phase/scheduler` = `45e9791` — Codex closure round 11 ACCEPT WITH FINDINGS (repaired or recorded), `docs/scheduler/SCHEDULER_AUDIT.md` |
| Merge | `bdaf17b` (`--no-ff`, no conflicts) |
| EOL normalization | `f6e3e62` — 21 LF-only lines in two CRLF guard files restored to CRLF; `git diff -w --ignore-cr-at-eol bdaf17b f6e3e62` empty |
| Integration review repair | `e6d8e84` — INT-01: the materializer also copies `scripts/scheduler_task_ctl.ps1` |
| Integration commit | the commit adding this receipt (docs and evidence only); hash reported in the final status message |

## 2. Dependency, ancestry, provenance

- The scheduler's base `99f8041` and the accepted hardening code `9ae28f4` are ancestors of `f24d57a`
  (`git merge-base --is-ancestor`); merge base of `phase/scheduler` and canonical = `99f8041`.
- Scope of `f24d57a..e6d8e84` (60 scheduler paths): `uri_scheduler/**`, `tests/scheduler/**`, `scripts/scheduler_*`,
  `docs/scheduler/**`, exact-path additions in `scripts/phase2close_chain.py`, `tests/phase2a/test_frozen_core.py`,
  `scripts/oi_materialize_test_runtime.py`, the Dashboard scheduler tile, its client/view and widget test. **No** path under
  `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/`, `model_lab/integration/`; root `.gitignore` unchanged. Binary
  additions: two fixture GIFs (evidence). No secret pattern in added lines.
- Codex integration review (read-only, clone `sra`, `gpt-6-sol`, medium): **ACCEPT WITH FINDINGS** — merge identical to the
  branch (same 60 paths, 56 added blobs identical, shared files identical ignoring whitespace/EOL), exact-path guards
  contain all 86 tracked scheduler + WS paths with no glob widening, tile reachable with companion-settings changes, no
  protected path, no activation. Finding INT-01 (Medium) repaired in `e6d8e84`.
- Frozen check at `e6d8e84` (`evidence/ws_frozen_check_e6d8e84.json`): 121/121 Phase 1 checkpoint files byte-identical,
  no protected path changed.

## 3. Combined regression (isolated gate tree `C:\Users\cheta\Development\uri-sched-gate2`)

Materialized from `f6e3e62` with `scripts/oi_materialize_test_runtime.py --exclude-oi-tests`
(`evidence/uri-sched-gate2_MATERIALIZATION_RECEIPT.json`: HEAD `e8e3b65` = base, overlay `759d0d4`, candidate `f6e3e62`).
Fixtures: `<gate>\evidence` copied from `uri-ws-gate4\evidence` without its chain outputs; `work\c1\checkpoints` copied
from `.codex\worktrees\uri-phase1-integration\uri-agent` (883 files; aggregate SHA-256 of the per-file list identical for
source and copy). `e6d8e84` differs from `f6e3e62` only in the materializer's path list, which the gate tree does not
execute (test directories are excluded from the gate), so the gate result applies to `e6d8e84`.

| run | gates | result |
|---|---|---|
| run 1 (`evidence/chain_run1_*`, 16:17) | phase2 | PASS 486 / 0 / 2 skipped |
| | authority | PASS 134 / 0 |
| | phase1-full | 2,675 / 11 / 12 — **outcome change**: `test_gemma_worker_mcp::test_live_ollama_status_and_model` passed → skipped |
| | phase1-scope, residue | PASS |
| | verdict | **CHAIN_FAILED** (kept, not overwritten) |
| run 2 (`evidence/chain_run2_*`) | phase1-full | **PASS 2,676 / 11 / 11; outcome identity: 2,698 ids, missing = added = outcome_changed = ∅; same failure set as the accepted log; baseline pins hold** |
| | phase1-scope | PASS: outside Phase 2 scope ∅, importers ∅, 98 frozen files byte-identical, runner argv accepted |
| | residue | PASS |
| | verdict | **ALL_PASS** |

**Correction record (run 1 → run 2).** The single outcome change in run 1 was environmental: the skip reason is
`Ollama service unavailable at http://127.0.0.1:11434 ... [WinError 10061] ... actively refused`
(`evidence/chain_run1_ollama_skip.txt`). An Ollama owned by another session was listening when the run started and had
stopped by the time the test ran. For run 2 this session started an idle `ollama serve` (no model loaded), re-ran
phase1-full, phase1-scope and residue on the same tree, and stopped that Ollama afterwards (pid 9600). Phase 2 and
authority were not re-run: they do not use Ollama and already matched the baseline on this tree.

The 11 Phase 1 failures are the accepted baseline failures (pre-existing), not regressions.

Suites on the integration worktree at `e6d8e84`:

| suite | result |
|---|---|
| `pytest tests/scheduler tests/oi tests/ws` | **297 passed, 20 skipped** (= 226 OI+WS of the canonical receipt + 71 scheduler; skips are the opt-in live tests) — `evidence/pytest_scheduler_oi_ws_e6d8e84.txt` |
| `flutter test` (uri_ui) | **431 passed, 3 skipped**, 0 failed — `evidence/flutter_full_e6d8e84.txt` |
| `flutter analyze` | 2 infos, both pre-existing and identical at `f24d57a` |
| `URIScheduler` scheduled task | not registered (checked before and after) |

GPU coordination: both runs held the machine-wide lease (`purpose regression_chain`) through a separate waiting holder;
four history records (`evidence/gpu_lease_history_scheduler_chain.jsonl`). No Brain was loaded.

## 4. Independent audit status

Scheduler code: Codex rounds 1-7 REJECT, 8 ACCEPT WITH FINDINGS (`7496bba`); closure rounds 9-10 REJECT, 11 ACCEPT WITH
FINDINGS (`a3d4d0f`, repairs in `45e9791`). Integration review: ACCEPT WITH FINDINGS (INT-01 repaired). The regression
gates above are this session's own runs, not Codex claims.

## 5. Limitations and owner gates carried

F10 live Claude generation not run (scheduler client profile not logged in); F2 (Claude Code permission engine is not an
OS sandbox); R7-1 (cancel/start window, measured ≤ 3.6 ms, no guarantee); festival list activation (owner approval; first
default GIF would be due 2026-10-18 09:00 IST); Windows logon task (procedure tested by dry runs only); SAFE-1 (machine
stability, historical; no hang during these runs).

## 6. Integration and rollback

Fast-forward `integration/git-sync-20261008` from `f24d57a` to the integration commit (normal push, no force), verified by
`git ls-remote` and a fresh clone.

Rollback (owner): the previous canonical tip is `f24d57a`. To revert the scheduler on the development line without
rewriting history: `git revert -m 1 bdaf17b` plus reverts of `f6e3e62`, `e6d8e84` and the receipt commit, then push.
To restore the exact previous ref instead (history rewrite, owner decision only):
`git push uri-repo +f24d57a:integration/git-sync-20261008`. Nothing outside the repository needs rollback: no task,
service or schedule was activated.
