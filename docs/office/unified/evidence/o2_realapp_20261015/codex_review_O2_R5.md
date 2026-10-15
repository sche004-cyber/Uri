# Independent review of the O2 real-application repairs (R5) — Codex

Reviewer: Codex CLI 0.158.0, model `gpt-6-sol`, reasoning effort medium, read-only sandbox, via the local
`codex-exec` bridge (ChatGPT login; the user's Codex config carries `windows.sandbox = "unelevated"`, so shell
commands ran). Working copy: disposable clone `C:\cx\o2r5` (`core.autocrlf=false`). No repair authority. In every
round Codex's pytest attempt stopped before collection ("No usable temporary directory found" under the read-only
sandbox); test results below are the author's runs, not the reviewer's.

| Round | Commit | Codex thread | Verdict | Findings |
|---|---|---|---|---|
| 1 | `fe7ed88a` | 01a13f37-5387-7f11-975f-980241a18d36 | REVISE | O2-R5-01 MAJOR token written before bind; O2-R5-02 MAJOR OfficeError inside verify_full left 'verifying'; O2-R5-03 MINOR reachable() accepted any HTTP answer; O2-R5-04 MINOR retry/close race. Noted: WebDAV canary has no positive control. |
| 2 | `b84062cf` | 01a13f41-994e-7280-9d55-6ee371823a1a | REVISE | 01 and 02 closed. O2-R5-05 MAJOR exclusive bind may block a quick restart on the fixed port; 04 and 03 still MINOR. |
| 3 | `f27f6bbf` | 01a13f47-0239-7662-a1cb-076a72600ecb | **ACCEPT WITH FINDINGS** | 05 no longer MAJOR (test + Windows measurement; the measurement is the author's claim). Open MINOR limitations: O2-R5-04 (check and cache copy not atomic; a close during conversion can still let a finished preview reach the shared cache or a conversion run against the deleted folder; the session itself is gone), O2-R5-03 (a program that returns `{"contract": ...}` on the recorded port with any token would still be taken as reachable), O2-WebDAV (no WebDAV positive control; NOT VERIFIED, starting WebClient not authorised). |
| 4 | `5973583b` (R6, after real-app run r2) | 01a13f5a-7fdb-7110-ae8c-7e6c22b17030 | REVISE | O2-R6-01 MAJOR "Open it" opened a recent path matched by basename, bypassing picker confirmation (contract: a recent entry is not a grant); MINOR O2-R6-02 Han text resolved by union of language tags, O2-R6-03 all numbering definitions counted, O2-R6-04 script ranges incomplete. |
| 5 | `6de5b32f` | 01a13f64-93f8-7831-8f94-efeaa7baf722 | **ACCEPT WITH FINDINGS** | R6-01 fixed (picker). Open MINOR: numbering lvlOverride/numStyleLink not followed and unused levels of a used definition counted (probe-confirmed by Codex); O2-R6-02; O2-R6-04 partial; widget test does not tap "Open it…"; carried O2-R5-03, O2-R5-04, WebDAV NOT VERIFIED. |

Author's verification of the round-1 and round-2 findings before repair: all confirmed in source. While confirming
O2-R5-01 the author also found that Python's `HTTPServer` sets `SO_REUSEADDR`, which on Windows let a second process
listen on 127.0.0.1:18530 beside a running service (probe printed `SECOND BOUND (port shared!)`); repaired with
`SO_EXCLUSIVEADDRUSE` in `b84062cf` (test `test_the_office_port_cannot_be_shared`). Quick-restart probe on this PC
(scratchpad `restart_probe.py`): exclusive, plain and reuse variants all rebound immediately after 5 requests; an
in-process rebind with an open accepted connection bound; a relaunch after killing the serving process bound.

Author's test runs at `f27f6bbf`: `tests/office_u2` + `tests/devices` (not engine) 193 passed; `tests/office` +
`tests/a2ui` 483 passed, 5 skipped (at `b84062cf`, unchanged files since); real-engine suite 16 passed (at
`fe7ed88a`; the engine code paths changed later only in the verify wrapper and signature error code, covered by unit
tests); Flutter suite 599 passed, 5 skipped (at `f27f6bbf`); `tests/office` + `tests/a2ui` re-run at `f27f6bbf`: 483 passed, 5 skipped.
