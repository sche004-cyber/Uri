# Ember V2.1 - canonical integration receipt (2026-10-21)

**Status: INTEGRATED by fast-forward** of `uri-repo/integration/git-sync-20261008` from `ec2fab54` to the commit
that adds this receipt (parent `68061d85`). The post-push check (`git ls-remote`) is recorded in `developmental.md`
and `decisions.md` on `audit/p0-comprehensive-20261021` and in the URI-CONTROLS-3 integration receipt
(`docs/ui/uri_controls_3/`), because a file cannot record the push of its own commit.

## 1. Authority

Owner decision 2026-10-21 (task "Complete Ember V2.1 and URI Controls integration into URI canonical"): "Ember V2.1
... APPROVED FOR CONTROLLED INTEGRATION", "Recognize existing valid independent reviews", "Avoid repeating completed
GPU/live tests unless evidence is missing, invalid, or affected by changes", "Do not block internal integration on
artwork licensing; preserve that as a distribution-stage gate". This answers P0 plan item Q-1
(`docs/audit/p0_20261021/P0_INTEGRATION_PLAN.md` on the audit branch).

## 2. Acceptance criteria and evidence (checked 2026-10-21)

| # | Criterion | Evidence | Result |
|---|---|---|---|
| 1 | Reviewed code equals the candidate | `git diff bb61e976 68061d85` touches only `docs/integration/qc_ember_20261018/**` (re-checked); this receipt adds docs only | MET |
| 2 | Independent review verdict on that code | R1-R4 (`docs/companions/fire/v21_integ/review/`), stage-2 `ember_stage2/review/EMBER_INTEG_report.md`, FINAL `ember_stage2/review/FINAL_EMBER_report.md`: all ACCEPT WITH FINDINGS, fresh read-only subagents (Lifecycle V3 tier 3; owner rule: subagents are legitimate independent reviewers). OD2_VERIFY2 ACCEPT WITH FINDINGS on `401a2964`; its docs repairs `6561e0b4` were not re-reviewed (docs only) | MET |
| 3 | Gates | at `bb61e976`: Flutter 855 passed / 5 skipped (log head verified by P0), pytest oi/ws 793/23, analyze 0 errors, release build rc 0. 2026-10-21 on `68061d85`: `ws_frozen_check` `unapproved_protected_changes: []`, `unapproved_drift: []`; focused Flutter (Ember companion, Ember transparency, companion orb, UI V2) 103 passed. The merged tree with URI-CONTROLS-3 (`1741e97e`): Flutter 882/5, pytest 807/23, build rc 0 | MET |
| 4 | Frozen-core integrity | no Runtime frozen path changed (`model_lab`, Runtime v1 config); UI V2 frozen-scope surfaces changed are listed in `02_EMBER_STAGE2_INTEGRATION_RECEIPT.md` and P0 evidence 20 | MET (UI V2 deltas disclosed) |
| 5 | Transparent, borderless companion; UI V2 compatibility | live on the same code: `p3-ember-switch` at `bb61e976` (borderless, 90.8 % transparent, click-through, drag, 1.25x, Brain switch under Ember), `e-first` at `8f883bbf`; UI V2 main journey 68/68 at `8f883bbf` and `bb61e976` | MET |
| 6 | Artwork provenance | `03_EMBER_OD2_PROVENANCE.md` rev 2: DEFERRED DISTRIBUTION-RELEASE GATE. `uri-repo` is private. The reference art is in history from `8a1438ec` and is now in the private canonical history; no external distribution before the rights review | RECORDED (distribution gate) |
| 7 | Rollback | `git revert --no-edit ec2fab54..<this commit>` as a new commit (no force-push). The art stays in remote history after a revert; removing it is a separate owner decision (history rewrite) | DEFINED |

## 3. Not done (missing evidence, disclosed)

UI V2 returning (12) and perf (3) journeys have not been re-run with Ember (P0 UIV2-DELTA-1). An attempt on
2026-10-21 16:27-17:05Z (`D:\uri-dev\uri-controls-live\live\e-main`, chain `chain_ember.sh`, runtime
`uri-integ-rt-e` = `bb61e976`, profile P3) never got a Brain: the production host waited in WAITING_FOR_GPU
(GPU_CONTENDED, fit -976 MiB; the desktop's `dwm.exe` held 1.77 GB). The run was stopped with the harness stop file;
no result exists (NO_OUTPUT, not counted as evidence). This affects a UI V2 re-freeze, not this integration; the
same journeys were also not re-run for the earlier post-freeze integrations (Brain QC, Office). They stay a required
follow-up for the next free GPU window.

## 4. Carried findings (unchanged, owner-held)

Fidelity AC-F1/AC-F3 NOT MET; T4 depleted state; F-SIZE-1; F-LIGHT-1; F-START-GAP; AC-P1; F-5; HARN-2; PERF-1
(Debug runner VRAM only); Brain throughput on an uncontended desktop at `bb61e976` NOT VERIFIED.
