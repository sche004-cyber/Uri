# Cloud test evidence: 2026-10-10

## Environment

| Item | Value |
|---|---|
| Checkout | separate detached worktree `/home/user/scratch-ti` at `54ad7be72847675ae662e2fd4f3b3b9d253e6d4e`. The research worktree was not used, so it stayed clean. |
| OS / Python | Linux (cloud container), Python 3.13.16 |
| Virtualenv | scratchpad venv, `pip install -r requirements.txt pytest httpx` |
| Extra packages | `google-api-python-client google-auth-oauthlib google-auth-httplib2` |

The Google client libraries are imported by `uri_core` but **not declared in `requirements.txt`**. Without them, 11 of
the Line A test modules failed at collection with `ModuleNotFoundError: No module named 'google'`. This is a
dependency-declaration defect (D-REQ-1, low severity).

## Run 1: Line A multi-user, auth and isolation, plus A2UI and the harness boundary

**Result: `COMPLETED_WITH_RESULT` — 315 passed, 16 subtests passed, 0 failed, 1 warning (29.87 s).**

```
python -m pytest -q -p no:cacheprovider test_user_accounts.py test_multi_user_isolation.py
  test_m22_2_roles_sessions.py test_m22_3_route_authorization.py test_m22_3_bind_refusal.py test_m22_3_cors.py
  test_m22_3_rate_limiting.py test_m22_4_capability_resolver.py test_m22_4_grant_endpoints.py test_auth_session.py
  test_devices.py test_multi_client_runtime.py test_m32_gmail_user_scoping.py test_m21_file_store_isolation.py
  test_graph_isolation.py test_usage_endpoints_isolation.py test_provider_keys_boundary.py
  test_m22_5_providers_endpoints.py test_m31_harness_boundary.py tests/a2ui
```

This run is the cloud baseline that S1 and S3 must not regress.

**What this run does NOT show.** The suite passes *with* the anonymous-fallback behaviour (R1) and *without* any test
for R3. Passing tests therefore do not mean those risks are absent.

## Run 2: subsystem suites (platform probe)

| Suite | Result | Classification |
|---|---|---|
| `tests/scheduler` | 56 passed, 15 skipped | `COMPLETED_WITH_RESULT` (the cross-platform part) |
| `tests/ws` | 303 passed, 12 failed, 14 skipped | Failures are in `test_ws_hardening.py` (GPU lease and host). Root cause: `msvcrt` is unavailable on Linux. **Platform-blocked, not passed** |
| `tests/oi` | 141 passed, 20 failed, 161 errors, 8 skipped | Dominated by `ModuleNotFoundError: No module named 'msvcrt'`. **Platform-blocked** |
| `tests/phase2a` | 92 passed, 73 failed, 5 skipped | Dominated by `msvcrt` and `WINDOWS_REQUIRED` (Job Objects) |

Root-cause count across the three failing suites (`-rfE` output): 190 × `No module named 'msvcrt'` and
4 × `WINDOWS_REQUIRED`.

**Not individually root-caused:** every remaining failure was not traced one by one. Some `tests/phase2a/test_ledger.py`
failures may have a different cause, such as SQLite version behaviour. No claim is made about these suites in either
direction. They must be run on the owner's Windows PC.

After both runs, `git status --porcelain` in the test checkout showed 0 entries: the tests left no tracked-file changes.

## Run 3: SSRF probe against `fetch_url` (2026-10-10)

**Result: `COMPLETED_WITH_RESULT` — defect SSRF-1 confirmed.**

**Method:** a throwaway script in the session scratchpad (not committed) did three things:
1. Started a local HTTP server bound to `127.0.0.1`, which serves a page containing `INTERNAL_ONLY_MARKER`, plus a
   `/redir` path that sends a 302 to that page.
2. Called `FetchUrlTool().execute(request_text="please read http://127.0.0.1:<port>/<path>")` from the canonical
   checkout, using the same virtualenv as Run 1.
3. Checked whether the marker appeared in the tool's result.

**Output:**
```
/internal success MARKER_LEAKED
/redir success MARKER_LEAKED
```

**Meaning:**
- `fetch_url` reads loopback services, and it follows redirects into them.
- It is registered READ_ONLY (`uri_core/capabilities/registry.py:20`) and is in the active registry
  (`uri_workspace/capabilities_registry.json`), so it needs no approval.
- On the server, `127.0.0.1:18470` (Runtime v1 with no API key, OI-SEC-1) and other loopback and LAN services would be
  reachable by any user whose request text contains such a URL.

**Not tested:**
- Private LAN ranges and the cloud metadata address. These were not reachable from the sandbox, and the code has no
  address checks of any kind (`fetch_url.py:103-131`).

After the run, `git status --porcelain` in the test checkout showed 0 entries.
