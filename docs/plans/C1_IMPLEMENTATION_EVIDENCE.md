# C1 implementation and validation evidence

Date: 2026-10-05. Status: implementation and focused validation completed; **awaiting independent review**. No milestone release, commit, push, C2 implementation, or production launcher change was performed.

This records execution of the reviewed Phase 1 C1 plan; it does not replace that plan or the governing architecture and authority documents.

## Scope and source

All application changes are in `C:/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent`, the prepared integration worktree at detached Core checkpoint `e8e3b65259c45fc823addc3ef8969425a265bd1b`. The implementation is uncommitted. The manifest additionally pins the changed source content; checkpoint identity alone is not treated as evidence of the running build.

New runtime files: `uri_core/core/runtime_identity.py`, `uri_core/app/runtime_routes.py`, `scripts/provision_uri_server.py`, `scripts/run_uri_isolated_server.py`, `scripts/uri_server_launcher.py`, `scripts/uri_server.ps1`, and `scripts/uri_server_manifest.schema.json`. Existing `server.py` receives additive route registration and readiness bookkeeping; route classification adds two explicit entries (79 classified routes total). `.gitignore` excludes generated `work/c1/` state. `test_c1_runtime_identity.py` and `scripts/validate_c1_regression.py` provide focused validation. Execution, approval, capability and permission implementations were not replaced.

## Live instance

| Observation | Actual result |
|---|---|
| Address | `http://127.0.0.1:8031` |
| State root | Integration worktree `work/c1/review-server` |
| Manifest | That root's `manifest.json` |
| Server ID | `c1963031-676d-4e04-8f80-224fb5588314` |
| Listener PID / creation time | `6504` / `1791146715.6053216` |
| Generation | `0e59955d-519a-4fa0-b298-f9dd4dbf614f` |
| Manifest digest | `75378e0273b352d9c58a9a0cbd13e6c9646ef255893d24b5a0f395fb05c578ae` |
| Source-content digest | `3744e2116aec8dc4121f518a4b56d20c0c31f66709a473152798344dcdb3fcd1` |
| Launch sequence | `STARTED`, then `ALREADY_RUNNING`, then `RUNNING`; same PID, creation time and generation |
| Anonymous / authenticated readiness | HTTP `401` / `200` |
| HTTP / public Graphify catalogue / synthetic legacy state | `READY` / `READY` / `READY` |
| Main Brain / Edge | `NOT_SELECTED` / `NOT_SELECTED` |
| Paired clients / harnesses | `NOT_IMPLEMENTED_C1` |

The review instance is intentionally left running. The original listener on port 8021 remains PID 16188. Neither model port 11434 nor 1234 had a listener during validation.

`GET /runtime/identity` exposes only server ID, composition, contract version, checkpoint, manifest digest and generation. An optional fresh 64-character hexadecimal nonce receives an Ed25519 signature over canonical identity and nonce. The launcher verifies that signature against the manifest's pinned public key, after verifying socket-owner provenance and again checking PID and creation time. Paths, credentials, user state and configuration are not public endpoint fields.

`GET /runtime/status` uses the existing strict authenticated principal dependency and explicit USER route classification. Anonymous and invalid credentials are rejected; ordinary authenticated synthetic users can read readiness. Neither route grants execution authority.

The Windows virtual-environment executable is a redirector: the listener's actual executable is the installed Python 3.13 image. The manifest pins both the venv interpreter and actual process image paths and hashes, and verification checks the exact command line. A redirector parent plus one listening backend is not interpreted as competing server instances.

## Launcher behavior and isolation

The opt-in PowerShell launcher supports only `validate`, `start` and `status`. It checks the isolated interpreter before invocation; Python validates exact source, interpreter, process image, dependency identity, manifest paths, fixture marker and allowed loopback port. Named server-ID and port mutexes serialize launch decisions. A lifetime server-ID mutex prevents a competing instance on another port. PID records are advisory: stale or corrupted records never authorize adoption or process termination.

Foreign listeners are refused before sending an identity request. Adoption requires exact process provenance and fresh signed identity; generic health responses are insufficient. Launch timeout reports an attempt PID without killing unknown processes. Tests demonstrate safe recognition if that exact attempted child subsequently becomes ready. There is no product stop/restart command.

