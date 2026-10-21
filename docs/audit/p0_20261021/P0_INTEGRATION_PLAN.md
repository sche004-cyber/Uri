# P0 Controlled Integration Plan (2026-10-21)

Status: PLAN ONLY. Nothing below has been integrated. This plan is not owner authorisation; each queue item needs its
own owner approval (DEC-041, DEC-076, DEC-090). After approval, use the existing controlled integration workflow
(`.claude/skills/uri-development-lifecycle/SKILL.md` stage 11 and integration preconditions) and record a receipt
under `docs/integration/`.

Canonical base for every item: `uri-repo/integration/git-sync-20261008` @ `ec2fab5493578a4f5a805642153d56b4d5ea59fa`.

## Acceptance criteria for an item to enter the queue

1. Exact candidate commit identified, and the reviewed code is byte-identical to it (or the difference is docs only).
2. An independent review verdict exists on that exact code (ACCEPT or ACCEPT WITH FINDINGS, no blocking finding open).
3. Recorded gates on that code: pytest and Flutter suites, `ws_frozen_check` ok.
4. Frozen-file impact known; any frozen-surface change has an owner record.
5. Live requirements named, and either met on that code or listed as a precondition.
6. Rollback defined.

## Queue

| Order | ID | Candidate | Ready? | Risk |
|---|---|---|---|---|
| 1 | Q-1 | Ember V2.1 `68061d85` | Yes, on owner approval (criteria 1-4 and 6 met; criterion 5 partly met) | MEDIUM |
| 2 | Q-2 | UI Controls & Typography `e9ee7409` | No: R1-01 MEDIUM open | MEDIUM |
| 3 | Q-3 | Reviewer tiers `67d45317` | No: no review and no test result on this commit | LOW-MEDIUM |
| — | Q-4 | VRAM-R1 research record `7c7a7776` | Optional; code already integrated | LOW |

Reasons for this order: Q-1 is the only item that meets the criteria now. Q-1 and Q-2 merge without textual conflict
(`git merge-tree --write-tree 68061d85 e9ee7409` -> tree `e68da43c`, rc 0; one shared file
`companion_settings_section.dart` auto-merged). Q-2 must re-run the Ember switch journey if it lands after Q-1 (its
controls change the chip text the Ember driver uses, R1-07). Q-3 does not touch product code and can land
independently once reviewed; landing it resolves POL-P0-1.

Not eligible: `milestone/sched-token-acl-2` `eaf3bf69` (R4 REJECT); `research/qwen38-27b-brain-20261016` `9689a666`
(no ACCEPT); all research branches; all superseded branches (see `developmental.md` §F).

## Q-1 Ember V2.1

| Field | Value |
|---|---|
| Candidate | `68061d85` on `integration-candidate/ember-on-canonical-20261018` (local only, worktree `D:\uri-dev\uri-integ-ember`) |
| Reviewed code | `bb61e976` (merge of `ec2fab54`); `bb61e976..68061d85` changes only `docs/integration/qc_ember_20261018/**` (verified) |
| Base | `ec2fab54`; 63 ahead, 0 behind; fast-forward possible |
| Acceptance evidence | R1-R4, stage-2, FINAL (on `74e7f7ba`): all ACCEPT WITH FINDINGS, fresh-subagent class (tier 3) |
| Gates | Flutter 855 passed / 5 skipped / 0 failed at `bb61e976` (log checked); `ws_frozen_check` `[]` |
| Live | UI V2 main journey 68/68 (twice); Ember live runs incl. `p3-ember-switch` (records on branch) |
| Required repairs | none blocking. Docs-only gap: OD2_VERIFY2 repairs `6561e0b4` not re-reviewed |
| Owner-carried items | fidelity AC-F1/AC-F3 not met, T4 depleted state, F-SIZE-1, F-LIGHT-1, F-START-GAP, AC-P1, F-5 |
| Frozen-file impact | No Runtime frozen path. UI V2 frozen-scope surfaces changed: `companion_orb.dart`, `living_app.dart`, `oi_sources.dart` (+177, Brain-state wiring per DEC-083), companion settings/gallery/state/theme/preferences/sources, `pubspec.yaml` (+2 assets), tests `ui_v2_test.dart` (11 -> 12 designs), `companion_orb_test.dart`, `voice_presence_test.dart` |
| Artwork (OD-2, DEC-081) | Reference art is absent from the tip tree but present in history from `8a1438ec` (15 commits). Pushing `68061d85` publishes it to the private `uri-repo`. Owner policy treats this as not external distribution. Derived Ember assets (12 shipped images) stay in the tree; public distribution stays gated |
| Live requirement before or right after integration | UI V2 returning 12/12 and perf 3/3 have not been re-run with Ember (freeze criterion 5). One GPU-lease window on the frozen Standard profile |
| Regression tests | full Flutter; typography guard; pytest oi/ws; `ws_frozen_check`; `test_frozen_core` in a materialised runtime; Ember T0-T5 |
| Expected result | gates as at `bb61e976`; 68/68 main; returning 12/12; perf 3/3 |
| Integration method | `git push uri-repo 68061d85:refs/heads/integration/git-sync-20261008` (fast-forward, no force) after re-checking the remote is still `ec2fab54`; receipt in `docs/integration/qc_ember_20261018/` |
| Rollback | Before push: nothing to undo. After push: `git revert --no-edit ec2fab54..68061d85` as a new commit (no force-push). The art remains in remote history after a revert; removing it needs a history rewrite, which is a separate owner decision |

