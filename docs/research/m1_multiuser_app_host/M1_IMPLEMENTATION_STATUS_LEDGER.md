# M1 implementation-status ledger (baseline `54ad7be`, 2026-10-10)

## Legend

**Status values:**
- **IMPL+TESTED**: code exists and tests target it.
- **IMPL**: code exists, but no targeted test was found.
- **PARTIAL**: code exists but does not cover the requirement.
- **DESIGN-ONLY**: described in documents only.
- **MISSING**: neither code nor design.
- **BLOCKED**: the owner's PC is required.

**Evidence grade:**
- **RUN**: `COMPLETED_WITH_RESULT` in this session.
- **CODE-RV**: source re-verified by the author.
- **CODE**: source read by an audit subagent and not individually re-verified.
- **DOC**: a project record only.

| # | Capability | Status | Evidence | Grade | M1 slice |
|---|---|---|---|---|---|
| 1 | Accounts, PBKDF2 hashing, first-account ADMIN | IMPL+TESTED | `uri_core/core/user_accounts.py`; `test_user_accounts.py` | RUN | — |
| 2 | Bearer sessions, 24 h TTL, device revoke | IMPL+TESTED | `auth_session.py:77`; `test_auth_session.py`, `test_devices.py` | RUN | — |
| 3 | Admin-only routes (6) | IMPL+TESTED | `route_classification.py:69-76`; `test_m22_3_route_authorization.py` | RUN | — |
| 4 | Per-user stores (about 20) | IMPL+TESTED | `server.py` `_build_user_context`; isolation tests | RUN | — |
| 5 | Anonymous request served as owner (R1) | IMPL (by design), **risk** | `server.py:653-677` | CODE-RV | S1 |
| 6 | Grants skipped on the anonymous path (R2) | IMPL, **risk** | `approval_gate.py:119-125` | CODE-RV | S1 |
| 7 | Multi-action Gmail on the install-wide token (R3) | **DEFECT for multi-user** | `server.py:542,600`; `capabilities/gmail/capability.py:28`; `google_auth_common.py:32` | CODE-RV | S1 interim, S3 |
| 8 | Approved action loses the principal (H-1) | **UNVERIFIED hypothesis** | `approval_store.py:432` (`asdict`); `dispatcher.py:81` | CODE-RV (partial) | S3-T1 |
| 9 | Shared temp folders, graphify owner metadata, tier resets mode (R5, R7, bug) | IMPL, **risk / bug** | subagent audit | CODE | S3 |
| 10 | Open signup | IMPL, **risk** | `route_classification.py:82` (PUBLIC) | CODE-RV | S1, S3-T8 |
| 11 | Suspension, role change, password reset | DESIGN-ONLY / MISSING | `URI_M22_ARCHITECTURE.md` §4.5 | CODE | S3-T7 (suspension only) |
| 12 | Provider and external keys encrypted, with a hard-coded default secret | IMPL+TESTED, **weak default** | `server.py:37`; `run_uri_server.py:47-48` | CODE-RV, RUN | S2 |
| 13 | Google tokens per user (single-action) | IMPL+TESTED, plaintext | `test_m32_gmail_user_scoping.py` | RUN | S3-T6 |
| 14 | Google consent only at the server PC | IMPL | `gmail_service.py:126`; `server.py:3378` | CODE-RV | S6 |
| 15 | Google Calendar | MISSING | grep | CODE | S6 |
| 16 | Bind refusal, CORS, auth rate limits | IMPL+TESTED | `test_m22_3_*` | RUN | reused by S1 |
| 17 | Private network / remote access | MISSING | grep | CODE | S5 (BLOCKED) |
| 18 | Paired client surface (Line B) | IMPL+TESTED (Windows), loopback-only frozen | `runtime_identity.py:313` | CODE-RV, DOC | not in M1 (D-1) |
| 19 | Runtime v1 Brain, single slot | IMPL, frozen; live on the PC only | freeze doc :34, :291 | CODE-RV, DOC | S4 (BLOCKED) |
| 20 | Line A connected to Runtime v1 | MISSING (configuration path exists: `provider_registry.py:184-187`) | grep for `18470` in `uri_core` returns nothing | CODE-RV | S4 |
| 21 | GPU lease, machine-wide exclusive | IMPL+TESTED (Windows) | `gpu_lease.py`; cloud run fails for `msvcrt` | CODE-RV; RUN = platform-blocked | reused |
| 22 | Per-user fair Brain queue | MISSING | `worker_bridge.py:176` refuses; Line A uncapped | CODE-RV | S1 |
| 23 | Supervisor, Job Objects, admission pools | IMPL+TESTED (Windows); no CPU or memory limits | `winproc.py:267` | CODE-RV | S7, S8 (D-6) |
| 24 | Harness adapters (Claude Code, Codex), bypass refusal, env filter | IMPL+TESTED (Windows) | `uri_harness_adapters/__init__.py`; `harness.py:33,37` | CODE-RV; `test_m31_harness_boundary.py` RUN | S7 |
| 25 | Per-client native CLI homes; shared login is a stop condition | IMPL; live test needs login | `qualification.py:377-390` | CODE-RV | S7 (BLOCKED) |
| 26 | Per-URI-user OS identity for harnesses | MISSING | `runtime_identity.py` DPAPI note | CODE | S7 (BLOCKED) |
| 27 | Gemini CLI harness | MISSING (not needed) | — | CODE | — |
| 28 | Scheduler | IMPL+TESTED, single owner, not activated | `tests/scheduler` 56 pass | RUN, DOC | later |
| 29 | A2UI contract, renderer, action authority | IMPL+TESTED; only the scheduler produces surfaces | `tests/a2ui` pass; `validate.py:19` | RUN, CODE-RV | S8 |
| 30 | App registry, lifecycle, broker | MISSING | grep | CODE | S8 |
| 31 | External capability contract (cli, loopback-http) | IMPL+TESTED offline; its doc still says DRAFT | `uri_core/external/` | CODE | reused by S8 |
| 32 | Flutter classic HTTP client with configurable URL | IMPL+TESTED (records); token plaintext | `http_uri_client.dart`; `session_store.dart` | CODE, DOC | S9 (BLOCKED) |
| 33 | Office backend (M39) | not on canonical (donor branches only) | git | CODE | out of M1 |
| 34 | `requirements.txt` omits the Google client libraries | **DEFECT (low)** | cloud collection errors | RUN | S2 |
| 35 | Local PC work after `54ad7be` (staging receipt, push record) | **UNKNOWN** | receipt §5 unfilled | DOC | re-check before S1 |
| 36 | User-chosen folders, drives, output location, named workspaces, per-verb folder grants | MISSING | `M1_STORAGE_ACCESS_MANAGER.md` §1 | CODE-RV | S10, S12, S13 |
| 37 | Default-deny for folders | Structurally true only (no tool takes a raw path) | grep of `uri_core/tools`, `capabilities` | CODE-RV | S10 (make explicit) |
| 38 | Per-run harness workspace + verified, symlink-refusing copy-out | IMPL (Windows-tested per records) | `turn_runner.py:225-262`; `postconditions.py:100-104` | CODE-RV | reused by S16 |
| 39 | FileStore containment (realpath + prefix), extension and size caps | IMPL+TESTED | `file_store.py:157-190`; `test_m21_file_store_isolation.py` | CODE-RV, RUN | reused by S10 |
| 40 | Reparse-point, UNC, device-path, ADS guards for arbitrary roots | MISSING | — | CODE-RV | S10 |
| 41 | Native folder picker | MISSING (single-file picker only; `file_picker ^12.2.0` present) | `platform_file_picker.dart:22`; `pubspec.yaml:43` | CODE-RV | S14 |
| 42 | File-access audit log | MISSING (hash-chain pattern exists in scheduler) | `uri_scheduler/store.py:9,60` | CODE-RV | S10 |
| 43 | Zip extraction has no decompressed-size bound | **Low-severity defect** | `linked_document_service.py:167-207` | CODE-RV | S16 |

Every row is unchanged by this research: no code was modified. Rows that move during M1 must be updated with a
correction record, never overwritten silently.
