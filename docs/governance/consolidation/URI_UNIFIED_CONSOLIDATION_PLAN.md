# URI Unified Repository, Runtime & PC Consolidation Plan — 2026-10-08

Owner of this plan: consolidation session (Claude), 2026-10-08. Status: **candidate built and verified; promotion,
live-PC containment and deletions await owner approval.** This plan does not create a milestone and does not
replace `docs/plans/URI_DEVELOPMENT_TODO.md`, which remains the single ledger (consolidation items CONS-1..CONS-14
were added there).

## 1. Acceptance criteria (set before implementation)

1. One proposed authoritative development baseline, with every accepted artifact traceable to its acceptance.
2. Every accepted artifact recoverable from a fresh GitHub clone, byte-verified.
3. Every URI-capable runtime path on the PC enumerated and classified; none unaccounted.
4. A machine-readable authority manifest and an automated check that detects obsolete or unknown runtimes.
5. A start gate that refuses to start the authoritative runtime while an unauthorized one is active.
6. No frozen Core file changed; no destructive or RED action taken without approval.
7. No credential, token, private database or recording in Git; secret exposure on the PC reported and contained.
8. Applicable regression gates re-run on the materialized candidate and compared with the accepted baselines.
9. Adversarial attempts to activate obsolete components, with results.
10. A clear owner-decision list and a reversible promotion and retirement procedure.

## 2. Authoritative sources used

Frozen Phase 1 checkpoint `31a34dcb…f7`; Runtime v1 freeze record; Phase 2 accepted candidates `9a0be52c…` (ops)
and `fcd0d72e…` (closure); GitHub backup (`uri-repo integration/git-sync-20261008` `f8de153`, verified by fresh
clone); `GIT_SYNC_AUDIT.md`; `IMPLEMENTATION_STATUS_LEDGER.md`; Phase 0 consolidation plan and preservation manifest;
`C7_CUTOVER_REQUIREMENTS.md`; `PHASE2CLOSE_C7_READINESS.md`. Every claim reused from these was re-checked against the
machine or the repository where possible (see the verification report).

## 3. Development history in one view

1. **Legacy line** to ARN.1 (`e8e3b65`, 2026-09-20): single checkout, server + desktop + `uri_workspace` together.
2. **Desktop/V1 line** (2026-09-21 → 10-03, `uri-repo`): M33–M39, URI-Memory, Edge, harness capsules, Office,
   INT-ARN-1, desktop features; frozen M36–M38 at `bd7c450`; installed at `uri-m37-m39-integration`.
3. **Side lines**: dynamic planning (frozen slice 1), dictation, harness-first, edge pair, `_V1` harness/voice
   (superseded base), harness console, intent workflow (superseded).
4. **Phase 0** (2026-10-05): inventory; recommends `e8e3b65` as accepted Core anchor, desktop/V1 as donors.
5. **Phase 1** C1–C7 on `e8e3b65`: client/server separation, launcher authority, client-owned state, client-local
   harnesses, intent discovery + RAR, UI contract, offline rollback → **frozen** 2026-10-05.
6. **Runtime v1** (resident Brain) frozen 2026-10-07; not yet wired into the Core composition.
7. **Phase 2** supervisor, bridge, native qualification, composition, UI/ops, closure → accepted 2026-10-08;
   operational qualification continuing in the Phase 2 worktree (other session).

## 4. Consolidated target structure

- **Repository:** `sche004-cyber/Uri`. **Canonical line:** Core lineage, proposed name `main`
  (`URI_CANONICAL_BRANCH_DECISION.md`). Accepted anchors tagged `accepted/*`, donor lines `donor/*`.
- **Runtime:** materialized checkout (§5) started only through the frozen C1 launcher behind
  `scripts/uri_authorized_start.ps1`, on a fresh provisioned state root and a non-legacy loopback port.
- **Authority:** `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json` + `scripts/uri_runtime_authority_check.py`.
- **Containment classes on the PC:** ACTIVE/AUTHORITATIVE (canonical dev checkout, materialized runtime checkout,
  Runtime v1 binary root); PRESERVED/DONOR-ONLY (Phase 1 integration, Phase 2 dev, desktop integration, `_V1`,
  harness console, intent discovery, dictation, edge experiments, batch candidate, m33 worktrees, vault);
  QUARANTINED/UNTRUSTED (legacy master `uri-agent`, `.tmp_m33` worktree, NVMe model copy, `%LOCALAPPDATA%\URI`).
  Containment works on execution (start gate + checker + task/shortcut actions), configuration discovery (forbidden
  entrypoints, shared UI preferences flagged), service activation (scheduled task), environment (no URI env vars;
  C1 sanitizes environment and pins interpreter), and data access (fresh ACL-restricted state roots; legacy data
  never imported; secret ACL hardening) — not on folder names alone.

