# Phase 2D: response to independent review round 2 (implementer's repair record)

Date 2026-10-07. Author: Claude (implementer/orchestrator). NOT a review; accepts nothing. Reviewer: Codex CLI 0.158.0,
model gpt-6-sol, `codex exec`, thread `01a115e5-2a4f-79f1-a447-8de5e8d82006`; verdict **PHASE 2D REJECTED**; report kept
verbatim at `evidence\phase2d_review\round2\CODEX_REVIEW_round2.md`. Reviewed candidate `phase2d-candidate-20261007-r1.zip`
(SHA-256 `0fa06ac3...230240`) is preserved unchanged.

| Reviewer ID | Severity (reviewer) | Implementer response | Regression tests |
|---|---|---|---|
| R2-1 expiry/evidence only checked at composition; long-lived worker keeps honouring an invalid record | High | REPAIRED. `compose_client` attaches `ExecutorBinding.revalidate` = `still_valid(provider)`: reloads the record file, requires the same `record_sha256` as composed (a swapped record, even validly signed, needs recomposition: `RECORD_CHANGED_SINCE_COMPOSITION`), and re-runs the full `revalidate` (signature, expiry against a clock consulted at call time, evidence hash and content, launch chain, `--version`). The bridge calls it before every execution (`NOT_STARTED:QUALIFICATION_NO_LONGER_VALID:<code>`); the registry's auth probe returns unknown (not usable) when it fails, so `harness_discover`/`selectable` also stop advertising it. The worker's `harness_discover` reports `qualification_live` per provider. | `test_record_expiring_after_composition_stops_execution`, `test_evidence_deleted_after_composition_stops_execution`, `test_record_replaced_after_composition_even_validly_signed_stops_execution`; worker-process test asserts `qualification_live == {claude_code: None}` |
| R2-2 a signed record may list models its evidence never exercised | Medium | REPAIRED. NATIVE: `models` must equal exactly `[evidence.model]`. FIXTURE: when the evidence names `models`, the record must equal it. | `test_native_record_listing_an_untested_model_is_refused`, `test_fixture_evidence_naming_models_bounds_the_record` |
| R2-3 OS-loaded libraries / child programs unpinned; check-to-spawn race | Medium, reviewer: not blocking | NOT CHANGED; stated as a limit in `PHASE2D_COMPOSITION.md` and in the qualification module docstring. | n/a |
| R2-4 architecture note contradicted repaired code | Low | REPAIRED with history kept (superseding note under the old bullet). | n/a |
| New, found by the implementer while repairing R2-1 (latent since round 1) | High (implementer's own rating) | In the Phase 2 worker process the frozen `FixtureGuard` refused `subprocess`'s `os.open(os.devnull, O_RDWR)` (stdin=DEVNULL) as an external write, so every live `--version` and auth-status probe failed closed after start-up: natively qualified providers could never be usable inside the worker profile. Repaired in the Phase 2 worker profile only (`Phase2FixtureGuard`, a subclass whose single relaxation is the null device); the frozen `FixtureGuard` is unchanged. | worker-process test (`qualification_live`), static pin `test_two_live_phase2_workers_on_one_client_are_refused` (exactly one `check_path` override, null device only) |
| R1 D6 (auth cached) | n/a | Reviewer round 2 ruled the round-1 finding incorrect; regression test kept. | `test_auth_is_probed_live_at_every_execution_not_cached_at_composition` |

Real-executor evidence after this repair: `evidence\phase2d_r2\codex_composition6.json` (signed v2 record, governed turn over
the UI frames, `SETTLED_VERIFIED`, ledger COMPLETE `POSTCONDITIONS_VERIFIED`, all post-run checks PASS). Approval programmatic.

Regression logs (ORCHESTRATOR-PRODUCED; the reviewer's sandbox cannot run pytest): `evidence\phase2d_r2\phase2_all.log`,
`phase1_authority.log`, `phase1_full.log`.

Files changed: `uri_supervisor_bridge/qualification.py`, `uri_supervisor_bridge/bridge.py`, `scripts/run_uri_supervised_worker.py`,
`tests/phase2d/test_qualification.py`, `tests/phase2d/test_selfaudit.py`, `tests/phase2d/test_worker_process.py`,
`docs/architecture/PHASE2D_COMPOSITION.md`, this file. Pre-repair copy: `evidence\phase2d_review\round2\qualification_v2_before_round2_repair.py.txt`.
Frozen Phase 1 files: none changed.
