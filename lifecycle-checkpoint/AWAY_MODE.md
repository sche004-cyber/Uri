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
   `integration/git-sync-20261008` (expected tip `cbdf3f2c` since DEV-LIFECYCLE-2 integrated) with a receipt.
2. **SSRF-1** (D2). Plan: `lifecycle-runs/SSRF-1_PLAN_DRAFT.md`. The branch is cut from the canonical tip after step 1,
   and `authorized_protected_changes` is `uri_core/tools/fetch_url.py` only.
2b. **IDN-1** (owner decision D21, 2026-10-11: block site addresses with non-English letters, and tell the user why in plain words). Plan: `lifecycle-runs/IDN-1_PLAN_DRAFT.md`. Branch from the canonical tip after SSRF-1.
2c0. **SETTINGS-1** (owner decision D28: everything set up in the app, no `.env`). Plan: `lifecycle-runs/SETTINGS-1_PLAN_DRAFT.md`. Builds the Security tab (all keys) and Connections section, imports `.env` once, and replaces the fixed default key-store password with a DPAPI-protected per-install secret. Branch after IDN-1.
2c. **LINK-REP-1** (owner decision D22, 2026-10-11: "Yes"). Known-scam lookup for real addresses, plus urgency and mismatched-link flags. Plan: `lifecycle-runs/LINK-REP-1_PLAN_DRAFT.md`. Branch after IDN-1. Provider URLhaus, skip when unavailable (owner). Key optional (D25): the check is added security, never a blocker.
3. **GRAPHIFY-LEAK-1 fix** (owner decision D12, 2026-10-11: "fix before W2"). A small milestone, with its branch cut
   from the canonical tip after SSRF-1. Each user's Graphify view rebuilds its memory pointers from that user's own
   memory store. `authorized_protected_changes` is `uri_core/app/server.py`, plus `uri_core/core/graphify_index.py`
   only if needed (named explicitly). The regression test is the confirmed reproduction in
   `lifecycle-runs/findings/GRAPHIFY-LEAK-1/`, made self-contained. Independent review, then D1.
4. **ONBOARD-1** (owner request 2026-10-11): first-use explainer card per ability per user, starting with Assist.
   Plan: `lifecycle-runs/ONBOARD-1_PLAN_DRAFT.md`. No frozen file, dependency or permission; independent review, then D1.
5. **W2a, then W2b** (see plan §4d). W2: plan and acceptance criteria in `lifecycle-runs/W2_PLAN_AND_ACCEPTANCE.md`, from the owner's "W2 Web &
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
6. **SCHED-TOKEN-ACL** (pre-existing issue, reported by the URI OFFICE thread on the owner's PC, 2026-10-11; NOT
   VERIFIED from the cloud).
   - **The issue:** the scheduler's `<state>/api-token` file inherits nine ACL entries, including
     `CodexSandboxUsers` with modify rights. Processes running as Codex sandbox users could read or replace the token
     and call the scheduler API as the owner.
   - **The fix:** in `uri_scheduler/service.py` (not frozen), restrict the token file AND its folder to the current
     user. It needs a Windows ACL test, so it is a small lifecycle milestone run where Windows is available. Not
     started from the cloud.