Owner choices for Q-1 (one is needed):
- (a) approve integration now, with returning/perf journeys run in the next GPU window and recorded in the receipt;
- (b) approve integration only after the returning/perf journeys pass;
- (c) hold.

## Q-2 UI Controls & Typography

| Field | Value |
|---|---|
| Candidate | `e9ee7409` on `milestone/ui-controls-typography-20261018` (local only, worktree `D:\uri-dev\uri-ui-controls-typo`; code `22b53b78`) |
| Base | `ec2fab54` (merged at `a4935c2b`); 5 ahead, 0 behind |
| Evidence | pytest oi+ws 805/23, Flutter 799 at `22b53b78`; live ui-2 26/26 (report claims 30/30), uiv2-1 68/68 |
| Review | R1 ACCEPT WITH FINDINGS. The record was an untracked file; P0 preserved a copy at `docs/audit/p0_20261021/evidence/preserved/UI_CONTROLS_TYPO_R1_report_uncommitted_on_e9ee7409.md` |
| Required repairs (R1 itself requires them before integration) | R1-01 MEDIUM (keyboard + screen reader, confirmed in code by P0: `qc_toggle.dart:111-140`); R1-02 live count. Recommended: R1-03..R1-06 |
| Also open | F-1 product decision (OPEN-04); contrast check on the four palettes (never measured) |
| Frozen-file impact | Runtime config and `runtime_profile*` unchanged; protected `settings_shell.dart` untouched; 43 Dart files restyled across UI V2 frozen surfaces (e.g. `bodyMedium` 13.5 -> 14); `ws_brain_host.py` +53, `worker_bridge.py` (restore path) |
| Steps (routine, no owner decision needed) | repair -> commit R1 record -> R2 re-review on the exact commit -> re-run ui-2, uiv2-1, Ember switch journey if after Q-1 -> then request owner integration approval |
| Regression tests | full Flutter + pytest; `tests/oi/test_ui_controls_switch_fallback.py`; new keyboard/semantics widget test; contrast check |
| Rollback | revert the range as a new commit |

## Q-3 Reviewer tiers 3-5 (owner-attested review)

| Field | Value |
|---|---|
| Candidate | `67d45317` on `milestone/lifecycle-owner-attested-review-20261017` (worktree `D:\uri-dev\uri-owner-attested`) |
| Base | `348677b7`; 16 ahead, 66 behind `ec2fab54`; merges cleanly onto `ec2fab54` (merge-tree check, P0 evidence 50) |
| Change | 4 files, +2335/-78, lifecycle tooling only, no frozen file |
| Evidence | none on this commit: r10 REJECT, r11 REJECT (2 blocking, repaired in `67d45317`), r12 tier-3 review started 2026-10-17T18:15:36Z and never collected; full test log `D:\uri-dev\lifecycle\suite_67d45317.log` truncated (64 bytes) |
| Steps | run full `tests/dev_workflow` (~42 min, CPU); independent review (Codex after 2026-10-22 14:03, else tier 3 per the policy this branch implements); then owner approval |
| Why it matters | canonical SKILL.md text currently says a separate Claude session review never counts as independent ACCEPT, while recent integrations used the 2026-10-17 tier policy (POL-P0-1) |
| Rollback | revert as a new commit |

## Q-4 VRAM-R1 research record (optional)

`7c7a7776` is 4 commits ahead of `ec2fab54` with records only: `research/runtime_vram_r1/` (157 files), research
harness scripts and 24 `model_lab/evidence/runs/vr1*` files. The accepted code (5 files) is already in canonical (4
identical, `scripts/ws_brain_host.py` a superset). The branch is pushed to `uri-repo`, so the record is preserved
without merging. Recommendation: do not merge into canonical; keep it as a published research branch. If the owner
wants it merged, run `ws_frozen_check` on the merge result first, because it adds files under `model_lab/`.

## Housekeeping eligible without integration (routine; no canonical change)

| Item | Status |
|---|---|
| Preserve uncommitted adaptive-runtime evidence | DONE by P0 (copy, SHA-256 recorded; source untouched) |
| Preserve UI-controls R1 record | DONE by P0 (copy in `evidence/preserved/`) |
| Remove ~95 stale runtime materialisation worktrees | NOT DONE: they are recoverable but deleting worktrees is irreversible; owner choice |
| Fast-forward the stale local branch `integration/git-sync-20261008` (348677b7 -> ec2fab54) | NOT DONE: harmless but changes a ref other sessions may use; owner choice |
| Push `audit/p0-comprehensive-20261021` to `uri-repo` | NOT DONE: outward action, needs owner yes (OPEN-09) |
