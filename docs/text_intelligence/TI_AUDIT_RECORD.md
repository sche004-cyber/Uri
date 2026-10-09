# Text Intelligence — Independent Audit Record

Auditor: Codex CLI (`codex exec`, model `gpt-6-sol`, reasoning effort medium) through the local `codex-exec` bridge,
read-only sandbox, on a disposable `core.autocrlf=false` clone `C:\Users\cheta\Development\tia` pulled to each
reviewed commit. Codex did not write this code (Claude did). Codex output is treated as a claim: every finding below
was reproduced or confirmed by reading the code before repair, and each repair carries regression tests.

## Final verdict

**Round 16 on `18f79ba`: ACCEPT WITH FINDINGS** — "no whole-branch finding met blocking rule (a), (b), (c), or (d)".
Recorded limitations: the abbreviation list in the replacement matcher (e.g. "Capt." can still cut a replacement at
its period), and routing/factual checks remain heuristics outside their recognised phrasings.

Blocking rule used from round 3 onwards (stated to the auditor; round 16 states it against the owner's
limitation-vs-repair rule): (a) URI can act without Core; (b) an action request lost when both the classifier and the
model-side guard miss it; (c) a violation of an acceptance criterion as written in `TI_BLUEPRINT.md` §0;
(d) a regression — a factual change an earlier commit's check flagged that now gets no flag.

## Rounds

| Round | Reviewed | Verdict | Findings (summary) | Repair |
|---|---|---|---|---|
| 1 | c7ed4e3 | REJECT | F1 chained actions captured by the desk (blocking); F2 named-part edits widened; F3 pending question lost on failure; F4 yes/no answers missed; F5 two `turn.started` on fallback; F6 checks trusted the model's fact list; F7 number phrases; F8 `uncertain` coerced | 2147a2c, 92e01d1 |
| 2 | 92e01d1 | REJECT | sentence-level actions; "it" after a named part; user exclusions; content actions sent to Core; abandoned questions; correction noise; Dart trimmed the raw transcript | 9026afb |
| 3 | 9026afb | REJECT | action after a colon payload; broad reported-request exemption; exclusions not persisted; open question kept for REVISE; correction stripping removed unrelated details | 4078ae0 (adds model-side `actions_requested` guard) |
| 4 | 4078ae0 | REJECT | guard suppressed while a question was pending; nearest-detail stripping; content sequences; pending create kept; exclusion parsing; "please" instructions | ac154a6 |
| 5 | ac154a6 | REJECT | "There" paired as a name | bebb11f |
| 6 | bebb11f | REJECT | "Everybody" paired as a name | 170b180, 6a141ad (170b180 was committed with two failing regressions; 6a141ad fixed them — recorded, not rewritten) |
| 7 | 6a141ad | REJECT | date pairing could excuse an unrelated date | 5493c46: heuristic stripping removed; supersession must be verified in the user's words |
| 8 | 5493c46 | REJECT | an apology ("sorry for …") verified a false supersession | cc42a1c |
| 9 | cc42a1c | REJECT | modal "may" as a month; "Keep Monday" excused a removal | 1721fbb: nothing is ever excused silently (DETAIL_DROPPED info lines) |
| 10 | 1721fbb | REJECT | sentence-initial names not extracted; value reassignment undetected | 6835215; reassignment accepted as limitation in round 11 |
| 11 | 6835215 | REJECT | grammar-only path ignored sentence-initial names | 625938f |
| — | live runs | — | first live Runtime v1 runs: LQ-1..LQ-26 and UI findings (flag precision, paragraph splitting, possessives, escalation, ambiguous dates, panel overflow, diff rendering) | e568beb … dd1e49a |
| 12 | dd1e49a | REJECT | six recall regressions introduced by the live precision fixes (partial matches, clock minutes, title-case surnames, Hindi "kal", swap replacement not required, inserted paragraphs) | f942dc2 |
| 13 | f942dc2 | REJECT | digit boundary broke "Rs5400"; clock tokens hidden from numeric check | 9402c94 |
| 14 | 9402c94 | REJECT | comma cut a replacement ("east wing, sector C") | b6e2130 |
| 15 | b6e2130 | REJECT | "Dr." cut a replacement; "18:00" → "00:18" unflagged (TI-AC4) | 18f79ba |
| 16 | 18f79ba | **ACCEPT WITH FINDINGS** | no blocker; two limitations | — |

Observation recorded for the owner: rounds 3–15 were dominated by one design area — the deterministic fact
verifier. Each tightening for recall produced noise and each precision fix risked a silent miss. The design change
that ended the loop was round 9's principle (*nothing is excused silently; the verifier only chooses severity*),
plus visible review lines for partial matches. The remaining residual misses are documented as limitations.

## Not reviewed by the auditor

- Live behaviour of Runtime v1 (out of scope for static review; measured separately in `TI_TEST_MATRIX.md`).
- Evidence JSON and screenshots (data, skimmed only).
- The regression chain outcome (run separately; see the report).
