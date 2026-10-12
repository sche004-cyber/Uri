# Working System Integration — provenance and acceptance evidence of the inputs (AC-1)

Verified 2026-10-08 in this session from the shared object store (`C:\Users\cheta\Development\uri-agent\.git`) and
from GitHub (`git ls-remote uri-repo`).

## 1. Baseline

| Item | Value | How verified |
|---|---|---|
| Published baseline | `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` = GitHub `sche004-cyber/Uri` `integration/git-sync-20261008` | `git ls-remote uri-repo refs/heads/integration/*` |
| Local ref of the same name | `f8de153` (stale, pre-round-2). Not used | `git rev-parse` |
| Accepted tags present locally and on GitHub | `accepted/phase1-core-freeze-31a34dcb`, `accepted/phase2-closure-f-fcd0d72e`, `accepted/phase2-ops-r6-9a0be52c`, `accepted/phase2-oq-g-0b49d86d`, `accepted/runtime-v1-freeze-20261007`, `accepted/m36-m38-closed-frozen-bd7c450`, `accepted/dynamic-planning-slice1-565eae8` | `git tag -l`, `git ls-remote uri-repo refs/tags/accepted/*` |
| Frozen Phase 1 files at the baseline | 121 checkpoint files byte-identical to `final-closure-20261005-phase1.zip` (SHA-256 `31a34dcb…98cf7`) | `scripts/ws_frozen_check.py` on a clean checkout of `037229c` |

## 2. Candidates

| Candidate | Branch / tip | Descends from `037229c` | Commits | Last independent verdict (as recorded on the branch) | Clean worktree |
|---|---|---|---|---|---|
| Living Companion UI | `phase/ui-living-companion` `569cf7c62d05…` (code last changed `838d1dd`) | yes | 10 | Codex round 6 on `4aef264`: **ACCEPTED WITH FINDINGS**; both findings were wording and evidence items, fixed in `569cf7c` (`docs/ui_phase/UI_TEST_EVIDENCE.md` §6) | yes |
| Operational Intelligence | `phase/operational-intelligence` `9306dc11317d…` | yes | 14 | Codex round 7 on `85d1ccf`: **ACCEPT WITH FINDINGS (development candidate)**; the two findings (a test-coverage item and a wording item) were fixed in `9306dc1` without another round (`docs/operational_intelligence/OI_INTEGRATION_READINESS.md` §2) | yes |

The two candidates change no path in common (`comm` of their name-only diffs against `037229c`).

**What "accepted" means for each input.** Both verdicts accept a development candidate, not an integration. The
OI readiness record marks integration NOT READY until four owner decisions are made. Those decisions were made in this
session (WS-D1..WS-D4, `WS_BLUEPRINT.md` §1). The mandate itself settles three UI owner items: the published line
`037229c` is the target (P2-6), the current orb stays provisional (orb choice), and Living becomes the default shell
(WS-D4).

**Limit of this verification.** The Codex verdicts above are read from the committed records on each branch. The raw
Codex outputs of those rounds were not re-inspected. This does not affect the integration verdict, because the
integrated candidate gets its own independent Codex review (AC-15).

## 3. Findings on the inputs

| ID | Finding | Disposition |
|---|---|---|
| FB-1 | The OI candidate (`04ef4f0`) edited the root `.gitignore`, which is one of the 121 frozen Phase 1 checkpoint files. Its isolation record called it the only modified path, but did not identify it as frozen | Repaired in `385250f`: frozen bytes restored; OI state ignored by a new tracked `work/oi/.gitignore`. `ws_frozen_check.py` now reports 121/121 byte-identical |
| PV-1 | The OI isolation record lists `uri_ui/` as untouched, which is true for the OI branch. UI changes come only from the UI candidate and this integration | none needed |

## 4. Integration branch

`integration/working-system-20261008` (worktree `C:\Users\cheta\Development\uri-working-system`), created with
`git worktree add -b … 037229c`; merges `ddaf67b` (UI, `--no-ff`) and `2b6ee9f` (OI, `--no-ff`), both conflict-free.
Final commit ids are recorded in `WS_INTEGRATION_RECEIPT.md`.
