## Verdict: REJECT

The repair tracks the requested files in `3c8087b`, and the frozen-scope guard plus M33.3-R anchors pass. However, the desktop path bypasses URI Core’s authoritative `/ask` lifecycle and fabricates several claimed integrations/results. This is a critical architectural and security failure.

Key findings:

- **Working tree is not clean.** `git status` reports untracked `run_reaudit.py`. The launcher, adapter, test, and both role-config files are tracked in `3c8087b`.

- **Startup lifecycle remains unsafe.** [launch_desktop.ps1](/C:/Users/cheta/Development/uri-m37-m39-integration/launch_desktop.ps1:91) detects a non-healthy listener on port 8000 but only warns, then starts another server anyway. [run_desktop_server.py](/C:/Users/cheta/Development/uri-m37-m39-integration/run_desktop_server.py:75) records its PID before Uvicorn successfully binds; it has no pre-bind port-conflict handling. Launcher log redirection is not configured on `Start-Process`; the runner only conditionally redirects when stdout/stderr are unavailable.

- **The named mutex is not an end-to-end single-instance guarantee.** It serializes launcher execution, but [launch_desktop.ps1](/C:/Users/cheta/Development/uri-m37-m39-integration/launch_desktop.ps1:142) starts the UI asynchronously and then releases the mutex. A second launcher can run before `uri_ui` exposes a window, see no process, and launch another UI instance.

- **Shutdown is only partly targeted.** [stop_desktop.ps1](/C:/Users/cheta/Development/uri-m37-m39-integration/stop_desktop.ps1:16) closes/force-kills every process named `uri_ui`, not a URI instance owned by this launcher. Its lingering-server test relies on `$p.CommandLine` from `Get-Process`, which is not a reliable available property, so a server whose PID file is stale can be left listening.

- **The two-model configuration is tracked but inert.** Both JSON files contain the requested Qwen and Codex values, but repository search found no consumer of `desktop_model_roles.json` or `model_roles.json`. Claude’s quota-exhausted state is only hard-coded into a capabilities response, not represented in the configuration.

- **Critical: `/ask` bypasses the canonical URI Core path.** [uri_desktop_adapter.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_desktop_adapter.py:425) intercepts every POST `/ask` and returns directly at line 437. It therefore skips the route’s authenticated-user dependency, content-length enforcement, context construction, approval-resumption handling, canonical execution, and response finalization in [uri_core/app/server.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/app/server.py:1631).

- **M36–M39/RAR are imported, not integrated.** Static analysis confirms `mem_log`, `edge_res`, `rar_det`, `HarnessRunner`, `ExecutionCapsule`, `PermissionProfile`, and related contracts are unused imports. The RAR response is a fixed string, not a call to deterministic RAR. Memory logging is never invoked. No v1 office workflow API is used.

- **Harness telemetry is false.** [_execute_harness_task](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_desktop_adapter.py:216) only probes Codex and writes `harness_instruction.txt`; it never creates a capsule, invokes `CodexCliAdapter.invocation`, runs `HarnessRunner`, verifies output, or records lineage. Yet it returns “processed” with successful execution telemetry. The real runner’s required lifecycle begins at [runner.py](/C:/Users/cheta/Development/uri-m37-m39-integration/uri_v1/execution/harness/runner.py:39).

- **T1–T10 are not a truthful acceptance battery.** [tests_desktop_recovery.py](/C:/Users/cheta/Development/uri-m37-m39-integration/tests_desktop_recovery.py:39) contains only T3–T10: T1 and T2 have no test functions. T5 accepts the fabricated harness response; T6 accepts the fixed RAR refusal; T7 tests `ApprovalGate` in isolation rather than through desktop `/ask`. Its “all tests” banner expressly claims only T3–T10.

Verification evidence:

- Frozen package diff against `985dc54`: none.
- RAR protected files diff: none.
- Current `rar_deterministic.py` SHA-256: `4DB775666868E09A9F7232707D67EC3B4070970A30145AD3C5B41BB86B5E1B95`.
- Direct frozen guard and M33.3-R anchor invocation: **PASS**.
- Live `http://127.0.0.1:8000/health`: **timed out**; no PID file was present.
- Pytest could not initialize because this audit environment has no writable temp directory; therefore no T3–T10 execution evidence exists.

Required remediation: route desktop requests through URI Core’s real `/ask` handler without middleware interception; integrate the actual M36/M37/M38/M39/RAR APIs and their authority/verification paths; make configuration runtime-consumed; correct lifecycle races; then add real T1/T2 and adversarial end-to-end tests before rerunning live verification.
