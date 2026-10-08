# OI source baseline and isolation proof

## 1. Baseline (verified 2026-10-08, start of the OI session)

| Item | Value | How verified |
|---|---|---|
| Repository | `https://github.com/sche004-cyber/Uri.git` (local remote name `uri-repo`; object store shared with `C:\Users\cheta\Development\uri-agent`) | `git remote -v` |
| Branch | `integration/git-sync-20261008` | `git ls-remote uri-repo integration/git-sync-20261008` |
| Commit | `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` ("docs(consolidation): GitHub publication receipt …") | remote tip equals the mandate's commit after `git fetch` |
| Not used | local ref `integration/git-sync-20261008` = `f8de153` (stale, pre-round-2) and `master` (`e8e3b65`, legacy line) | `git rev-parse` |
| OI branch / worktree | `phase/operational-intelligence` at `C:\Users\cheta\Development\uri-operational-intelligence`, created with `git worktree add -b phase/operational-intelligence … 037229c` | `git log` |

Runtime v1 artifacts (read-only, `D:\uri-model-lab`): all five pinned SHA-256 values re-verified by full hash on
2026-10-08 (server binary, `ggml-vulkan.dll`, model 13.68 GB in 87.5 s, mmproj, MTP draft): `work/oi/state/artifact_hash_cache.json`.

## 2. Ownership boundaries observed (nothing modified)

| Location | Owner | OI action |
|---|---|---|
| `C:\Users\cheta\Development\uri-ui-phase` (`phase/ui-living-companion`) | UI / Living Companion session | none; it moved to `d0a3751` with its own uncommitted work during this session |
| `C:\Users\cheta\Development\uri-canonical-candidate` (`canonical/candidate-20261008` @ `037229c`) | consolidation | none (clean, 0 porcelain entries) |
| `C:\Users\cheta\Development\uri-canonical-runtime-candidate` (e8e3b65 + overlay) | consolidation | read only: its `.venv` was copied as the pinned interpreter |
| `.codex\worktrees\uri-phase1-integration`, `.codex\worktrees\uri-phase2a`, other `.codex` worktrees | Phase 1 / Phase 2 / audits | none |
| Legacy server `\URIServer` (127.0.0.1:8000, pid 13660), Ollama (11434, no model loaded) | live PC | never contacted, stopped or reconfigured |
| Windows services, scheduled tasks, shortcuts, production databases | owner | none |

## 3. Frozen / accepted code untouched

`git diff --name-status 037229c HEAD` on the OI branch: every entry is `A` (added) except one `M`: `.gitignore`
(one line `/work/oi/` so OI runtime state is never committed). Added paths are only `uri_operational_intelligence/`,
`tests/oi/`, `scripts/oi_materialize_test_runtime.py` and `docs/operational_intelligence/`. No file under `uri_core/`,
`uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `uri_ui/`, `model_lab/` or `scripts/` (other
than the one new script) changed. The final ledger (`OI_PLAN_AND_STATUS_LEDGER.md`) repeats this check on the final
commit.

## 4. Work created outside the OI worktree (disclosed)

| Path | What | Why | Removal |
|---|---|---|---|
| `C:\Users\cheta\Development\uri-oi-testrt` | detached worktree at `e8e3b65` + Phase 2 OQ overlay + OI files + venv copy | frozen `runtime_identity.py` only runs the real paired Core when `HEAD == e8e3b65` (CONS-7); live Core tests need such a tree | `git worktree remove --force <path>` |
| `C:\Users\cheta\Development\uri-oi-gate\uri-agent` (+ `..\evidence`) | same, without `tests/oi` | regression gate: accepted Phase 1/2 gates must collect exactly their accepted test sets in the presence of the OI package | same |
| `.git/worktrees/*` metadata in the shared object store | worktree registrations | inherent to `git worktree add` | removed with the worktrees |

These are new directories; no existing file outside the OI worktree was written. They are disposable test scaffolding,
not runtimes, and hold no production state.

## 5. Runtime and GPU use (authorized local inference benchmarks)

Runtime v1 was started only through `uri_operational_intelligence.host` with the exact frozen argv on its configured
port 18470 (and once, for the MTP comparison only, a separate contained instance on 18472 without the four MTP
arguments while 18470 was stopped). Every instance ran in a kill-on-close Job Object and was stopped with the job
confirmed empty (`STOPPED_CLEAN True`). `local_brain.json` and every Runtime v1 artifact were only read.
