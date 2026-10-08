# UI Living Companion phase: isolation evidence

Date: 2026-10-08. Author: Claude (UI phase session). Status: RECORDED, re-verified at each commit of this phase.

## Baseline selection

| Item | Value | How verified |
|---|---|---|
| Canonical candidate branch (GitHub) | `integration/git-sync-20261008` | `git ls-remote uri-repo integration/git-sync-20261008` -> `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` |
| Local consolidation clone tip | `C:\Users\cheta\Development\uri-canonical-candidate`, branch `canonical/candidate-20261008` @ `037229c` | `git -C ...uri-canonical-candidate log --oneline -3` (read-only) |
| Shared repo's own `integration/git-sync-20261008` | `f8de153` (older than the published tip; lacks the Phase 2 OQ `-g` import, 5 `uri_ui/lib` files differ) | `git diff --stat f8de153 037229c -- uri_ui` in the clone (read-only) |
| **Chosen UI baseline** | **`037229c1fc04eadc6a2e42e92e6ef0d12520d3fe`** (published, GitHub-verified consolidation tip) | SHA equality between `ls-remote` and the clone |
| Accepted tags reachable from the baseline | `accepted/phase1-core-freeze-31a34dcb`, `accepted/runtime-v1-freeze-20261007`, `accepted/phase2-ops-r6-9a0be52c`, `accepted/phase2-closure-f-fcd0d72e`, `accepted/phase2-oq-g-0b49d86d`, `accepted/m36-m38-closed-frozen-bd7c450`, `accepted/dynamic-planning-slice1-565eae8` | `git tag` in the clone |

Why not `62d564c` (`codex/antigravity-harness-recon`, the session's starting worktree): it is a provisional M36-M38 line with a large uncommitted working set, not an ancestor of the published candidate (`git merge-base --is-ancestor` -> no), and its `uri_ui` lacks the independently accepted supervised execution screen/runtime that the next-phase UI readiness document (`docs/architecture/PHASE2CLOSE_UI_READINESS.md`) names as the interface the Orb must read.

## How the baseline entered the shared repository without touching shared refs

```
git fetch --no-tags C:/Users/cheta/Development/uri-canonical-candidate \
  canonical/candidate-20261008:refs/ui-baseline/canonical-candidate-20261008
```

* Source: the local consolidation clone (path URL, not a configured remote), so no remote-tracking ref was updated.
* Destination: a private ref namespace `refs/ui-baseline/*`. No branch, tag, or `refs/remotes/*` entry changed.
* Post-check: `git rev-parse uri-repo/integration/git-sync-20261008 integration/git-sync-20261008` -> both still `f8de153`.

## Worktree and branch

```
git worktree add -b phase/ui-living-companion C:/Users/cheta/Development/uri-ui-phase \
  refs/ui-baseline/canonical-candidate-20261008
```

| Check | Result |
|---|---|
| New worktree HEAD | `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` |
| New worktree branch | `phase/ui-living-companion` (local only, never pushed by this phase) |
| Starting worktree after the operation | `C:\Users\cheta\Development\Uri\_V1` still `62d564c` on `codex/antigravity-harness-recon`, working set untouched |
| Consolidation clone after the operation | unchanged (`037229c`, `canonical/candidate-20261008`) |

## Physical separation from active worktrees (from `git worktree list`, 2026-10-08)

| Worktree | Path | Role | Touched by this phase |
|---|---|---|---|
| main checkout | `C:\Users\cheta\Development\uri-agent` (master `e8e3b65`) | frozen Core base | no |
| Phase 1 integration | `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent` | Phase 1 / Runtime v1 research (`model_lab`) | no |
| Phase 2 | `C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent` | Phase 2 supervisor bridge | no |
| Consolidation candidate | `C:\Users\cheta\Development\uri-canonical-candidate` (separate clone) | published candidate | read-only (`git log`, `git diff`, `git show`, fetch source) |
| Runtime candidate | `C:\Users\cheta\Development\uri-canonical-runtime-candidate` | materialized runtime | no |
| Batch candidate | `C:\Users\cheta\Development\uri-batch-candidate` | M36-M38 | no |
| Session start | `C:\Users\cheta\Development\Uri\_V1` | provisional harness recon | no (read-only inspection) |
| **UI phase** | **`C:\Users\cheta\Development\uri-ui-phase`** | this work | yes (only here) |

## Modified-file boundary for this phase

Allowed to change (inside the UI worktree only):

* `uri_ui/lib/**` new files under `lib/living/`, `lib/companion/`, `lib/theme/glass_theme.dart`, `lib/main_living.dart`, plus additive edits to `lib/theme/uri_theme.dart` (new palette/extension) and `pubspec.yaml` (shader asset).
* `uri_ui/shaders/**`, `uri_ui/test/living/**`, `docs/ui_phase/**`, `docs/design_library/approved|rejected/*living*`.

Never changed by this phase (verified by `git status` / `git diff --stat` at each commit, recorded in `UI_TEST_EVIDENCE.md`):

* `uri_core/**`, `uri_supervisor/**`, `uri_supervisor_bridge/**`, `uri_v1/**`, `uri_workspace/**`, `uri_harness_adapters/**`, `scripts/**`, `model_lab/**`, `tests/**`, `docs/governance/**`, `docs/evidence/**`, Windows startup tasks, shortcuts, port 8000, the production database, any launcher.
* Existing `uri_ui/lib/screens/**`, `uri_ui/lib/services/**`, `uri_ui/lib/widgets/**` files (the Hybrid UI and the accepted supervised screen) stay byte-identical; the living experience is additive.

## Baseline health in the UI worktree (before any change)

| Command | Result |
|---|---|
| `flutter --version` | Flutter 3.47.2 stable, Dart 3.13.2 (Impeller default on Windows desktop since 3.47) |
| `flutter pub get` | OK |
| `flutter analyze` | 2 pre-existing infos (`providers_screen.dart:730` deprecated `value`, `chat_supervised_handoff_test.dart:5` unnecessary import), 0 errors |
| `flutter test` | `+205 ~2: All tests passed!` |

## Standing prohibitions honoured

No merge, rebase, cherry-pick, push, tag, branch deletion, reset, or stash on any shared ref. The live `\URIServer` scheduled task, port 8000 ownership, `URI.lnk` shortcuts and `%APPDATA%\com.example\uri_ui\shared_preferences.json` were not touched. (Note: all `uri_ui` builds share that preferences file; `main_living.dart` therefore namespaces its own keys under `uri.living.*` and never writes the Hybrid app's keys.)
