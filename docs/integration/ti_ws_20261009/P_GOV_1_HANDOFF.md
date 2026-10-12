# P-GOV-1 handoff: URI app windows and the machine-wide GPU lease

Date: 2026-10-09. From: the Text Intelligence session. To: the owner of the canonical GPU lease and launcher (the
Integration / WS-hardening session). The companion-voice session owns the perf runners named in item 3.
Status: **PLANNED (handoff).** Nothing below is implemented on the TI branch. The files involved are shared
infrastructure on the canonical branch (`uri_operational_intelligence/gpu_lease.py`,
`scripts/launch_uri_working_system.ps1`) and other sessions' test drivers, so the TI branch does not edit them (owner
instruction: hand off rather than modify unrelated owned files).

## Problem, as measured

1. Frozen Runtime v1 leaves about 85 MiB of the 16,368 MiB card free next to the desktop.
2. A Living window takes 126-480 MiB.
3. A GPU consumer that appears **after** the Brain loaded leaves the Brain at about a third of its speed until it
   restarts, even after the consumer closes:
   - companion-voice §4.4: 160 → 45-50 tok/s, 51 after the window closed;
   - hardening host report at 08:37: 3,678 MiB non-local at 33.7 tok/s, with 3-5 `uri_ui.exe` of several sessions.
4. With the window opened **first**, the Brain runs at 133-147 tok/s and the companion keeps 144.7 FPS (UI-first).
5. App windows are not lease clients, so a session's test window can land in the middle of another session's Brain
   benchmark or live test. The census sees it only afterwards.

## Smallest compatible change (no new framework, no mandatory lease for UI)

1. **Advisory check in the existing lease module.** Add `gpu_lease advise --window [--mib N]` plus a Python
   `advise_window(expected_mib=480)`. It is read-only: no lock is taken and nothing is stopped. It reads `status()`
   and `census()` and returns one of:
   - `GO`: no Runtime v1 server is resident, or the census margin can take the window;
   - `WAIT_HEAVY` (exit 75): the lease is held with purpose `benchmark`, `regression_chain`, or `runtime_v1_brain`
     with a live-test/benchmark label. A test or capture window should wait (`--wait S`, the same polling as
     `acquire`);
   - `WILL_DEGRADE_BRAIN` (exit 76): a resident Runtime v1 server, and a margin smaller than the window. Opening now
     will probably demote the Brain until it restarts. The message names the consumer and the fix: open windows
     before the Brain starts, or use Restart Brain afterwards. The host's residency alert already reports it.
   The user's own interactive Companion is never blocked. The app does not need to call this. If it does, only a
   hint is shown.
2. **UI-first launcher order.** Today the launcher starts the Brain host and then the window seconds later (step 1,
   then step 4). The host's fit check can therefore run before the window exists, and the load then shares the card
   with it. Start (or reuse) the window first, wait for the window's process to exist, and then start the Brain host.
   The host's fit check then counts the window, which is the order measured at 133-147 tok/s. Lease ownership and
   release do not change.
3. **Test drivers call the advisory.** Scripts that open URI windows for testing or capture call
   `gpu_lease advise --window --wait 1800` first and record the verdict in their evidence:
   - `docs/working_system/tools/capture_ws.ps1` (canonical);
   - companion-voice `rnd/voice/run_perf.ps1` and `rnd/companions/settings/brain_contention.py`;
   - live UI tests that start a Flutter window.
   On `WILL_DEGRADE_BRAIN`, a benchmark marks itself invalid instead of reporting a slowed Brain as a result.

## Acceptance tests for the implementing session

- **Unit (fake census and fake lease records):**
  - every verdict and exit code;
  - an unreadable census gives `WAIT_HEAVY`, never `GO` (fail closed for tests, never blocking the user);
  - `advise` never acquires the lock and never writes `lease.json` or `history.jsonl`.
- **Launcher self-test:** the window process exists before `ws_brain_host.py` is started. A reused Brain host
  still opens the window.
- **Live, under the lease, one run:** a UI-first start through the launcher gives the Brain's calibration ≥ 120 tok/s
  with a window open. `advise --window` reports `WILL_DEGRADE_BRAIN` while a resident Brain has less margin than
  the window.
- Regression: the hardening suite (`tests/ws/test_ws_hardening.py`) and the launcher self-test pass unchanged.

## What the TI branch relies on meanwhile

Nothing. TI does not open windows or start a Brain by itself. Its live tests run under the lease with no other GPU
application, and they stop at the first sign of non-local growth.
