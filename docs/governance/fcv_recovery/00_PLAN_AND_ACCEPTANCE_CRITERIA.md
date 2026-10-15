# FCV recovery: plan and acceptance criteria

**Milestone:** URI Frozen Core Recovery & Integration Reconciliation (FCV-R-20261014). It follows FCV-20261014, whose verdict was BLOCKED.

| Item | Value |
|---|---|
| Baseline | canonical `uri-repo/integration/git-sync-20261008` = `1b5423bc15fd7e5da9161c862cf839925da9f2eb`, verified by fetch on 2026-10-14 |
| Frozen Core | tag `accepted/phase1-core-freeze-31a34dcb` → `925ad45c`, checkpoint zip `31a34dcb…98cf7` |
| Candidate branch | `recovery/fcv-core-reconciliation-20261014` |

Scope: repair the FCV findings with the smallest evidence-backed changes, reusing the repairs on the recovery line `2e3262cd` without its Office/Assist work. No redesign, no Office qualification, no deployment or cutover.

## Acceptance criteria

The independent reviewer checks the candidate against each criterion below.

| ID | Criterion | Evidence required |
|---|---|---|
| AC-1 | Frozen integrity | (1) 118 of 121 frozen files are byte-equal to `925ad45c`. (2) The only differences are the owner-authorized exact blobs: `uri_core/app/server.py` → `59cfde59` (security D12); `scripts/phase1_offline_rollback.py` → `50f8540d` (FCV-01, OWNER-FCV01-20261014); `scripts/uri_client.ps1` → `3a011277` (FCV-05, OWNER-FCV05-20261015). `uri_core/tools/fetch_url.py` → `404e6092` is the approved security blob on a non-frozen path. (3) The historical runtime carries server.py, fetch_url.py and uri_client.ps1 at their approved bytes and keeps the original rollback tool. (4) `scripts/ws_frozen_check.py` reports `ok=true` on the candidate. |
| AC-2 | FCV-03 | (1) A runtime materialized from the candidate holds the approved security blobs. (2) The materializer refuses its own output unless verification passes. (3) A direct `FetchUrlTool` call refuses: loopback (127.0.0.1, localhost, `127.1`, decimal form, `::1`, IPv4-mapped IPv6, 0.0.0.0, port 80 and port 18889); private ranges (10/8, 172.16/12, 192.168/16, 100.64/10); link-local (169.254.169.254, fe80::1); non-http schemes; redirects to loopback, localhost, link-local and private addresses; DNS rebinding to loopback. (4) Every refusal happens with zero canary hits. (5) A pre-security negative control does reach the canary. (6) A regression test fails if the materializer stops reconciling or verifying. (7) The live server path never shows canary content. |
| AC-3 | FCV-07 | (1) The root cause is shown reproducibly: the new tests fail on canonical and pass on the candidate. (2) Through the production UI, real worker, Core and Brain: same-session context; approval-gated memory creation; recall after an application restart; client isolation (a second installation does not know the fact); a denied write is not stored; conflicting memories are reported; missing information is not invented. |
| AC-4 | FCV-01 | (1) The owner authorized the exact amendment. (2) The exact frozen checkpoint rehearses: all 121 files byte-equal, metadata verified and not restored. (3) Every existing rollback refusal still passes. (4) A tampered archive is refused before anything is written. (5) A failed rehearsal writes no success evidence. (6) The frozen checker requires the amendment once its anchor is in ancestry. |
| AC-5 | FCV-04 | `ws_frozen_check` passes on the candidate without path-wide exceptions. Its negative tests pass. |
| AC-6 | FCV-02, FCV-09 | (1) `uri_web` is present in the materialized runtime. (2) Fixtures are installed by exact hash and refused on mismatch. |
| AC-7 | FCV-05 | Diagnosed in disposable copies. The cause is stated only if evidence shows it. Otherwise it is "not reproduced; cause not established". |
| AC-8 | UX: Brain startup, capability discovery, interface accuracy, completion | (1) Startup never shows a raw `STOPPED` state; it names the real phase. (2) No `<<ACTION>>` marker is shown, including when split across stream chunks. (3) No simulated rows appear in the live context rail. (4) Chips show plain words, with the raw code in a tooltip. (5) A verified save names the saved fact, read from the client store. (6) There is no generic "independently verified" claim. (7) Discovery answers get a semantic review. |
| AC-9 | Regressions | Each gate is compared by test ID with its baseline: (1) source gates: combined, security and governance; (2) Flutter; (3) the historical runtime chain (phase2, authority, Phase 1 full suite and scope). A failure is acceptable only when the same test fails on the baseline for the same cause. |
| AC-10 | Live Windows | (1) Original production `main()`, real worker, paired Core and real Runtime v1 Brain, on this PC. (2) Automation input is labelled as automation. (3) Physical keyboard and manual dialogs are reported as NOT VERIFIED. |
| AC-11 | Independent review | A separate reviewer process, with no implementation authority, reviews the exact candidate SHA. The verdict and its findings are recorded verbatim. Repairs are re-reviewed. |

## Owner decisions

- FCV-01: "Authorize amendment", 2026-10-14 23:47 +05:30.
- FCV-05: "Authorize amendment", 2026-10-15 07:35 +05:30.
- GPU contention override for this milestone's live runs: "Temporary override".
- Canonical integration, deployment and cutover are not authorized by this plan.