## 5. Runtime materialization procedure

The frozen `runtime_identity.py` requires `git HEAD == e8e3b65`. To produce the authoritative runtime checkout from
the canonical branch:

```powershell
git -c core.longpaths=true clone --no-checkout https://github.com/sche004-cyber/Uri.git <runtime-dir>
cd <runtime-dir>; git config core.autocrlf false
git checkout --detach e8e3b65
git fetch -q origin <canonical-branch>   # the overlay list lives on the branch tip, not at <accepted-commit>
git show FETCH_HEAD:docs/governance/consolidation/RUNTIME_OVERLAY_PHASE2OQ_G.txt | Set-Content -Encoding ascii ..\overlay.txt   # not '>' (UTF-16 in PowerShell 5.1)
git checkout <accepted-commit> --pathspec-from-file=..\overlay.txt
git reset -q          # HEAD stays e8e3b65; accepted files become the uncommitted overlay
```

`<accepted-commit>` today is `759d0d4` (Phase 2 operational-qualification candidate -g bytes, accepted by Codex OQ
round 7, plus its 14:42 post-acceptance records). Since the consolidation and sync records now precede it in history,
the overlay is an explicit committed list, `RUNTIME_OVERLAY_PHASE2OQ_G.txt` (273 files: every path changed from
`e8e3b65` by the Phase 1 freeze and the Phase 2 commits, excluding `model_lab/`, `docs/evidence/`, the git-sync
records and the consolidation tooling). Materialized from Git on 2026-10-08, those 273 files are byte-identical to
the live Phase 2 worktree on which chain10 was accepted. The previous overlay (`2325ad7`, 256 files, closure -f) is
superseded. The consolidation tooling runs from the canonical development checkout, never from the runtime checkout.

## 6. Work performed in this consolidation (GREEN, reversible)

1. Fresh GitHub clone → `C:\Users\cheta\Development\uri-canonical-candidate` (also the reproducibility test).
2. Materialized runtime checkout → `C:\Users\cheta\Development\uri-canonical-runtime-candidate`.
3. Authority manifest, checker (+66 adversarial tests), start gate, containment script (plan-only default).
4. PC audit; ACL hardening of 33 secret files; git exclusion rules for runtime state.
5. Local tags `accepted/*` and `donor/*` in the candidate clone.
6. Regression gates on the materialized runtime; results in `URI_CLEANUP_VERIFICATION_REPORT.md`.
7. Documents in `docs/governance/consolidation/` and consolidation items in `docs/plans/URI_DEVELOPMENT_TODO.md`.

## 7. Owner-gated steps (RED) in order

| Step | Action | Reversible by |
|---|---|---|
| P-1 | Approve the canonical decision; push `canonical/candidate-20261008` + tags (new refs, no force) | delete the new refs |
| P-2 | Run `scripts/uri_containment.ps1 -Apply` (disable `\URIServer`, move `URI.lnk` ×2) | `-Restore` |
| P-3 | Stop the running legacy server (PID tree under the task) at a convenient time | re-enable task / log on |
| P-4 | Choose the authoritative install directory, state root and port; provision with `scripts/provision_uri_server.py` / `provision_uri_client.py` | delete the fresh roots (no legacy data touched) |
| P-5 | Start through `scripts/uri_authorized_start.ps1 -Action start -ServerManifest <manifest>`; verify `--strict` checker CLEAN | stop server |
| P-6 | Create `main` + set default branch on GitHub | change default back |
| P-7 | Per item, with tested recovery: archive-tag-then-delete historical branches; remove obsolete worktrees (`.tmp_m33`, intent-discovery, …); delete NVMe model copy | archive tags / preserve branches / D: copy |
| P-8 | C6 parity work before retiring the installed desktop UI; C7 cutover per `C7_CUTOVER_REQUIREMENTS.md` | C7 rollback |

## 8. What this plan deliberately does not do

It does not merge the desktop line into the Core, does not modify frozen Core files (including the
`HEAD == e8e3b65` coupling), does not import legacy user data, does not stop or edit the Phase 2 session's work,
and does not declare cutover. Those are listed as owner decisions in the TODO ledger.
