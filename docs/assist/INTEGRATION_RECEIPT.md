# Integration receipt — W1, A0, REA discovery (2026-10-10)

**No milestone was integrated into the canonical branch.** Canonical `integration/git-sync-20261008` remains at
`ffdf534` (verified with `git ls-remote` on 2026-10-10). Governance requires an independently accepted candidate
(Codex) and passing combined gates before controlled integration; Codex was not available, so the work is delivered
as a reviewable candidate on the session branch only.

## 1. Repository, baseline, branches, worktrees

| Item | Value |
|---|---|
| Repository / remote | `github.com/sche004-cyber/Uri` (`origin`) |
| Canonical baseline | `ffdf534386a3d40cf9e1646ef1080bee28dd3aa9` = `integration/git-sync-20261008` = `integration/final-qualification-20261010` |
| Session checkout (integration carrier) | `/home/user/Uri`, branch `ccr-cab5ed06-9hwyc4` (the only branch this session may push) |
| W1 worktree | `/home/user/uri-wt/w1`, branch `milestone/w1-web-intelligence-20261010`: `885483b` → `db7c02c` (local) |
| A0 worktree | `/home/user/uri-wt/a0`, branch `milestone/a0-assist-foundation-20261010`: stacked on W1; `f140506`, `be5bc6c`, repair `1844b48`, docs (local) |
| REA worktree | `/home/user/uri-wt/rea`, branch `research/rea-discovery-20261010`: `cea2a77` (local; research only) |
| Delivery | the milestone and research branches are merged into `ccr-cab5ed06-9hwyc4` with merge commits (no rebase, no force) and pushed there |

## 2. Changed files (vs `ffdf534`)

- New packages: `uri_web/` (15 files), `uri_assist/` (10 files incl. `browser_extension/`).
- New tests: `tests/web/` (5), `tests/assist/` (4 + 3 fixtures), `uri_ui/test/living/assist_mode_test.dart`.
- Existing, non-frozen files edited (additive): `scripts/run_uri_integrated_worker.py` (dispatch lines, package list),
  `scripts/oi_materialize_test_runtime.py` (exact new paths), `tests/phase2a/test_frozen_core.py` (exact
  `ALLOWED_NEW` paths, CRLF preserved; WS-D3 precedent), `uri_ui/lib/living/{integration/oi_conversation.dart,
  living_app.dart, living_scope.dart, presentation/living_shell.dart, presentation/presentation_controller.dart,
  screens/companion_mode_view.dart, screens/dashboard_mode_view.dart}`; new `uri_ui/lib/living/assist/*` (3).
- Docs: `docs/assist/**`; research: `research/rea_discovery/**`.
- Frozen/protected paths changed: **none** (`ws_frozen_check` protected list; Phase 1 zip byte check BLOCKED here).

## 3. External dependencies

| Item | Where | Runtime dependency? |
|---|---|---|
| httpx (already used by `uri_operational_intelligence`, undeclared in `requirements.txt` before this work) | W1 | yes, pre-existing |
| Pillow (`requirements.txt`) | A0 vision preparation | yes, pre-existing |
| No new Python, Dart or npm runtime dependency | — | — |
| Test-only: Playwright 1.56 + Chromium 1194 (preinstalled in the container) | Chromium tests skip ("BLOCKED") when absent | no |
| Dev-only in `/tmp/claude-0`: a Python venv (requirements + pytest), Flutter 3.47.7 SDK, `graphifyy` (installed into the venv to check whether `graphify update` was usable; not run against the repo) | container | no |
| Licence metadata: wheels downloaded with `pip download --no-deps` to `/tmp/claude-0/lic`, read as zip metadata, never installed or executed | container | no |

## 4. Resource use and GPU

No GPU in the container; the GPU lease was not needed and not touched. No process belonging to another thread was
started, stopped or signalled. Network: pypi.org (direct) and the search/social/public hosts listed in
`evidence/w1_live_proxy_egress_denied.json` (refused by the organisation's egress policy; not retried around it).

## 5. Containment controls actually enforced

| Control | Mechanism | Verified |
|---|---|---|
| No access to the owner's PC, legacy server (`\URIServer`, port 8000), production config, other PC worktrees, GPU | isolated cloud container | by construction |
| No edits to the session checkout or the `uri-agent` repository through file tools | harness deny rules `Edit(//home/user/Uri/**)`, `Edit(//home/user/uri-agent/**)` in `~/.claude/settings.json` | an Edit attempt was refused by the harness |
| No `npx`, global npm installs, `pip install`, `git config --global`, force pushes, pushes to `integration/*`, `milestone/*`, `research/*`, `master` | harness Bash deny rules (prefix match) | an `npx` call was refused by the harness |
| Writes limited to worktrees and `/tmp/claude-0` | worktrees + rules above | partial (see exceptions) |

## 6. Containment exceptions (recorded, not hidden)

1. **Before the containment instruction arrived**, W1 and A0 (`885483b`, `74b24eb`, `a0c7bbe`, `ddfa530`) were developed
   in the session checkout `/home/user/Uri` on `ccr-cab5ed06-9hwyc4` and pushed there. They were then re-homed onto
   the milestone branches/worktrees above (same content; A0 rebased onto the repaired W1). Canonical was never touched.
2. `git config --global --add safe.directory /tmp/claude-0/flutter` was run once (container-global git config, to
   let the Flutter SDK run as root), before the deny rule existed.
3. The Bash deny rules are **prefix rules**: a differently spelled command (for example `python -m pip …`) would not be
   matched. They were respected, not circumvented, but they are not a complete sandbox; the container is the real
   boundary.
4. Milestone and research branches are **local only** (the session may push only its designated branch); their
   commits reach the remote through merge commits on `ccr-cab5ed06-9hwyc4`.
5. `graphify update .` was not run: canonical carries no `graph.json`, and running it would rewrite tracked marker
   files with container paths.

## 7. Gates on the candidate (A0 tip `1844b48`, which contains W1)

| Gate | Result |
|---|---|
| Python ws/oi/a2ui/web/assist (Linux) | 772 passed, 24 skipped; failure set identical to baseline (0 new, 0 fixed) |
| `tests/web` + `tests/assist` | 215 passed |
| Flutter full | 526 passed, 5 skipped, 1 failed (pre-existing `reference_render_test`) |
| Frozen check | protected paths unchanged; Phase 1 zip check BLOCKED (PC only) |
| Independent review | interim Claude review ACCEPT WITH FINDINGS, repaired (`INTERIM_REVIEW.md`); **Codex: NOT PERFORMED** |