Before Core import, the bootstrap selects a fresh synthetic state root, synthetic home/AppData/temp directories, a sanitized environment and ephemeral fixture credentials. Only the accepted public capability catalogue is seeded. The private signing key is Windows current-user DPAPI protected; state ACL inheritance is disabled with access limited to the current account and SYSTEM. Private fixture keys, authentication state, logs and preservation probes remain ignored by Git.

Existing startup code is retained. During the live startup, **four legacy provider health connection attempts were blocked**, with zero external read/write attempts and zero startup subprocess attempts. No model was loaded or required. Startup network and subprocess suppression ends after Core startup; the fixture file guard remains. This Python audit-hook fixture guard contains the known compatibility startup paths; it is not a production sandbox against malicious native code, nor proof of completed client-state separation. C1 readiness deliberately says `SYNTHETIC_FIXTURE_ONLY`.

## Test evidence

Executed with isolated Python 3.13.15, FastAPI 0.141.1, uvicorn 0.52.4, cryptography 50.0.1 and pytest 9.1.1. Dependencies were copied into the isolated venv from the existing installed environment; the original venv was not modified.

- C1 suite: **22 passed**, 31.42 seconds. Includes strict manifest rejection, signed proof/privacy, synthetic environment and junction containment, simultaneous real PowerShell launches, stale/corrupted PID records, foreign listener refusal without contacting it, same-ID competing-port refusal, anonymous/invalid/authenticated readiness, restart generation, timeout recovery and missing protected-key refusal.
- Focused Core regression suite: **303 passed, plus 29 subtests**, one warning. Covers route authorization, bind refusal, CORS, rate limits, request size, sessions/roles, capabilities/grants, experience-tier authority, approval gate/store/resumption/endpoints, canonical execution, ARN deterministic narrowing, Graphify, startup services, user-scoped startup and portable paths.
- `git diff --check`: passed.

Reproduce from the integration worktree in PowerShell:

```powershell
& .venv/Scripts/python.exe -B -m pytest -q test_c1_runtime_identity.py --disable-warnings -p no:cacheprovider --junitxml=work/c1/c1-tests.xml
& .venv/Scripts/python.exe -B -I scripts/validate_c1_regression.py
& scripts/uri_server.ps1 -Manifest "$PWD/work/c1/review-server/manifest.json" -Action validate
& scripts/uri_server.ps1 -Manifest "$PWD/work/c1/review-server/manifest.json" -Action start
& scripts/uri_server.ps1 -Manifest "$PWD/work/c1/review-server/manifest.json" -Action status
```

The regression helper creates a fresh synthetic working directory before importing Core. It copies Core source into that fixture for existing tests which inspect relative source paths; it executes the original test files without weakening assertions. C1 tests provision separate temporary fixtures and terminate only their independently proven test-owned instances. The review server is not a test-cleanup target. Full backend, model-dependent qualification and Flutter suites were not run; this is focused C1 evidence, not a broader release qualification.

Initial defects found and repaired within C1 included FastAPI lazy-router enumeration affecting the canonical route guard, Windows sharing of the running venv image during hashing, asyncio's internal loopback setup before startup network suppression, and regression fixture paths for source-inspection tests. Relevant suites were rerun after repairs.

## Existing installation preservation

A protected before/after comparison checked **4,571 existing files: zero changed hashes**. Coverage included existing URI workspace/private configuration and state, critical Core and legacy launcher sources, selected existing account configuration/credential files by hash only, and desktop/Start Menu shortcuts. No private file contents, credential values or per-file private hashes are included here. The production `URIServer` scheduled task XML remained identical to the preserved export and its task state remained Ready. The original 8021 service was not stopped or replaced.

The earlier Phase 1 encrypted preservation vault remains the recovery source for original installations. C1 made no data migration, model configuration change, shortcut/task edit, merge or release. Generated C1 state is additional synthetic development state only.

## Review and stop point

Independent review should trace the actual bootstrap, identity proof, Windows mutex/process/socket checks, strict authentication dependency and fixture boundary, using the supplied live instance and tests. Dependency identity hashes distribution metadata/RECORD and runtime paths; this is not a complete operating-system image attestation. Current-user Windows mutex/DPAPI ownership is a developer-local boundary; production administration and multi-user hardening remain deferred by the approved scope.

No broader Core refactor was necessary for C1. The implementation stops here, pending review. C2, client migration, model/harness selection, UI changes and production launcher replacement have not begun.