7. **RW1** is NOT started unattended. Its benchmark needs Windows and WebView2 on the owner's PC.

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
| 2026-10-11 10:40 | Office rewrite verified from the remotes: `phase/uri-office` 14cff587 has no node_modules in any commit, tree = da2a3de plus 3 new files, base ce1a90c, uri-agent copy deleted, canonical unchanged. W1/A0 run-2: R4 and R5 REJECT, then RETRY_LIMIT (R5-01 '_'/'-'-wrapped links; R5-02 D7 qualifiers dropped at claim edges). Coordinator repair `29771992` (D10 precedent; 38/50 new tests fail on f5a5b8e; web+assist+a2ui 3002 pass; two older tests' sources given commas, recorded). Unblocked, relaunched (PID 3397). R6 REJECT: R6-01 one-sided spaced dot and dot-like separators (R1-01 class, 6th recurrence); R6-02 comma edge still lets a qualifier go (coordinator's rule too loose — correction recorded). Driver repairing. Link-detection scope question put to the owner. Spend run-2 ~$30. |
| 2026-10-11 11:05 | Owner decisions D13 (mask any dot-joined word) and D14 (Brain-worded claims run sentence edge to edge). Driver stopped mid-repair (its worker had written nothing); coordinator repair `806dcd12` (60/72 new tests fail on 29771992; web+assist+a2ui 3126 pass; ledger rows added). Driver relaunched (PID 10652), CANDIDATE_MOVED recorded, re-diagnosing. Owner request: first-use explainers, queued as ONBOARD-1 before W2a (W2-AC27 added). |
| 2026-10-11 12:10 | W1/A0: R7 REJECT then R8 RETRY_LIMIT (R8-01, link class 8th time: letter-category dots, spelt-out TLD). Owner D15 "allow-list + accept rest": coordinator repair `66a4765a` (30/50 new tests fail on 474adb84; web 1032 + assist/a2ui 2313 pass; residual risk stated in the AC file). Note: an earlier draft overwrote the driver's own round-8 test file; caught by a test-count drop and restored before commit. Relaunched (PID 7651). Owner direction DEV-LIFECYCLE-2 (Windows support + canonical remote): plan, candidate `f3706e03` on `milestone/dev-lifecycle-2-20261011` from ce1a90c (tests/dev_workflow 212 pass + 5 platform-gated on Linux; 11 new F1/F3 tests fail on ce1a90c). Driver launched with canonical ce1a90c driver (PID 2971), fast-forward integration authorised under D1. |
| 2026-10-11 12:30 | **DEV-LIFECYCLE-2 handed over to another thread (owner).** Run stopped before any review result (driver, then the orphaned reviewer); candidate `f3706e03` kept in the bundle; handover instructions given to the owner. Not resumed here. W1/A0: driver's own P7 `7b1252f7` (R9-01); R10 review NO_RESULT (verdict outside the result block) with real finding R10-01 (look-alike dots from listed scripts). Owner decision **D16** ("the separator does not matter": name + anything + real top-level domain, offline list; web search rejected): coordinator repair `6b07b467` (31/61 new tests fail on 7b1252f7; web 1159 + assist/a2ui 2313 pass). Relaunched (PID 8369). |
| 2026-10-11 12:55 | W1/A0 R11 on `6b07b467`: REJECT, then RETRY_LIMIT. Blocking: R11-01 (link class again: 12-character gap cap, 'co m'/'sh op' splits, a lone 'ʘ', 'xn--p1ai') and R11-02 (httpx.InvalidURL ended the whole research job as INTERNAL_ERROR). Five non-blocking LOW findings (R11-03..07) recorded. Coordinator repair `834c1c30` (58/74 new tests fail on 6b07b467, the 16 precision controls pass on both; web 1159 pass). Disclosed, NOT owner-accepted: a split ending after a common two-letter word ('to day') is not joined; precision cost 'the org chart' masked. Python gate running; then unblock and relaunch. |
| 2026-10-11 13:15 | Gate comparison (Linux, tests/ws oi a2ui web assist): 834c1c30 = 38 failed / 161 errors, 6b07b467 = 37 failed / 161 errors; identical except test_ws_hardening::test_host_requests_are_explicit_fresh_and_used_once, which flakes on both (1/5 and 1/3) and is in a file the repair does not touch. The shared failures are Windows-only (`msvcrt`, `powershell`). Unblocked with a note listing every change; driver relaunched (PID 24535). Correction: the first checkpoint push for 12:55 was rejected (bundle rebuilt without base exclusions, 218 MB); rebuilt with the earlier exclusions (482 KB) before any push. |
| 2026-10-11 13:40 | W1/A0 R12 on `834c1c30`: REJECT, RETRY_LIMIT again. R11-02 confirmed fixed. Only blocking: R12-01 (R1-01 class: a name in another script than the ending, 'пример com', 'refunds-portal ~ рф'). Coordinator repair `eedbc639`: any real word of a listed script is the name; only single/repeated foreign letters are separator; native sentence punctuation counts as prose (also fixes the R11 precision regression 'Tokyo (東京) in Japan.'). Reviewer's 24 R12 tests pass; own file 41 tests, 32/33 link tests fail on 834c1c30; web 1257 pass. Full gate running; then unblock and relaunch. |
| 2026-10-11 13:50 | Gate on eedbc639: 37 failed / 161 errors, the same set as 6b07b467 (Windows-only); the ws flake did not occur. Unblocked with a note listing every change; driver relaunched (PID 32246) for R13. |
| 2026-10-11 14:20 | W1/A0 R13 on `eedbc639`: REJECT, RETRY_LIMIT. Only blocking: R13-01 (the R12 repair read a short foreign word '丶丿'/'ㆍᆢ' or 'ʘʘ' as the name). Put to the owner before repairing, as promised. **Owner decision D17 "brackets + odd letters"**: a short word of another script is a separator unless alone in brackets as a gloss; a word of odd Latin letters is a separator. Residual: bracketed separator. Precision cost disclosed after the choice: unbracketed 'Tokyo 東京 is big' masked. Coordinator repair `842ad64d` (21/21 link tests fail on eedbc639; 7 controls pass on both; web 1274 pass). Gate running; then unblock and relaunch. Note: /tmp/uri_review_R13/test_r13_hidden.py is from run 1 (invisible text), unrelated. |
| 2026-10-11 14:45 | **Owner loosened D17** ("loosen it and let other checks discover it"): only one repeated letter or stroke/dot-shaped letters of another script are a separator; a real short foreign word is the name ('Tokyo 東京 is big' readable). Residual 'portal 中国 shop' owner-accepted. Repair `da10d0b8` (21 link tests fail on eedbc639; web 1302 pass; gate = baseline set plus a ws flake seen on 6b07b467 too). Unblocked with note; driver relaunched (PID 11013) for R14. Asked the owner what "arn and rar" refers to. |
| 2026-10-11 13:40 | **DEV-LIFECYCLE-2 review stage (cloud session session_013sHvxV).** Run record DEV-LIFECYCLE-2 VERIFIED at f3706e03 (then superseded by Windows findings W-1..W-3). DEV-LIFECYCLE-2-win (cloud W repair fcc0ebdd) superseded and stopped (owner). DEV-LIFECYCLE-2-r2 on the owner-PC candidate 73bdbef1: R1 REJECT (R1-01 precheck fail-open), repair 0ee6885a, R2 ACCEPT WITH FINDINGS, VERIFIED. DEV-LIFECYCLE-2-r3 (owner-directed import of r2 R1-02/R1-03/R1-04/R2-01; R1-05 documented limitation): repair cbdf3f2c, R2 ACCEPT WITH FINDINGS (1 LOW open), gate 238 passed + 5 platform-gated, 0 new failures, **VERIFIED, not integrated** (authorized=false). Bundle: milestone/dev-lifecycle-2-20261011 = cbdf3f2c. Windows gate on cbdf3f2c pending (owner PC). |
| 2026-10-11 15:10 | Owner: RaR/ARN are intent discovery and never see page text, so **D17 tightened back** (every short foreign word is a separator unless bracketed). New owner requirement **D18: all result summaries brief and in simple words** (recorded; goes into the lifecycle skill in DEV-LIFECYCLE-3; applied to replies now). Meanwhile the driver had run R14 (REJECT, R14-01 stroke-list gaps; R1-01 confirmed fixed) and its own repair fe77015a; stopped during R15 (driver + reviewer, no orphans). Coordinator commit `9b6b4f27` (tightening removes the stroke list; R13/R14 tests aligned to the owner's rule; web 1737 pass; gate = baseline set). Relaunched. |
| 2026-10-11 13:50 | **Correction (bundle overwrite).** Checkpoint 3803775 (W1/A0 thread) rebuilt milestones.bundle/REFS.txt from a stale ref set and wrote milestone/dev-lifecycle-2-20261011 back to f3706e03 (reported by the owner-PC coordinator). Re-written to cbdf3f2c (the DEV-LIFECYCLE-2-r3 VERIFIED tip, as in 92929da), keeping a0 = 9b6b4f27; every other ref was checked and is unchanged. Restore from canonical alone was re-tested. **Rule for every thread:** before rebuilding the bundle, start from the refs in the CURRENT pushed bundle (`git fetch <bundle> refs/heads/*:refs/heads/*`) and move only your own milestone ref. |
| 2026-10-11 15:35 | W1/A0 R16 on 9b6b4f27: REJECT, OWNER_DECISION. R16-01 (3+ stroke letters as separator) → **owner decision D19 "stroke list"**. R16-02 (local-use NAT64) fixed. Coordinator commit `101bf972` (web 2309 pass; gate = baseline set + a ws flake seen 1/8 on 6b07b467 too). R16-03..06 LOW non-blocking open. Unblocked; relaunched (PID 10278). Known risk: ws_hardening tests flake ~1 in 6-8 on both commits; could fail the driver's post-ACCEPT gate. |
| 2026-10-11 14:05 | **DEV-LIFECYCLE-2 INTEGRATED** by the owner-PC coordinator under D1: canonical integration/git-sync-20261008 ce1a90c → cbdf3f2c (ls-remote checked from the cloud). Windows gate on cbdf3f2c: 238 passed, 0 failed, 5 linux-only platform-gated (receipt branch receipts/dev-lifecycle-2-20261011 @ 9f0f6059, evidence SHA-256 checked). See lifecycle-runs/DEV-LIFECYCLE-2-INTEGRATED.md. **W1/A0 must now be rebased onto cbdf3f2c and re-reviewed with expected_target_tip = cbdf3f2c**; its current config expects ce1a90c, so its integration would stop. **The canonical driver for new runs is now cbdf3f2c** (RESTORE.md still names ce1a90c for existing runs). |
| 2026-10-11 14:10 | **Second bundle overwrite.** Checkpoint f222876 (W1/A0 thread) again wrote milestone/dev-lifecycle-2-20261011 = f3706e03 from that container's stale local branch. Restored to cbdf3f2c, keeping a0 = 101bf972. **Fix for the W1/A0 thread:** in its container, run `git branch -f milestone/dev-lifecycle-2-20261011 cbdf3f2ceb5eea4e8b634f92c8e3dee4571a3b35` (cbdf3f2c is now canonical; fetch origin integration/git-sync-20261008 first), or rebuild the bundle only from the current pushed bundle refs. |
| 2026-10-11 16:15 | DEV-LIFECYCLE-2 **integrated** by the owner-PC coordinator (canonical = cbdf3f2c, verified with ls-remote); the other thread reported that my checkpoints had rolled its bundle ref back to f3706e03 (it restored it twice). **Correction:** my local ref was stale; fixed to cbdf3f2c, bundle rebuilt, only my a0 ref moves. W1/A0 R17 on 101bf972: RETRY_LIMIT, R17-01 (stroke list gaps: ㅡ ㅣ ノ 丷 三). Repair `0136d915` within D19 (list built from whole Unicode groups; 455/503 new tests fail on 101bf972). Merged canonical cbdf3f2c into W1/A0 (`b7b93e7c`, no overlapping files). Gate: baseline set + known ws flake; tests/dev_workflow 238 pass. Config expected_target_tip → cbdf3f2c, acknowledged with a note (CONFIG block). Relaunched (PID 12353). |
| 2026-10-11 16:45 | W1/A0 R18 on b7b93e7c: RETRY_LIMIT, R18-01 (stroke-shaped kana). **Owner decision D20 "add kana, then close"**: all kana join the stroke list; the list is final, other look-alikes are accepted risk (non-blocking). Repair `0577aeb6` (75/78 new tests fail on b7b93e7c; web 2890 pass; gate = baseline + known ws flake). Unblocked; relaunched (PID 19447). |
| 2026-10-11 17:10 | W1/A0 R19 on 0577aeb6: RETRY_LIMIT. R18-01 and R17-01 confirmed fixed. Blocking R19-01 (mark-only word as separator) and R19-02 (Cyrillic look-alike ending 'сом'). Coordinator repair `eb4d676d` within D16 (11/12 new link tests fail on 0577aeb6; web 2890 pass; gate = baseline + known ws flake). Unblocked; relaunched. Precision cost noticed: Portuguese 'café com leite' is masked (from the R11 'core domain after a plain space' rule). |
| 2026-10-11 17:35 | W1/A0 R20 on eb4d676d: RETRY_LIMIT. Blocking R20-01 (separator word + combining mark) and R20-02 (spelt Cyrillic look-alike 'с о м'). Coordinator repair `68feb3e7` (21/22 new link tests fail on eb4d676d; web 2905 pass; gate identical to baseline). Unblocked; relaunched for R21. Owner asked whether an AI search tool could help; answered (it would not close this class; see reply). |
| 2026-10-11 18:05 | W1/A0: R21 REJECT → driver repair 57ccdd22 (P9); R22 REJECT, RETRY_LIMIT. **R1-01 confirmed fixed by the reviewer.** Only blocking: R22-01 (marks on fillers / marks of another script). Coordinator repair `0e9a51ea` (structural: a mark is kept only on a letter of its own script; 15/27 new tests fail on 57ccdd22; web 2946 pass; gate identical to baseline). Unblocked; relaunched for R23. |
| 2026-10-11 18:35 | W1/A0 R23 on 0e9a51ea: RETRY_LIMIT, R23-01 (one letter + own-script marks). Coordinator repair `d51207ea` (letters only; same-script bracketed phrases; 14/19 new tests fail on 0e9a51ea; web 2992 pass; gate identical to baseline). Relaunched for R24. Owner shared phishing-defence ideas: hidden-text stripping already done; threat feeds + urgency/mismatch flags proposed as LINK-REP-1 after W1/A0 (needs owner yes for sending URLs to an outside service); sandboxed link checkers rejected (would open scam sites). |
| 2026-10-11 19:00 | W1/A0 R24 on d51207ea: RETRY_LIMIT, R24-01 (Arabic/Hebrew TLD with optional vowel marks). R23-01 confirmed fixed. Coordinator repair `0adc9541` (18/18 new link tests fail on d51207ea; web 3014 pass; gate = baseline + known ws flake). Relaunched for R25. Noted, unchanged: D15 masks pointed Hebrew (shin dot). Owner asked about blocking sites without English letters: proposed blocking non-English site ADDRESSES (IDN hosts) as a small change after W1/A0; awaiting owner yes. |
| 2026-10-11 19:25 | W1/A0 R25 on 0adc9541: RETRY_LIMIT, R25-01 (hand-picked Arabic mark ranges incomplete). Coordinator repair `74909458` (all Mn/Me marks removed for ending match; 14/14 new link tests fail on 0adc9541; web 3032 pass; gate identical to baseline). Relaunched for R26. |
| 2026-10-11 19:35 | **Owner decision D21**: block site addresses with non-English letters (option 1), and when a genuine site is blocked URI must say why. Queued as IDN-1 after SSRF-1 (plan draft written). Not applied to the W1/A0 candidate (would restart its review). The D21 row goes into OWNER_DECISIONS in the IDN-1 branch. |
| 2026-10-11 19:45 | **Owner decision D22**: "Yes" to LINK-REP-1 (read as approval of the pending proposal; owner told to correct if meant otherwise). Queued after IDN-1, plan draft written. Needs provider + API key from the owner before it runs. |
| 2026-10-11 19:50 | LINK-REP-1 settings from the owner: provider URLhaus; when the lookup is unavailable, skip the site. Still needed before the run: the owner's URLhaus key in `.env` (URLHAUS_AUTH_KEY). |
| 2026-10-11 20:00 | **Owner requirement D23**: every item waiting on the owner lives in one file, `lifecycle-checkpoint/OWNER_ACTIONS.md`, added the same day and removed only when done. File created (4 to-dos, 4 PC items, 5 decisions, 5 optional readability items). |
| 2026-10-11 20:15 | **Owner decision D24** (W2): proposed site list; refresh only when the user asks for the same data again; personal data searchable only; no PDF copies. Readability: O1 'com' after a space stays caught (owner confirmed after a clearer re-ask; first wording was muddled), O2 Hebrew points allowed (added to IDN-1), O3-O5 unchanged. PC items A2/W1-W4 delegated to a PC thread. W1/A0: R26 REJECT, driver repairing itself. |
| 2026-10-11 20:25 | D24 Q2 corrected by the owner: "refresh when visit again" (any revisit: asking for the data or opening it). W2 plan updated. |
| 2026-10-11 20:35 | **Owner decision D25**: relying on an outside API must not restrict URI. LINK-REP-1: without a key or when URLhaus is down/slow, URI works as today with a 'Not scam-checked' note; only a positive listing blocks. Replaces the earlier 'skip when unavailable' default. A1 now optional. |
| 2026-10-11 20:50 | W1/A0: R26 REJECT → driver repair be7cdecf (P10); R27 REJECT, RETRY_LIMIT, R27-01 (Latin look-alike endings 'ɡov', 'ᴄᴏᴍ', 'sħop'). Coordinator repair `0fcc39d4` (Latin letters folded by Unicode name, whole range by rule; 14/14 new link tests fail on be7cdecf; web 3064 pass; gate identical to baseline). Relaunched for R28. |
| 2026-10-11 21:00 | **Owner decision D26**: Settings > Security tab to add the URLhaus key (part of LINK-REP-1). Frozen exception approved for `uri_ui/lib/screens/settings/settings_shell.dart`, tab entry only; the tab is a new file. Key stored user-only, never shown in full or logged. |
| 2026-10-11 21:05 | **Owner decision D27**: add a Tavily key slot to the Security tab. Both keys show only "Key saved" (no characters, per the never-expose-the-Tavily-key rule); tab key wins, `.env` still works (D3). |
| 2026-10-11 21:15 | **Owner decision D28**: everything front-loaded in the app, no `.env` later. SETTINGS-1 queued before LINK-REP-1 (plan draft). Finding while planning: the launchers set a fixed default key-store password (`uri_local_dev_secret_key_v1`), so encrypted provider keys are decryptable by anyone with the file and the code; fix included in SETTINGS-1. |
| 2026-10-11 21:45 | W1/A0: R28 → driver repair 6c51965f (P11); R29 REJECT, RETRY_LIMIT, R29-01 (hand-made look-alike table incomplete). Coordinator repair `c5fe6351`: endings read through the full Unicode confusables data (generated `uri_web/confusables_ascii.py` from UTS #39 confusables.txt 2026-08-06, fetched from the ICU GitHub copy since unicode.org is blocked; sha256 6ed3ee96...), Latin names and the old table; unknown Latin letters are wildcards; cross-script look-alikes count after a plain space. 16/18 new link tests fail on 6c51965f; web 3109 pass; gate identical to baseline. Relaunched for R30. |
| 2026-10-11 22:15 | W1/A0 R30 on c5fe6351: RETRY_LIMIT, R30-01 (Cyrillic look-alikes of accented Latin letters). **Owner decision D29: the Unicode confusables list is final** (unlisted look-alikes such as 'ҁ' are accepted risk, not blocking). Coordinator repair `87bd6aa7` (data also keeps Latin-prototype entries; 12/14 new link tests fail on c5fe6351; web 3135 pass; gate = baseline + known ws flake). Relaunched for R31. |
| 2026-10-11 22:20 | **Correction to the 22:15 row:** the relaunch for R31 did not start; the run hit its 30-review-round budget (BUDGET blocker). Owner raised max_rounds 30 → 40; config change acknowledged (CONFIG) with a note; driver relaunched for R31. |
| 2026-10-11 22:45 | W1/A0 R31 on 87bd6aa7: RETRY_LIMIT, R31-01 (ASCII look-alikes c0m/g0v/miI listed in the Unicode data). R30-01 confirmed fixed. Coordinator repair `1525b10d` (same-length ASCII variant; 20/20 new link tests fail on 87bd6aa7; 11 controls pass; web 3153 pass; gate identical to baseline). Relaunched for R32 (round budget 40). |
| 2026-10-11 23:10 | W1/A0 R32 on 1525b10d: RETRY_LIMIT, R32-01 (two-character look-alike endings 'i0', 'c0', '1y'). Coordinator repair `fc3d6f42` (one-letter runs read only when they then spell a domain; 18/18 new link tests fail on 1525b10d; web 3184 pass; gate identical to baseline). Relaunched for R33. |
| 2026-10-11 23:35 | W1/A0 R33 on fc3d6f42: RETRY_LIMIT, R33-01 (leading 'I' as 'l' in endings). R32-01 confirmed fixed. Coordinator repair `bdc82ef1` (19/19 new link tests fail on fc3d6f42; web 3207 pass; gate = baseline + known ws flake). Relaunched for R34. |
