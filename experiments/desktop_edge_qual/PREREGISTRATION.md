# Desktop Edge qualification: social-turn route (pre-registration)

- Date: 2026-10-01. Author: Claude (desktop recovery thread). Written and committed
  before any run of `corpus.json`.
- Candidate: route `HARNESS_EDGE_CHAT` = deterministic admission
  (`social.social_intent`) + `qwen3:0.6b` reply (`edge_chat.generate`) + URI
  validator (`edge_chat.validate`), code copied verbatim from
  `claude/harness-first-edge@86de4c0` into `uri_desktop_seams/harness_first/`.
- Bounded task envelope: a purely social turn (greeting, thanks, farewell,
  acknowledgement, "who/what are you") with no attachment, no pending approval,
  no waiting workflow, no explicit model choice. Anything else must escalate
  (stay on the existing canonical chain).
- Independence limit (disclosed): the corpus is authored by the same session
  that integrates the route. It is new text (not copied from the harness track's
  dev corpus or chat trials), but it is not an independent holdout. Codex
  reviews the corpus and results.

## Metrics and gates (all must pass)

| ID | Metric | Gate |
|---|---|---|
| Q1 | False admission: non-social turns (`expect=escalate`) admitted to the Edge route | 0 |
| Q2 | Social recall: `expect=edge` turns admitted | >= 0.80 (misses cost latency only) |
| Q3 | Intent agreement on admitted social turns (deterministic intent vs label) | >= 0.95 |
| Q4 | Model reply accepted by the URI validator (no fallback) on admitted turns, warm | >= 0.95 |
| Q5 | Deterministic reply check on accepted replies: no action claim, no link/code/brace, <= 240 chars, <= 1 question, and an intent marker (thanks -> welcome/pleasure/glad/anytime/no problem; farewell -> bye/goodbye/see you/take care/night/later; greeting/acknowledgement -> no further requirement; about_uri -> mentions URI or assistant/help) | >= 0.95 |
| Q6 | Warm latency of the model call, p95 | <= 1,000 ms |
| Q7 | Main Brain / Claude / Codex calls on the Edge route | 0 (by construction: the route calls only loopback Ollama with the candidate model; verified from Ollama /api/ps and code) |

Each social turn is run 3 times (temperature 0.7 as configured); Q4/Q5 count
every run. Cold load latency is reported, not gated.

A pass qualifies only this route for this envelope on this PC, as EXPERIMENTAL
pending Codex audit. It does not qualify qwen3:0.6b for any other task
(selection, extraction, labelling, drafting), which the harness-first track
found unqualifiable at 0.30-0.50 precision.

## Round 2 (added after r1 FAIL, before any r2 run)

r1 failed Q5 (0.929): farewells answered "You're welcome!". Repair (commit
after r1): directive intent hints for thanks/farewell and a URI-side
intent-fit check in `edge_chat.validate` (thanks needs a welcome marker;
farewell needs a goodbye marker and must not say "you're welcome"); a
mismatch falls back to the fixed line. Gates Q1-Q7 unchanged. r2 runs on a
fresh corpus, `corpus_r2.json` (no text shared with `corpus.json`), same
author (same independence limit).

## Post-r2 change (narrowing only)

After the live battery showed the Edge model answering "what can you do?" with
a generic list not taken from URI's capability catalogue, capability questions
("can/do/help/able/capability") are no longer admitted to the Edge route; they
escalate to the canonical chain. Identity questions stay. This only shrinks
the envelope. Re-check on corpus_r2 (not a new qualification):
`results_r2_recheck_after_narrowing.json` - Q1 0 false admissions, Q2 0.90,
Q4/Q5 0.963, warm p95 102 ms; all gates still met.
