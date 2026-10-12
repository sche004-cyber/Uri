# Phase 2D: response to independent review round 1 (implementer's repair record)

Date 2026-10-07. Author: Claude (implementer/orchestrator). This is NOT a review and does not accept anything. The
independent reviewer (Codex CLI 0.158.0, model gpt-6-sol, non-interactive `codex exec`, thread `01a115c0-513d-7f73-ac44-9c5e94ccf0be`)
returned **PHASE 2D REJECTED** in `evidence\phase2d_review\CODEX_REVIEW_round1.md` (kept verbatim, unmodified). This file
records what the implementer changed in response, so the reviewer can re-examine it. The verdict belongs to the reviewer.

Reviewed candidate: `evidence\phase2d-candidate-20261007.zip` (SHA-256 `6c7cb4f8...3c6785`). It is preserved unchanged.

## Findings and responses

| Reviewer ID | Severity (reviewer) | Implementer response | Regression tests (all new) |
|---|---|---|---|
| D1 unkeyed, recomputable record digest; edited `models` accepted | High | REPAIRED. Record schema v2 is signed (Ed25519) by the client's own key (`secure/client-key.dpapi`, same key the C1 worker uses for its identity proofs); `verify_trust` refuses `RECORD_SIGNATURE_INVALID`. | `test_hand_edited_record_is_refused_even_with_a_recomputed_digest`; REAL check `tampered_record_with_recomputed_digest_invalidated` (run 5) |
| D2 evidence never re-read | High | REPAIRED. Evidence is copied into the client store (`qualification/evidence/<provider>-<sha16>.json`); every load rehashes it (`EVIDENCE_HASH_MISMATCH`/`EVIDENCE_MISSING`) and checks content against the record: provider; fixture flag, or for native records `ok=true`, same version, same executable SHA-256, model in `models` (`EVIDENCE_CONTENT_MISMATCH`). | `test_evidence_is_rehashed_and_content_checked_on_every_load` |
| D3 no client binding / expiry; copyable | Medium | REPAIRED. Records carry `client_id`, `client_public_key`, `qualified_at`, `expires_at` (default 30 days, max 90); composition requires a `RecordTrust` from the client manifest (`RECORD_CLIENT_MISMATCH`, `RECORD_EXPIRED`, `NO_TRUST_ANCHOR`). | `test_record_signed_by_another_key_or_for_another_client_is_refused`, `test_expired_record_is_refused`, `test_no_trust_anchor_qualifies_nothing`; REAL check `record_copied_to_another_client_invalidated` |
| D4 pin covers only the npm `.cmd` shim | High | REPAIRED (bounded). Records carry `pinned_files` (every file of the launch chain: `node.exe`, `codex.js`, both `package.json`, every `.exe/.dll/.js/.cmd/.ps1` under the vendor directory; 36 files on this machine) and `resolve_pins` (`node` must still resolve on the executor PATH to the pinned file). Re-checked at load (`LAUNCH_CHAIN_*`) and by the bridge before every run (`NOT_STARTED:EXECUTOR_LAUNCH_CHAIN_MISMATCH`). A native `.cmd/.bat/.ps1` launcher without a pinned chain is refused (`LAUNCH_CHAIN_NOT_PINNED`). Remaining limit: DLLs the OS loader resolves outside the pinned directories and programs the executor itself spawns (shells) are not pinned. | `test_payload_replaced_behind_an_unchanged_shim_is_refused`, `test_resolution_redirected_to_another_payload_is_refused`, `test_native_cmd_launcher_without_pinned_chain_is_refused`, `test_real_npm_codex_launch_chain_is_discovered_and_pins_the_payload` (REAL install, read-only); REAL check `launch_chain_pinned_and_intact` |
| D5 no mid-run cancel over the serial worker protocol | Medium, reviewer: not blocking for 2D | NOT CHANGED. The frozen Flutter client matches replies FIFO, so a concurrent cancel frame needs a request-id protocol change: UI/operations scope. Recorded as NOT IMPLEMENTED. | n/a |
| D6 auth status cached at composition | Low | DISPUTED with evidence, for the reviewer to judge. `compose_client` installs a probe the Phase 1 registry calls on every `discover()`; the bridge calls `registry.selectable()` (= `discover()`) before every task. | `test_auth_is_probed_live_at_every_execution_not_cached_at_composition` (logout after composition -> `NOT_STARTED:HARNESS_*`, zero tasks) |
| Candidate vs live tree mismatch (report appended after the cut) | integrity note | REPAIRED in procedure: the new candidate is cut last; its hash is written only to the sidecar and to this repair record's successor, never appended to a file inside the candidate. | n/a |
| Overstated report wording (UI composition; "everything else implemented") | contradiction | CORRECTED with history preserved: see the correction record appended to `PHASE2D_REPORT.md`. | n/a |
| Reviewer could not execute tests (sandbox ACL: pytest temp `WinError 5`, `icacls` `STATE_ACL_FAILED`) | environment | Regression suites re-run by the orchestrator OUTSIDE the reviewer's sandbox; logs in `evidence\phase2d_r1\`. These logs are orchestrator-produced and are labelled as such; the reviewer may reproduce any non-ACL-dependent subset itself. | n/a |

## Real-executor evidence after the repair

`evidence\phase2d_r1\codex_composition5.json`: direct probe OK, live `codex login status` true, signed v2 record persisted (36 pinned
files, `resolve_pins {node: C:\Program Files\nodejs\node.exe}`, TTL 30 days), composition QUALIFIED, governed turn over the UI
frames `SETTLED_VERIFIED`, ledger COMPLETE, argv SHA-256 recomputed and matched, 4-byte `PONG`; 14 post-run checks PASS
(including the three D1/D3/D4 checks above). Approval was programmatic (this harness), not a human click.

## Files changed by this repair

`uri_supervisor_bridge/qualification.py` (rewritten: schema v2), `uri_supervisor_bridge/bridge.py` (`pinned_files`,
`resolve_pins`, `_launch_chain_intact`), `uri_supervisor_bridge/composition.py` (`trust` parameter),
`scripts/run_uri_supervised_worker.py` (trust from manifest; guard admits pinned chain files),
`scripts/phase2d_composition_qualification.py` (signs with the provisioned client key; new checks),
`tests/phase2d/conftest.py`, `tests/phase2d/test_qualification.py`, `tests/phase2d/test_selfaudit.py`,
`tests/phase2d/test_worker_service.py`, `docs/architecture/PHASE2D_COMPOSITION.md` (qualification section), `docs/plans/PHASE2D_REPORT.md`
(correction record appended). Pre-repair copy of the qualification module: `evidence\phase2d_review\qualification_v1_before_round1_repair.py.txt`.
Frozen Phase 1 files: none changed.
