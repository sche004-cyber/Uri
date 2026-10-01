## Verdict: REJECT

The current desktop recovery/integration state is not ready for acceptance.

Major findings:

- The current working tree differs from the accepted baseline: [`Launch URI.bat`](C:/Users/cheta/Development/uri-m37-m39-integration/Launch%20URI.bat) is modified; `run_codex_audit.py` and `uri_workspace/model_roles.json` are untracked. The latter is effective runtime configuration and cannot serve as accepted, reproducible baseline evidence.

- The launcher has a backend-start race. The batch file directly starts `run_uri_server.py`, then invokes [`launch_uri.ps1`](C:/Users/cheta/Development/uri-m37-m39-integration/scripts/launch_uri.ps1), which can independently start the Scheduled Task. `MultipleInstances=IgnoreNew` protects only Scheduled-Task instances, not the direct Python process. This can produce duplicate startup attempts and a port-8000 collision.

- Single-instance UI protection is best-effort, not enforced. It checks `Get-Process uri_ui` after backend readiness, with no mutex or atomic handoff; concurrent launches can both start the app. It can also focus an unrelated `uri_ui.exe`.

- At audit time, `http://127.0.0.1:8000/health` was unreachable, no `uri_ui` process was running, and no listener on port 8000 was observable. The server log shows earlier successful starts, but not sustained current availability. Thus end-to-end desktop recovery was not live-verified.

- Shutdown is not graceful end-to-end: [`uri_server_ctl.ps1`](C:/Users/cheta/Development/uri-m37-m39-integration/scripts/uri_server_ctl.ps1) ultimately uses `Stop-Process -Force`; desktop exit does not coordinate backend shutdown or demonstrate deterministic port release.

- Main Ollama configuration is not the requested accepted configuration. Tracked defaults remain `qwen3:14b`; the untracked `model_roles.json` changes all roles to `qwen3.5:9b`. There is no `qwen3:0.6b` edge-chat configuration, and the default edge inventory is empty. This fails the required two-model deployment configuration.

- The UI/backend endpoint contracts are statically aligned: the Flutter HTTP client uses `/health`, `/ask`, `/capabilities`, `/providers`, and `/auth/me`, and matching FastAPI routes exist. However, its compiled default is `http://localhost:8000`, not the requested explicit `http://127.0.0.1:8000`; live verification was impossible while health was offline.

- M36/M37/M38/M39 components are preserved, but not integrated into the production `uri_core` desktop request path. Imports of `uri_v1.memory`, `edge`, `execution.harness`, and `office` occur in qualification/demo scripts, not `uri_core`. This contradicts the requirement to confirm desktop/backend reuse and integration.

Positive evidence:

- Frozen-boundary guard passed: `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`.
- Protected M33.3-R anchors passed: 8 replay and 24 frozen-LF anchors intact.
- No tracked or untracked changes were found under the frozen M36–M39 package paths.
- [`CodexCliAdapter`](C:/Users/cheta/Development/uri-m37-m39-integration/uri_v1/execution/harness/adapters.py) correctly constructs `workspace-write`, `approval_policy="never"`, default `network_access=false`, and rejects the named bypass flags.
- [`ApprovalGate`](C:/Users/cheta/Development/uri-m37-m39-integration/uri_core/core/approval_gate.py) enforces proposal → explicit decision → single-use consumption → dispatch, with session and argument binding. Approval resumption is also wired into `/ask`.

Regression status:

- Frozen guard: 1 passed.
- M38 harness run: 5 passed, 34 setup errors because this audit environment cannot create any temporary files. Those errors are environmental, not test failures; they provide no usable M38 validation.
- Full M36–M39, governance, Flutter, launcher, and live endpoint regression evidence was therefore not established.

The minimum remediation path is: restore one authoritative backend launcher path, add atomic desktop single-instance control, make shutdown/port-release behavior explicit and tested, commit the intended model configuration including the edge model, integrate the accepted v1 capabilities through the canonical `/ask` path, then rerun the full suites and live desktop launch/health/ask verification.
