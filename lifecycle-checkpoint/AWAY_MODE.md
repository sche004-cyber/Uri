# Away mode — unattended operation while the owner is away (from 2026-10-11, 10+ days)

Owner request (2026-10-11): "continue but I will be away from computer for more than 10 days, find a way for it to
work while am away from pc". This file is the standing plan; every check-in follows it and records what it did.

## Mechanism

- A Routine fires into this same Claude Code session every 4 hours. Each firing is one check-in.
- At each check-in, Claude does the following:
  1. If the container was reset, restore it from `RESTORE.md`.
  2. Read the lifecycle state and the driver's state.
  3. Act on the outcome, following the rules below.
  4. Update this checkpoint and push it to `ccr-cab5ed06-9hwyc4`.
  5. Re-arm a watcher for the running driver.
- Between check-ins the lifecycle driver runs as a detached process, with independent reviewers and repair workers as
  separate `claude -p` processes, exactly as in an attended run.

- Routine `trig_015qjUTUMbs595nDBNdzpYBW` ("URI away-mode lifecycle check-in"), cron `16 */4 * * *` UTC, fires into
  session `session_01P2p3uVP5b87uL5UMyWApaJ`.
- Driver launches go through `lc-launch.sh <config>` (copy kept here; installed at `/tmp/claude-0/lc-launch.sh`), which
  accepts only configs under `/home/user/uri-wt/lifecycle-runs/`.
- Owner-approved narrow allow rules (2026-10-11) in the container's `~/.claude/settings.json`: that launcher,
  `create_trigger` and `send_later`. **Known limit:** a container reset loses these rules. A check-in after a reset can
  still restore, verify and push the checkpoint, but auto mode may refuse driver launches. That refusal is recorded as
  BLOCKED until the owner is back; it is never worked around.

## Queue (in order)

1. **W1/A0 closure** (running; active run record `W1-A0-closure-2`, config `lifecycle-runs/W1-A0-closure-2.json`;
   `W1-A0-closure` is superseded history). Independent ACCEPT on the exact commit, then the gates, then the D1 merge into
   `integration/git-sync-20261008` (expected tip `ce1a90c`) with a receipt.
2. **SSRF-1** (D2). Plan: `lifecycle-runs/SSRF-1_PLAN_DRAFT.md`. The branch is cut from the canonical tip after step 1,
   and `authorized_protected_changes` is `uri_core/tools/fetch_url.py` only.
3. **GRAPHIFY-LEAK-1 fix** (owner decision D12, 2026-10-11: "fix before W2"). A small milestone, with its branch cut
   from the canonical tip after SSRF-1. Each user's Graphify view rebuilds its memory pointers from that user's own
   memory store. `authorized_protected_changes` is `uri_core/app/server.py`, plus `uri_core/core/graphify_index.py`
   only if needed (named explicitly). The regression test is the confirmed reproduction in
   `lifecycle-runs/findings/GRAPHIFY-LEAK-1/`, made self-contained. Independent review, then D1.
4. **W2a, then W2b** (see plan §4d). W2: plan and acceptance criteria in `lifecycle-runs/W2_PLAN_AND_ACCEPTANCE.md`, from the owner's "W2 Web &
   Document Intelligence: Implementation Instructions" (2026-10-11, recorded as D9) reconciled with the earlier brief.
   The plan supersedes the brief where they differ (approved scopes only, manual refresh, OCR over vision). Starts only
   after SSRF-1 is accepted and integrated. Owner-gated but not blocking: the approved domain list. Earlier owner
   direction, 2026-10-11:
   - Downloaded documents are temporary. Each is read, then deleted when the work is done, including on failure or
     cancel; leftovers are swept at the next start.
   - What stays is a memory record: source URL, site, the menu path where the document was found, the linking page,
     title, date, reference number, per-page text, content hash and retrieval time.
   - Relations go in the existing M23 `GraphStore`: notice → attachment, corrigendum → original, same reference number,
     same department, supersedes.
   - Answers cite URL and page, and quote numbers from the stored text (D7).
   - Correction to the earlier "PDF-to-image library needs an owner decision": URI already ships PyMuPDF and
     pytesseract (`requirements.txt`, `uri_core/services/pdf_reader.py`). Scanned PDFs therefore use the existing
     `PDFReader` OCR, with no new dependency. OCR needs Tesseract installed on the PC: NOT VERIFIED in the cloud.
   - Still open, with conservative defaults until the owner decides:
     - no scheduled refresh;
     - the benchmark site list is a proposal only;
     - personal data in public documents (for example names in results lists) is indexed for search only and never
       written to user memory or learning (D5);
     - no permanent copies of PDFs are kept.
