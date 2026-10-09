# Text Intelligence — Test Matrix, Runtime v1 Quality and Latency

Branch `phase/text-intelligence`. Live runs 2026-10-09 07:10–07:56 IST on Runtime v1 (`qwen3.6-35b-a3b-ud-iq3_s`,
frozen argv, llama-server b11425 Vulkan, RX 7900 GRE), started from the accepted materialized runtime
`uri-ws-final` under the machine-wide GPU lease (`%LOCALAPPDATA%\URI\gpu`, label "TI live qualification").
FAST tier only (thinking off, temperature 0, JSON schema). No stronger model or harness was used.

**Input labelling.** Every "transcript" input below is a SIMULATED transcript: typed text sent in the
`uri.text_input.v1` envelope with `engine: "simulated"`. No microphone and no recogniser were used.

## 1. Levels (never merged in reporting)

| Level | What | Result | Evidence |
|---|---|---|---|
| Unit (fake Brain) | classifier, store, verifier, input contract, desk through the real bridge, audit-round regressions | 207 passed, 10 skipped (whole `tests/ws`, accepted WS tests included) | `pytest tests/ws` at 18f79ba |
| Dart unit/widget | draft model, word diff, panel (views, labels, flags, scroll), transcript envelope | 24 passed (`test/ws`); full suite 301 passed / 4 skipped | `flutter test` at dd1e49a |
| Live, in-process bridge | `scripts/ti_live_matrix.py`: IntegratedTurns + DraftDesk + Runtime v1 (Core not attached; drafting never uses it) | final run 160/161 checks, two repetitions | `evidence/ti_live_matrix_fast_20261009T073332.json` |
| Live, real worker | `tests/ws/test_ti_worker_live.py`: integrated worker (C1 gates, paired Core, integrated server) + Runtime v1; owner demo typed and as simulated transcript | 2 passed | `evidence/ti_worker_live_20261009-073802.json` |
| Live, real widgets | `uri_ui/test/ws_live/ti_ui_live_test.dart`: real Living composer, Draft panel and buttons against the real worker | 1 passed (7 steps) | `evidence/ti_ui_live.json` |
| Physical app | built `uri_ui.exe` (Release) driven by `capture_ws.ps1` | owner demo + Changes/Original views + simulated transcript captured | `screenshots/ti_0*.png`, `ti_1*.png` |

The live matrix was run five times while live findings were repaired (07:13 77/83, 07:17 159/161, 07:21 157/161,
07:26 160/161, 07:33 160/161). All runs are kept in `evidence/`. Verifier changes made after 07:33 (Codex rounds
12–15) were verified by unit tests, not by a further live run (GPU then held by the WS hardening session; §6).

## 2. Matrix (final live run, 07:33, two repetitions; check counts are summed)

| Case | Scenario (brief §6) | Checks | Failed check | Wall time per step (s) |
|---|---|---|---|---|
| M1 owner demo | self-correction, allegation rewrite, tone + shorten, undo | 33/34 | `second_para_shorter` in one repetition (model shortened paragraph 1 instead) | 4.8 / 1.8 / 2.3 / 0.0 |
| M2 | spoken date correction ("yesterday, no wait, the 6th"), transcript | 6/6 | – | 4.8 |
| M3 | three corrections in one statement (amount, day, name) | 12/12 | – | 3.6 |
| M4 | number correction in a later turn ("not two days, three") | 8/8 | – | 3.2 / 1.9 |
| M5 | "No, I meant Tuesday." | 8/8 | – | 3.3 / 1.9 |
| M6 | misheard name (recogniser marked "Priya near" uncertain) | 6/6 | – (name kept, POSSIBLE_MISHEARING shown) | 2.9 |
| M7 | Hinglish leave application + "isko thoda chhota karo" | 10/10 | – | 3.3 / 1.5 |
| M8 | informal Indian English, two phone numbers | 6/6 | – | 4.2 |
| M9 | long dictated report with fillers and a correction | 16/16 | – | 4.7 |
| M10 | contradictory instruction | 2/2 | – (Brain asked) | 1.7 |
| M11 | revise first paragraph only, keep the rest | 8/8 | – (only that block changed) | 5.3 / 1.9 |
| M12 | grammar-only correction | 10/10 | – (original kept as version 1) | 1.8 |
| M13 | "Don't mention the student's name" | 8/8 | – | 3.6 / 1.9 |
| M14 | ambiguous "change the date" (two dates) | 4/4 | – (deterministic question, no model call) | 2.7 / 0.0 |
| M15 | add a sentence, "remove the previous sentence" | 6/6 | – | 2.8 / 1.6 / 1.5 |
| M16 | rewrite politely | 4/4 | – | 1.8 |
| M17 | expand notes into a circular | 6/6 | – | 4.7 |
| M18 | greeting keeps the fast path | 2/2 | – (route `answer`) | 0.4 |
| M19 | cancel during generation | 2/2 | – (CANCELLED, no draft) | – |
| M20 | Brain unavailable (readiness forced STOPPED; runtime untouched) | 3/3 | – (BRAIN_UNAVAILABLE, draft unchanged, original still served) | 0.0 |

