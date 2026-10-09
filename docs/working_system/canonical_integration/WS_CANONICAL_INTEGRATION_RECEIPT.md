# Working System — canonical development integration receipt

Date: 2026-10-09. Recorded by Claude from the primary evidence in `evidence/` next to this file.
Mandate: "URI — Final Working-System Integration and Canonical Merge" (owner, 2026-10-09). The owner waived only the
standalone PC/system stability test (SAFE-1 stays documented as historical evidence). Code correctness, security,
frozen-file integrity and the regression gates were not waived.

## 1. Commits

| Role | Commit |
|---|---|
| Canonical development branch before integration | `integration/git-sync-20261008` = `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` |
| Accepted integration | `integration/working-system-20261008` = `68cac3d50b0bd63c833704504c2c59bb43a9b782` |
| Hardening candidate (validated) | `integration/ws-hardening-20261009` = `522939c151ead6641223330f7656a7a06cc5dd85` |
| Code last reviewed by Codex | `9ae28f4` (hardening round 10, ACCEPT WITH FINDINGS); `git diff -w --ignore-cr-at-eol 9ae28f4 522939c` outside `docs/` is empty |
| Integration commit | the commit that adds this receipt (docs and evidence only, child of `522939c`); its hash is reported in the final status message |

## 2. Pre-integration inspection

- Remote refs fetched from `https://github.com/sche004-cyber/Uri.git` before and after validation: `git-sync` =
  `037229c`, `working-system` = `68cac3d`, `ws-hardening` = `522939c` (unchanged throughout).
- Ancestry: `037229c` and `68cac3d` are ancestors of `522939c`; 71 commits over `037229c`, 26 over `68cac3d`, no merge
  commits in `68cac3d..522939c`, one author identity. `git fsck --no-dangling`: clean. Candidate worktree clean.
- Scope of `68cac3d..522939c` (57 paths): `docs/working_system/**`, the four new WS hardening paths
  (`scripts/ws_brain_host.py`, `tests/ws/test_ws_hardening.py`, `uri_operational_intelligence/brain_health.py`,
  `uri_operational_intelligence/gpu_lease.py`), WS-owned files (`worker_bridge.py`, integrated worker, launcher, WS Dart
  files, Dashboard tile), and the WS-D3 scope guards (`tests/phase2a/test_frozen_core.py`, `scripts/phase2close_chain.py`)
  plus `scripts/oi_materialize_test_runtime.py`. No path under `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/`,
  `model_lab/integration/`; root `.gitignore` unchanged. Binary additions: 7 PNG screenshots only. No secret pattern in
  the added lines.
- Frozen check (`scripts/ws_frozen_check.py` at `522939c`, `evidence/ws_frozen_check_522939c.json`): 121/121 Phase 1
  checkpoint files byte-identical, no protected path changed.
- Other threads: the Text Intelligence reconciliation branch `integration/ti-on-ws-hardening-20261009` is local to its own
  worktree and was not touched or merged. No other worktree, branch or window was modified.

## 3. Validation (isolated gate tree `C:\Users\cheta\Development\uri-ws-gate4`)

Materialized from `522939c` with `scripts/oi_materialize_test_runtime.py --exclude-oi-tests` (receipt
`evidence/uri-ws-gate4_MATERIALIZATION_RECEIPT.json`: HEAD `e8e3b65`, overlay `759d0d4` 273 paths, candidate head `522939c`).
Accepted fixtures: `<gate>\evidence` copied from `uri-ws-gate3\evidence` without that tree's own chain outputs;
`work\c1\checkpoints` copied from the canonical Phase 1 worktree `.codex\worktrees\uri-phase1-integration\uri-agent`
(883 files, SHA-256 list `evidence/phase1_checkpoint_fixtures_sha256.txt`, byte-identical to the copy). An idle Ollama
(no model loaded) listened on 11434, as in the accepted baseline. These two items were the environment causes of the
two outcome changes in the interrupted hardening run 1.

