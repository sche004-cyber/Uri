# URI A2UI — canonical development integration receipt

Date: 2026-10-09 (Asia/Kolkata). Recorded by Claude from the evidence in `evidence/` next to this file.
Mandate: owner brief "URI — Scheduler Closure, Integration & URI-Wide A2UI Development", Part 3 step 10: integrate only
after the relevant acceptance gates pass. **No production cutover. Nothing activated** (no task, no festival schedule;
live Claude not logged in). A2UI is shown only where a scheduler service is configured (`URI_SCHEDULER_STATE`).

## 1. Commits

| role | commit |
|---|---|
| Canonical before | `integration/git-sync-20261008` = `b02ed4f` (scheduler integrated) |
| A2UI branch | `phase/a2ui` = `cdcffe3` (contains `b02ed4f`) |
| Code last reviewed by Codex | `199b08a` (A2UI round 7 ACCEPT WITH FINDINGS); later commits: `54ecdb8` audit record, `608b930` materializer list, `cdcffe3` live-check evidence handling (both reviewed in the integration review) |
| Merge | `5432eec` (`--no-ff`) |
| Integration commit | the commit adding this receipt (docs and evidence only); hash in the final status message |

## 2. Inspection

- `b02ed4f` is an ancestor of `cdcffe3`; the merge tree equals the branch tree (Codex integration review).
- Scope `b02ed4f..5432eec`: new `uri_a2ui/**`, `tests/a2ui/**`, `scripts/a2ui_live_check.py`, `uri_scheduler/a2ui_host.py`,
  `uri_operational_intelligence/schedule_intent.py`, `uri_ui/lib/living/a2ui/**`, `uri_ui/test/a2ui/**`, `docs/a2ui/**`;
  recorded hooks in `uri_scheduler/service.py`, `uri_operational_intelligence/worker_bridge.py`, `events.py`, and six Dart
  files (`oi_conversation.dart`, `scheduler_client.dart`, `living_app.dart`, `living_scope.dart`, `companion_mode_view.dart`,
  `workspace_mode_view.dart`) plus `main_living.dart` (env table); exact-path guards and materializer roots. No protected
  path; CRLF/LF preserved; no token in evidence (live evidence is an inert JSON snapshot).
- `ws_frozen_check` at the tip: 121/121 Phase 1 checkpoint files byte-identical, no protected path (`evidence/ws_frozen_check.json`).

## 3. Regression

Gate tree `C:\Users\cheta\Development\uri-a2ui-gate`, materialized from `fad0bec` with `--exclude-oi-tests`
(`evidence/uri-a2ui-gate_MATERIALIZATION_RECEIPT.json`: HEAD `e8e3b65` = base, overlay `759d0d4`, candidate `fad0bec`).
Fixtures as for the scheduler integration (`uri-ws-gate4\evidence` minus chain outputs; `work\c1\checkpoints` from the
Phase 1 worktree, 883 files, identical aggregate hash). An idle `ollama serve` started by this session (no model) listened
for the whole run and was stopped afterwards. `5432eec` differs from `fad0bec` only in `scripts/a2ui_live_check.py` and
`docs/a2ui/**`, which the chain does not execute.

| gate | result |
|---|---|
| phase2 | PASS 486 / 0 / 2 skipped |
| authority | PASS 134 / 0 |
| phase1-full | **PASS 2,676 / 11 / 11; outcome identity: 2,698 ids, missing = added = outcome_changed = ∅; same failure set; baseline pins hold** |
| phase1-scope | PASS: outside Phase 2 scope ∅, importers ∅, 98 frozen files identical |
| residue | PASS |
| verdict | **ALL_PASS** on the first run (`evidence/chain_summary.json`, SHA-256 `46876cdd…de2f9c`) |

Suites at `5432eec`: Python `tests/a2ui tests/scheduler tests/oi tests/ws` **404 passed, 20 skipped** (opt-in live tests);
Flutter **444 passed, 4 skipped**; `flutter analyze` 2 infos, both pre-existing at canonical. Process-level live check
(`docs/a2ui/evidence/live_20261009/`): **PASS**. GPU lease held through a waiting holder for the chain
(`evidence/gpu_lease_history_a2ui_chain.jsonl`). `URIScheduler` task: not registered.

## 4. Independent audit

A2UI rounds: 1 REJECT, 2 AwF, 3 REJECT, 4 REJECT, 5 AwF, 6 AwF, 7 AwF (final) — `../A2UI_AUDIT.md`. Integration review:
AwF, INT-1 repaired. Residual for owner acceptance: after a storage failure an extra PROPOSED proposal can remain until a
successful owner action on the refreshed surface (inert: a PROPOSED job never runs).

## 5. Integration and rollback

Fast-forward `integration/git-sync-20261008` from `b02ed4f` to the integration commit (normal push, no force), verified by
`ls-remote` and a fresh clone. Rollback (owner): `git revert -m 1 5432eec` plus a revert of the receipt commit, or restore
the previous ref `b02ed4f` (history rewrite, owner decision only). Nothing outside the repository needs rollback.