Real worker (07:38): owner demo passed typed and as simulated transcript: create 5.0–5.2 s, revise 1.95–2.0 s,
tone 2.5–2.6 s, undo 1 ms with no model call; route `draft` throughout; no `core.result` or `approval.required`.

## 3. Latency (final run)

| Step kind | n | median | p90 | max |
|---|---|---|---|---|
| Create (letter, email, notice, report) | 28 | 3.59 s | 4.78 s | 5.37 s |
| Revise / correct / rewrite | 22 | 1.82 s | 2.00 s | 2.43 s |
| Brain clarification | 2 | 1.74 s | – | 1.76 s |
| Deterministic (undo, redo, original, date question) | 6 | <0.01 s | – | <0.01 s |
| Greeting (ordinary fast path, unchanged) | 2 | 0.38 s | – | 0.39 s |

Decode: median 119.5 tok/s, minimum 93.9 tok/s (headless). Text-intent classification: <2 ms per turn (unit test
bound). In the physical app run decode fell to 33–40 tok/s: the GPU census showed `uri_ui.exe` holding 447 MiB and
llama-server demoted to 14.8 GiB dedicated / 1.9 GiB non-local. This is the accepted Working System finding
PERF-W1/OI-PERF-1 (VRAM oversubscription), not caused by this feature; draft steps then took 5–12 s.

## 4. Comparison with the accepted baseline (68cac3d)

Same prompts through the accepted answer channel with history (`--baseline`, run 07:13):

| Aspect | Baseline (68cac3d) | This candidate |
|---|---|---|
| Routing of "URI draft a letter …, sorry seven …, Make it formal." | triage ACTION → Core first (no drafting capability in the WS composition) | draft desk; Core untouched |
| Self-corrections in plain chat | resolved by Runtime v1 (seven, 5400, Wednesday, Sunil) | resolved, and the replaced value is checked and shown |
| M3 multiple corrections | wrote a "Correction:" e-mail (misread the spoken correction as the topic) | correct e-mail, no "correction" framing |
| M2 transcript with "make it formal" | answer channel returned `<<ACTION>>` (handed to Core) | drafted |
| Revisions | whole letter regenerated every turn (1.5 k chars), no locality guarantee | edit operations on blocks; untouched blocks byte-identical |
| Undo | not supported (model regenerated text) | deterministic, 1 ms, versions kept |
| Grammar-only | offered "Option 1 / Option 2" with restyling | one corrected text, meaning checks, original as version 1 |
| Facts/flags | none | deterministic checks with visible flags |
| Latency | create 2.2–3.4 s (prose), revise 0.8–2.6 s | create 3.6 s median (JSON + checks), revise 1.8 s |

Runtime v1 is adequate for these tasks; no stronger model was needed (TI-D9). Residual model-quality issues seen
live: occasional escalation wording ("disciplinary action") in letters (caught by ESCALATION_ADDED; reduced by the
final-check prompt), occasional placeholder lists of student names, one paragraph mis-count (M1 run 2).

## 5. Flag precision (final live run, before Codex rounds 12–15)

60 Brain steps: 0 steps with an error flag, 11 with a review line (6 × CORRECTION_UNCONFIRMED, 2 × POSSIBLE_MISHEARING
(intended), 1 × ESCALATION_ADDED (true positive), 2 × USER_DETAIL_MISSING for "two line note"). The first live run had
error flags on most cases (false positives) — see the report's correction history. Rounds 12–15 deliberately made
some matches stricter (partial matches become FACT_REWORDED review lines), so review lines will be somewhat more
frequent than in this run.

## 6. Not run / not verified

- No live run after commit 18f79ba (verifier-only changes after the last live run); GPU was then held by the WS
  hardening session's Brain host and this phase did not attach to or contend with it.
- No real speech: no microphone capture, no recogniser, no audio.
- NORMAL tier (thinking) was not measured for drafting; FAST passed the matrix.
