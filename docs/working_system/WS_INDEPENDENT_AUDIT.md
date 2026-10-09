# Working System hardening — independent audit record

Reviewer: Codex CLI (`gpt-6-sol`, reasoning medium) through the local codex-exec MCP, read-only sandbox, in a
disposable clone (`C:\Users\cheta\Development\wsa`) reset to each candidate commit. Codex inspected source and diffs;
it cannot run tests in its sandbox, so its verdicts rest on static review. Test and live results come from this
session's own runs (`WS_TEST_EVIDENCE.md`). Codex output is a claim; every finding below was checked against the
source before it was repaired.

Scope of every round: `git diff 68cac3d..<candidate>` (68cac3d = accepted integration, Codex WS round 8) against
H-AC2..H-AC9 of `WS_HARDENING_PLAN.md`, plus the frozen-boundary and approval-boundary constraints.

| Round | Candidate | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 1 | `e6eddf7` | REJECT | F1 HIGH a load stopped before its spawn could start Runtime v1 after the lease was released; F2 HIGH a restart request could race a new turn; F3 MEDIUM AT_RISK start below the request and an UNKNOWN census proceeded without override; F4 MEDIUM a worker hanging before replying to `oi_turn` left the UI unaware; F5 MEDIUM the release wait timed out into a start | All confirmed. Repaired in `079bf0d` (loader reaping; restart gate on turns; UNKNOWN waits; release keeps waiting; pending-send liveness). F3's AT_RISK band was kept and justified with live evidence (plan §7 correction) |
| 2 | `079bf0d` | REJECT | F3, F4, F5 FIXED (AT_RISK revision "justified by the recorded measurements … not a reason for rejection"). F1 PARTIAL (lease released after a 330 s bound with a live loader); F2 PARTIAL (unreadable report opened the gate); new MEDIUM gate timestamp; new MEDIUM late reply from a replaced worker | Confirmed. Repaired in `550843a` (no time bound; DONE marker per request; runtime identity check in `send`) |
| 3 | `550843a` | REJECT | F1 and late-reply FIXED. HIGH any `psutil` error counted as a dead host; MEDIUM superseded request could strand the gate; MEDIUM send allowed during restart | Confirmed. Repaired in `f987025` (positive-evidence liveness with a 15 s heartbeat; per-request results, gate follows the latest request; no send while restarting) |
| 4 | `f987025` | REJECT | All round-3 items FIXED. HIGH the `gpu_lease run` workload could outlive a crashed holder; MEDIUM timings of a previous instance could count without a host report | Confirmed. Repaired in `f8dd67b` (workload in the holder's kill-on-close job via the accepted `spawn_contained`; timings keyed to the verified server pid + start time) |
| 5 | `f8dd67b` | REJECT | Both FIXED. MEDIUM the host's calibration was not bound to the server readiness verified | Confirmed. Repaired in `9808fb6` (calibration carries pid + start time, cleared on stop, ignored for another instance) |
| 6 | `9808fb6` | **ACCEPT** | Round-5 item FIXED; "no new or regressed HIGH/MEDIUM findings against H-AC2..H-AC9"; frozen and accepted protected paths unchanged; scope-guard additions exact paths only | — |

Rounds 7-10 reviewed the changes made after round 6 (live-validation fixes and the reports), scope `git diff 9808fb6..<candidate>`:

| Round | Candidate | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 7 | `2831586` | REJECT | HIGH host re-measurement not coordinated with user turns, could hold stop requests 120 s; MEDIUM evidence implied an app-level Restart URI click; MEDIUM two host observations without committed receipt; LOW status still said 1 GiB | Confirmed. `47c1b6d`: /slots-gated bounded re-measurement; wording; receipt `brain_host_report_0858_before_freeze.json`; status fix; SAFE-1 recorded |
| 8 | `47c1b6d` | REJECT | Click wording and status FIXED. HIGH re-measurement still racy between the last /slots check and the request; MEDIUM SAFE-1 figure (2.6 GB) vs receipt (3,678 MiB) and an unsupported lease statement | Confirmed. `b5fd75c`: the host sends nothing to the Brain after the start calibration (memory taken after load becomes a reported warning; real-answer timings decide DEGRADED); figures and lease history corrected |
| 9 | `b5fd75c` | REJECT | Race FIXED. MEDIUM an unknown residency sample cleared the warning; MEDIUM "2.6 GB at 08:37" not in a receipt | Confirmed. `9ae28f4` |
| 10 | `9ae28f4` | **ACCEPT WITH FINDINGS** | Both FIXED; "no remaining HIGH or MEDIUM production-code defect against H-AC2-H-AC9"; MEDIUM documentation: the status table called post-round-6 components "Independently Accepted (round 6)" | Repaired in the final status document (labels now name round 10 at `9ae28f4`) |

After round 10: `1401aba` restored LF line endings on five files that text-mode patch scripts had turned into CRLF (finding INT-EOL-1, reported by the Text Intelligence session); `git diff -w --ignore-cr-at-eol 9ae28f4 1401aba` is empty, so the reviewed content is unchanged. Later commits are documentation and evidence only (listed in `WS_INTEGRATION_RECEIPT.md` §7) and were checked by the final Codex documentation round recorded in §2.

## 1. Boundary statements Codex made (each round)

- No file under `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/` or `model_lab/integration/` changes.
- Within the accepted OI package only `worker_bridge.py` (a WS-owned file) changes; `gpu_lease.py` and `brain_health.py`
  are new.
- `tests/phase2a/test_frozen_core.py` and `scripts/phase2close_chain.py` change only by enumerated exact paths
  (owner decision WS-D3).

## 2. Final documentation round

| Round | Candidate | Verdict | Findings | Disposition |
|---|---|---|---|---|
| docs-1 | `1b424a2` | REJECT (documentation evidence only; the round-10 code verdict unchanged; `9ae28f4..1401aba` content-empty diff and docs-only changes after `1401aba` verified) | MEDIUM receipt §7.4 placeholder; MEDIUM this §2 placeholder; MEDIUM final suite counts without committed output; MEDIUM SAFE-1 OS events without receipt | Repaired: remote confirmation recorded (§7.4 of the receipt); this table; `pytest_ws_final.txt` (65 passed) and `flutter_test_ws_final.txt` (36 passed) committed, full-suite counts labelled session-reported; `safe1_os_events_20261009.txt` committed |
| docs-2 | see the commit after the repair | see below | | |
