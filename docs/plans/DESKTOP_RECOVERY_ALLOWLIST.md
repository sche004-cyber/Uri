# Desktop recovery: narrow frozen-scope allowlist (record)

Status: AUTHORIZED AND IMPLEMENTED (candidate commit recorded in DESKTOP_RECOVERY_HANDOFF.md). Codex independent audit pending.

## Authority

- User (Chetan), 2026-10-01 18:10 UTC: authorized "the narrowly scoped desktop
  repair changes within `uri_core` and `uri_ui`, subject to the existing
  governance and frozen-file boundaries".
- User (Chetan), 2026-10-01 18:21 UTC, "APPROVED - Narrow Desktop Allowlist
  Amendment": authorizes the proposed allowlist solely for desktop recovery and
  mandatory Edge-first integration, with ten boundaries (frozen M36-M39 code,
  qualification oracles, anchors and security contracts preserved; exact files
  only, each recorded with its justification; no broad unfreeze; URI Core stays
  the orchestration authority; Edge tasks qualified with real tests; zero
  unnecessary Main Brain or harness calls on Edge-eligible tasks; escalation
  verified; end-to-end latency and actual model shown in the UI; regression,
  governance and frozen-boundary checks; Codex audit before acceptance).
- Precedent: the 2026-09-29 M39 allowlist entry in the M37 guard.

## Mechanism

The Edge route's code lives outside the frozen apps, in `uri_desktop_seams/`
(not in any guard's scope). Frozen files receive only a call-out hook, a
validation fix and telemetry fields. The three frozen-scope guards get one
exact-file allowlist (`DESKTOP_RECOVERY_ALLOWED_FILES`); no prefix entries, so
any other file under `uri_core`/`uri_ui` still fails the guards.

## Amended frozen-scope paths and justification

| Path | Why |
|---|---|
| `uri_core/app/server.py` | `/ask` call-out to the qualified Edge social route after approval resumption and lifecycle handling (S6 decides; any failure continues down the unchanged chain); per-turn model-call telemetry (all calls since turn start, not only the last) and turn duration in the response. |
| `uri_core/app/server.py` | Bounded LM Studio verification repair: discover model IDs from a loopback `/models` endpoint using the stored key, then probe and cache usable models. |
| `uri_core/core/response_validation.py` | Pure conversational turns (nothing dispatched) are no longer held to the capability-gap evidence-length cap, which rejected ordinary replies and made the UI show the decision rationale. Success-claim, credential, length and action-id checks unchanged. |
| `test_response_validation.py` | Root-level test for the validation change (outside guard scope; listed for completeness). |
| `uri_ui/lib/models/uri_turn.dart` | Carries model-call count and client-measured send-to-response time. |
| `uri_ui/lib/services/http_uri_client.dart` | Reads the new telemetry fields and times the `/ask` round trip. |
| `uri_ui/lib/widgets/turn_card.dart` | Caption shows the executing model, number of model calls, summed model time and send-to-reply time. |
| `uri_ui/test/chat_lifecycle_test.dart` | Caption text changed ("Model: ..." and "model N s"); one new test for multi-call and Send-to-reply time. |
| `tests/test_m36_memory_adversarial.py`, `tests/test_m37_edge_resolution.py`, `tests/test_m39_boundaries.py` | Exact-file exemption: a path passes only if it is listed in `desktop_recovery_allowlist.py` and its blob matches the pin; the module itself is blob-pinned in the M37 and M39 guards; the edited M36 guard is blob-pinned in both. |
| `tests/test_m37_frozen_guard_pin.py` | `GUARD_SHA256` re-pinned to the amended M37 guard. Tamper tests unchanged. |
| `uri_core/app/server.py` | Per-user Gmail registry construction and lifecycle refresh now use that user's OAuth token path. |
| `uri_ui/lib/services/http_uri_client.dart` | Failed `/ask` turns show the backend's `response.message` when no top-level error or Brain setup reason applies. |
| `test_gmail_user_scope.py` | Root-level regression proof for Gmail token-path isolation across registry creation and refresh; outside frozen guard scope. |
| `uri_ui/test/desktop_recovery_failure_reason_test.dart` | Mock HTTP regression cases for capability failure text and existing fallback priority. |
| `desktop_recovery_allowlist.py` | Re-pins the changed server and UI client blobs and pins the new UI test. |
| `tests/test_m37_edge_resolution.py` | Re-pins the desktop allowlist module blob. |
| `tests/test_m39_boundaries.py` | Re-pins the desktop allowlist module and both authorized frozen guard edits. |
| `tests/test_m37_frozen_guard_pin.py` | Re-pins the normalized M37 guard SHA-256. |
| `docs/plans/DESKTOP_RECOVERY_ALLOWLIST.md` | Records this bounded Gmail and failure-reason repair and its exact changed paths. |

Outside the guards' scope (not frozen, listed for completeness):
`desktop_recovery_allowlist.py` (the pinned list), `uri_desktop_seams/`
(the Edge route's code), `test_response_validation.py`,
`test_desktop_edge_seam.py`, `run_desktop_server.py`.

Verification (2026-10-02): guards pass on the amended tree; appending one line
to `uri_core/app/server.py` makes all three guards fail; adding an unlisted
file under `uri_core/core/` makes the M37 and M39 guards fail.

Changing any listed file later requires updating its pin in
`desktop_recovery_allowlist.py`, which changes that module's blob and so the
pins in the M37/M39 guards and the M37 guard hash: a visible, reviewable chain,
and a new User authorization for anything beyond this scope.