5. **SCHED-TOKEN-ACL** (pre-existing issue, reported by the URI OFFICE thread on the owner's PC, 2026-10-11; NOT
   VERIFIED from the cloud).
   - **The issue:** the scheduler's `<state>/api-token` file inherits nine ACL entries, including
     `CodexSandboxUsers` with modify rights. Processes running as Codex sandbox users could read or replace the token
     and call the scheduler API as the owner.
   - **The fix:** in `uri_scheduler/service.py` (not frozen), restrict the token file AND its folder to the current
     user. It needs a Windows ACL test, so it is a small lifecycle milestone run where Windows is available. Not
     started from the cloud.
6. **RW1** is NOT started unattended. Its benchmark needs Windows and WebView2 on the owner's PC.

## Code graph (graphify)

The repository rule is "after modifying code, run `graphify update .`".

- In this cloud container, graphify (`graphifyy` 0.9.5, the same version as the repo's skill) is installed as a
  developer tool with `uv tool install`. It is not a URI dependency.
- Its output is not git-ignored and the `.gitignore` is frozen. Generating it inside a milestone worktree would
  leave untracked files that make the candidate dirty, and excluding them via `.git/info` would set off the
  GIT_CONTROL tamper check.
- So the graph is built from a clean `git archive` export, outside the repository:
  - `/home/user/uri-wt/graphs/canonical`: rebuilt after every canonical integration.
  - `/home/user/uri-wt/graphs/<milestone>`: rebuilt after a milestone's accepted commit.
  - Lesson (2026-10-11 07:35): once graphify was installed, a repair worker followed the repo rule, ran
    `graphify update .` in the worktree and then deleted the tracked `graphify-out/` files. The driver refused this
    as OUT_OF_SCOPE and restored the worktree. **Every milestone config therefore carries an environment note:** no
    graphify writes in the worktree; use the read-only graph outside the repo.
  - New milestone configs give workers this path as an environment note, so they can run `graphify query/path/explain
    --graph <path>/graphify-out/graph.json`.
- A rebuild takes about 1 minute (AST only, no API cost). After a container reset it is simply rebuilt; it is not
  stored in git.
- On the owner's PC, the local `graphify-out/` is updated by the owner's own graphify setup after pulling.

## Allowed unattended (already authorised)

- Lifecycle runs, repairs, reviews and gates (skill policy).
- D1 merge integration after the driver's own evidence checks.
- The D2 change to `fetch_url.py` only.
- Pushes to the session branch.

## Never unattended (waits for the owner)

- Production deployment or cutover.
- Any other frozen-file change.
- New runtime dependencies.
- Edits to `~/.gitconfig` (the three leftover test entries stay until the owner removes them).
- Weakening gates or suppressing findings.
- RW1, the social-search hand-off and YouTube work.
- Any blocker whose `needs` names the owner, except this one: a TAMPER whose only cause is a container reset
  (a different reviewer CLI path or version, or fresh git config).
  - It may be unblocked only after inspection, with a note that lists what changed.
  - If anything else changed (hooks, repo config, refs, `url.*`, filters), the run stops and waits.
- **Budget:** each milestone keeps its own lifecycle budget (W1/A0: $400, 30 rounds, 36 h). The whole away period is
  capped at **$600 of worker spend**. On reaching the cap, work stops at a checkpoint and waits.

## If a check-in cannot act

Permission refusals, missing tools or network blocks are recorded here and in the closure report as BLOCKED. Claude
retries at the next check-in and never works around them. After 3 check-ins in a row with nothing new and nothing
runnable, the Routine is paused and the reason is written here.

## Check-in log

| UTC | What happened |
|---|---|
| 2026-10-11 06:20 | Checkpoint created. W1/A0 round 9 review of `3dd9cde` running (driver PID 15820). Spend so far $32.94. |
| 2026-10-11 06:25 | R9 REJECT (6 blocking MEDIUM: R9-01..06), driver repairing. Allow rules added and routine created with owner approval. |
| 2026-10-11 06:30 | Owner switched back to Auto. Allow-rule test in auto mode: `lc-launch.sh` with a nonexistent config ran and refused (exit 2) - launches are permitted unattended. |
| 2026-10-11 06:40 | Owner direction for W2 documents recorded: temporary download, memory record and relations, then delete. PDF-library decision corrected: PyMuPDF and Tesseract OCR already exist. |
| 2026-10-11 06:43 | R10 REJECT (1 blocking: R10-01, a regression from the R9-01 fix). Three repair attempts refused: their test skipped on the pre-repair commit because new fixture files are not copied there. Diagnosis recorded; one environment note added (policy hash unchanged). REPAIR_FAILED and CONFIG unblocked with notes; driver relaunched (PID 16072). Follow-up queued: carry repair-added fixture files into the pre-repair checkout (lifecycle). |
| 2026-10-11 06:55 | D9 (W2 implementation instructions) received. Repository inspected; W2 plan with 14 acceptance criteria written and self-reviewed (no new owner decision needed except the approved domain list, not blocking). |
| 2026-10-11 07:10 | W1/A0 rounds 11-13: everything before is confirmed fixed, but the hidden-text blocklist was bypassed again (R11-01 class, diagnosis D6, OWNER_DECISION). Owner chose **D10: pixel-checked page text** (fail closed). Coordinator-directed implementation by a separate agent in progress, following the D7/D8 precedent; independent review follows. Spend $49.90. |
| 2026-10-11 07:15 | graphify installed (cloud developer tool) and the canonical `ce1a90c` graph built outside the repo (23,413 nodes, 49,620 edges, 54 s; query checked). W2 plan: bounded cache for frequently needed documents added (owner direction, W2-AC15). |
| 2026-10-11 07:40 | Owner D11: W2 runs on ARN (no frozen change), plus a narrow frozen exception adding a `document` pointer kind to the runtime Graphify index. W2 plan updated (W2-AC16..18). GRAPHIFY-LEAK-1 **confirmed** by reproduction on canonical: the primary user's memory pointers (ID/category/consent, no content) reach other users' Brain hints. Pre-existing, frozen; fix awaits owner decision. |
| 2026-10-11 07:45 | Owner D12: fix GRAPHIFY-LEAK-1 as its own milestone after SSRF-1 and before W2 (frozen exception: server.py, plus graphify_index.py only if needed). Queue: W1/A0 → SSRF-1 → GRAPHIFY-LEAK-1 → W2. |
| 2026-10-11 07:35 | D10 implemented by a separate agent and reviewed by the coordinator: frozen check clean; 2650 assist+web tests pass; 17 new tests fail on d029f60 with real payload leaks. Committed `fcfb465`; OWNER_DECISION unblocked; driver relaunched (PID 24911) and resumed in FIXING on the new candidate. Ledger now records D9-D12. |
| 2026-10-11 07:40 | Diagnosis D7 on fcfb465 went to repair. Repair P14 was refused OUT_OF_SCOPE because the worker ran graphify in the worktree (coordinator-caused). Worktree restored. Graphify read-only note added (policy hash unchanged); W1/A0 graph built at graphs/W1-A0 (fcfb465). Unblocked; driver relaunched (PID 31137). |
| 2026-10-11 08:15 | Owner approved two W2 additions: named collections (W2-AC19) and the current-rules view built only from confirmed relationships (W2-AC20). W2 plan now has 20 acceptance criteria. |
| 2026-10-11 08:35 | Owner approved W2-AC21 (agenda-item index for BoG/Senate/FC/BWC minutes) and W2-AC22 (uploaded/Drive/local internal sources). Owner's DoPT-leave example generalised into FIND/LIST (W2-AC23) and SUMMARISE (W2-AC24) intents. W2 is one document-retrieval skill with five intents; delivered as W2a (core) then W2b (structured). |
| 2026-10-11 08:55 | Owner approved W2-AC25 (task → applicable rules → cited procedure; heater/GFR example; thresholds never from model memory) and asked for a UI placeholder to add sources → W2-AC26 (Sources & Rules A2UI surface with placeholders and add/approve actions; no catalog change). Found R-8: the A2UI catalog forbids URLs → `docs.open_document` action (server-side resolution, full URL confirmed before opening) in W2a. |
| 2026-10-11 09:05 | **R16 ACCEPT WITH FINDINGS on `67aff50`** (W1-A0-closure). The gates then reported 178 "new" failures. Diagnosis: the baseline gate ran 0 tests (`tests/web` missing at `ffdf534`) and the driver accepted it (driver defect, queued). A manual baseline run shows the failures are environmental; the only candidate-only one is flaky on both commits and already allowed. That result is recorded as invalid evidence. Gate fixed to run only existing folders (owner approved; nothing loosened). The driver cannot re-verify from FIXING, so the old run is superseded and `W1-A0-closure-2` re-plans the same candidate with the baseline pinned to merge-base `ffdf534`. Fresh independent review started 09:02. Spend so far: $69.73 in the old run. |
| 2026-10-11 10:00 | Office M1 (owner's PC thread, branch `phase/uri-office` 2fbbaed0 on `ce1a90c`, not pushed). Reported: HTTP service now copies the scheduler (127.0.0.1 + per-launch bearer token) plus Host and Origin guards; inline-string rule; real Excel fixture. It also reported a scheduler api-token ACL weakness on the PC, queued as SCHED-TOKEN-ACL. Unverified from the cloud. |
| 2026-10-11 10:25 | Office branch `phase/uri-office` da2a3de checked from the cloud. 4 commits on `ce1a90c`, no frozen or W1/A0 files touched, 63/72 tests pass on Linux (8 are Windows-path-only). BLOCKER found: 190.8 MB of `node_modules` (11,477 files) committed and pushed. **Owner approved** the Office thread rewriting and force-pushing `phase/uri-office` only, and deleting its `uri-agent` copy; the instructions were given as a paste box. Also flagged: the blueprint/architecture drift, the duplicated `untrusted` helper, and `@grpc/grpc-js`, which is not on the approved download list. |