Chain: `scripts/phase2close_chain.py <gate>\evidence\canon_chain --no-native --only phase2,authority,phase1-full,phase1-scope,residue`
(14:24-14:47), verdict **ALL_PASS**, exit 0 (`evidence/chain_summary.json`, `evidence/canon_chain_console.log`).

| Gate | Result |
|---|---|
| phase2 | PASS: 486 passed, 0 failed, 2 skipped |
| authority | PASS: 134 passed, 0 failed |
| phase1-full (the interrupted gate) | **PASS**: 2,676 passed / 11 failed / 11 skipped; outcome identity against the accepted baseline: 2,698 ids, missing = added = outcome_changed = ∅; same failure set as the accepted log; JUnit integrity ok for run and baseline; baseline pins hold; `OLLAMA_BASE_URL=http://127.0.0.1:9` |
| phase1-scope | PASS: outside Phase 2 scope = ∅, importers of Phase 2 = ∅, 98 frozen files byte-identical, runner argv equals the accepted one; identical result to the hardening gate tree `uri-ws-gate3` |
| residue | PASS (nothing to remove) |

The 11 Phase 1 failures are the accepted baseline failures (pre-existing, unchanged), not regressions.

Further suites on the candidate worktree at `522939c`:

| Suite | Result |
|---|---|
| OI + WS Python (`pytest tests/oi tests/ws`) | 226 passed, 20 skipped (all skips opt-in live tests: `URI_OI_LIVE`, `URI_WS_LIVE`, `URI_WS_RESTART`) — `evidence/pytest_oi_ws_522939c.txt` |
| Flutter full suite (`uri_ui`, `flutter test`) | 313 passed, 3 skipped — `evidence/flutter_full_522939c.txt` |

Reused, not repeated (GPU-heavy, code unchanged since): live worker/UI runs with Runtime v1 READY from the hardening
phase (`hardening/evidence/worker_live_20261009-081634.json`, `hardening/evidence/ws_ui_live_hardening.json`).
Not run: chain steps flutter (covered above), bridge, native and native-worker (no change to those packages; native
needs a client-profile Codex login, PA-8/9).

## 4. GPU coordination

The chain held the machine-wide lease (`purpose regression_chain`, holder pid 12796) for its whole run, through a
separate holder process so that the test processes ran outside any extra job object, exactly as in the accepted runs.
History (`evidence/gpu_lease_history_canonical_chain.jsonl`): the stale record of the WS Brain host that died in SAFE-1
hang 3 was recovered (`STALE_RECOVERED`), a 0.1 s probe lease (label `test`, pid 9700) checked the CLI after a first
launch failed on a relative executable path (`WinError 2`, nothing ran), the chain lease was acquired at 14:24 and released at 14:47, and another
session's queued benchmark (companion-voice contention check, `--wait 14400`) acquired the lease 0.5 s after the
release. No Brain was loaded by this integration.

## 5. Independent audit status

Code: Codex hardening round 10 ACCEPT WITH FINDINGS at `9ae28f4`, findings repaired; documentation round 2 ACCEPT WITH
FINDINGS at `c32933e`, repaired in `522939c` (see `../WS_INDEPENDENT_AUDIT.md`). This integration adds no code. The
phase1-full gate that blocked integration was re-established by this session's own run; it is not a Codex claim.

## 6. Limitations carried (non-blocking)

SAFE-1 (historical; standalone stability test waived by the owner), CUT-1 (no production cutover; legacy `\URIServer`
on 8000 untouched), GPU-2/3/4, R-SHUT, R-STALL, L-MUTEX, L-CLASSIC, L-RT, L-SIM, L-PLAN, OI-SEC-1, CLOUD, MD-1, L-MD
partial — as listed in `../WS_REMAINING_LIMITATIONS.md`.

## 7. Integration

Fast-forward `integration/git-sync-20261008` from `037229c` to the integration commit, normal push (no force), then
verification through a fresh clone. Production deployment and cutover are not authorized and were not done.
