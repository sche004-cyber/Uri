# URI Runtime Build, Start and Rollback Runbook — 2026-10-08

Scope: how to rebuild the authoritative URI runtime from Git, how to start it once the owner approves cutover, and
how to roll every step back. Steps marked **RED** need explicit owner approval. Nothing in this runbook has been
executed against the live PC except the GREEN steps in section 1 (materialization and gates).

## 1. Rebuild the runtime checkout from Git (GREEN, reproducible)

```powershell
git -c core.longpaths=true clone --no-checkout https://github.com/sche004-cyber/Uri.git C:\URI\runtime-src
cd C:\URI\runtime-src
git config core.autocrlf false; git config core.longpaths true
git checkout --detach e8e3b65
git show origin/integration/git-sync-20261008:docs/governance/consolidation/RUNTIME_OVERLAY_PHASE2OQ_G.txt |
  Set-Content -Encoding ascii ..\overlay.txt          # not '>' (UTF-16 in Windows PowerShell 5.1)
git checkout 759d0d4 --pathspec-from-file=..\overlay.txt
git reset -q                                          # HEAD stays e8e3b65; accepted files are the overlay
```

Verify before use:
1. `git rev-parse HEAD` prints `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
2. `git status --porcelain` lists only overlay paths.
3. Frozen files: re-hash the 121 files of `work/c1/checkpoints/final-closure-20261005-phase1.zip`
   (`31a34dcb…98cf7`, also in Git at `925ad45`) against the checkout; zero differences.
4. Phase 2 files: hash the 154 tree files of `docs/evidence/phase2/phase2oq-candidate-20261008-g.zip`
   (`0b49d86d…c4cd`) against the checkout; zero differences except the three post-acceptance documents
   (`PHASE2OQ_REPORT.md`, `PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `URI_DEVELOPMENT_TODO.md`, from `759d0d4`).
5. Interpreter: create `.venv` from Python 3.13.15 and install the pinned dependencies (the accepted runs used a
   copy of the Phase 2 worktree `.venv`; a clean `pip install` from the repository requirements is not yet
   separately qualified — see the outstanding list, item R-3).

The candidate checkout already built this way is `C:\Users\cheta\Development\uri-canonical-runtime-candidate`.

## 2. Regression gates (GREEN)

The accepted chain (`scripts/phase2close_chain.py`) expects the evidence tree as a sibling `..\evidence`
directory. Lay out a gate workspace:

```
<gate>\uri-agent\   materialized checkout (section 1) + .venv + work\c1\checkpoints (from the Phase 1 worktree)
<gate>\evidence\    copy of docs\evidence\phase2\ from the canonical branch
```

Run with Ollama unreachable for the Phase 1 suite (the chain sets `OLLAMA_BASE_URL=http://127.0.0.1:9` itself):

```powershell
cd <gate>\uri-agent
.venv\Scripts\python.exe -I scripts\phase2close_chain.py <gate>\evidence\phase2oq\chain_<name>
```

Pass criteria are the chain's own: Phase 2 suites exit 0; authority 134 passed; Phase 1 full = the pinned
per-test outcome baseline (2,698 IDs, 11 known failures, same IDs); Flutter all passed; bridge 10/10; native
Codex lifecycle `SETTLED_VERIFIED`; native worker refuses `HARNESS_NOT_USABLE` without a client-profile login.

## 3. Start the authoritative runtime (RED — cutover, not authorized)

Order (from `URI_UNIFIED_CONSOLIDATION_PLAN.md` section 7, unchanged):
1. P-2 `scripts\uri_containment.ps1 -Apply` (exports and disables `\URIServer`, moves the two `URI.lnk` files).
2. P-3 stop the legacy server process tree on port 8000 at a time the owner chooses.
3. P-4 choose install dir, state root and port; provision with `scripts/provision_uri_server.py` and
   `scripts/provision_uri_client.py` into fresh, ACL-restricted roots. No legacy data is imported.
4. P-5 `scripts\uri_authorized_start.ps1 -Action start -ServerManifest <manifest>`; then
   `python scripts\uri_runtime_authority_check.py --strict` must report CLEAN.
5. Runtime v1 (resident Brain) is **not** part of this start: it is not wired into the Core composition
   (Operational Intelligence milestone). Starting `llama-server` alone gives no URI capability.

## 4. Rollback

| Step undone | How |
|---|---|
| Runtime checkout | delete the materialized checkout; rebuild from section 1 (Git is the source) |
| P-5 start | the frozen C1 launcher has no stop action (`validate`/`start`/`status` only): stop the server process tree it reports in `status` (by PID); there is no automatic stop tool yet (outstanding item R-4) |
| P-4 provisioning | delete the fresh state roots (no legacy data was touched) |
| P-3 legacy stop | `Start-ScheduledTask \URIServer` or log on again (task still exists until P-2 is undone or kept) |
| P-2 containment | `scripts\uri_containment.ps1 -Restore` (re-imports the exported task XML, moves the shortcuts back) |
| Phase 1 file set | `scripts/phase1_offline_rollback.py` (frozen C7 offline rollback) |
| Git | nothing was rewritten; every accepted state has a commit and a tag; old tips remain reachable |
| Runtime v1 | flags and hashes in `model_lab/integration/local_brain.json`; binaries and models on `D:\uri-model-lab` (pinned SHA-256 re-verified 2026-10-08) |
| Secret ACL hardening (CONS-13) | `icacls <dir> /restore <saved acl file>` per entry in `uri-canonical-evidence\acl\` |
