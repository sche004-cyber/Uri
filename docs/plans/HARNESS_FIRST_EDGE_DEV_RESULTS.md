# Harness-First Edge: Development Results (H0-H5)

- **Status:** PROVISIONAL. Development evidence only. Nothing here qualifies an Edge model. Independent audit and the H6 holdout run are still required.
- **Date:** 2026-10-01. **Author:** Claude (thread "Harness-first Edge track").
- **Branch:** `claude/project-thread-sqk105` on `sche004-cyber/Uri` (private).
- Raw records: `experiments/harness_first/runs/` (`dev_r1.jsonl`, `dev_r2.jsonl`, `app_latency.jsonl`). Tables: `experiments/harness_first/results/dev_r2_tables.md` (primary) and `dev_r1_tables.md`.

## 0. Acceptance criteria for this report

| ID | Criterion |
|---|---|
| R-1 | Every number comes from a recorded run in `runs/` and is reproducible with the commands in §10. |
| R-2 | Mocks, fixtures and test doubles are named where they affect a number. |
| R-3 | The critical gates (false success, unauthorised action, invented binding, bypassed clarification) are reported for every configuration, not only the best one. |
| R-4 | Claims that came from my own earlier reading and turned out wrong are corrected in place (§9). |
| R-5 | The recommendation follows from the measured evidence only. |

## 1. Baseline and integration base

| Item | Ref | Evidence |
|---|---|---|
| Running app, complete local snapshot | `uri-agent` `869fae5` (local branch `preserve/running-app-2026-10-01-local-full`) | Tree equals the live working tree (`git write-tree` identical, re-checked before push) |
| Running app, pushed (public uri-agent) | `preserve/running-app-2026-10-01` at `a91e0e4` | Same as `869fae5` minus 3 converted drafts with personal-looking data and 3 graphify dev artifacts (kept on disk) |
| Needle pre-route default off | `71edc17` (local branch `needle-preroute-default-off-2026-10-01`), child of `869fae5` | Runs only with `URI_EDGE_NEEDLE_PREROUTE=1`; EDGE_ONLY keeps its limitation; 32 targeted tests pass, 2 pre-existing failures unchanged |
| URI v1 frozen line + EPQ-1 harness | `c17f593` | M36-M38 freeze `5bbf738`, Edge pair plan r2, EPQ-1 |
| **Track base** | merge `b9b5c37` on this branch (parents: this track's first commit on `c17f593`, and `71edc17`) | Only conflict was `docs/governance/URI_AGENT_RELAY.md`; no code conflict. `uri_core`/`uri_ui` differ from `71edc17` only by the V1 line's 13 added files (insert-only); `uri_v1/` equals `c17f593` |

Tests reproduced from the preserved snapshot (`869fae5`, scratch export): Flutter **182/182**; backend **2,273 passed, 19 failed**. 13 failures match the readiness audit exactly. 6 are additional: `step3_test.py`/`step4_test.py` (manual Drive scripts) and 4 in the untracked `test_m33_3_fix_a_telemetry_reconciliation.py` (server returns `reasoning_ms: None` where the test expects 2450). Not investigated further; not on this track's path.

## 2. What was built (H2)

`experiments/harness_first/`: `pipeline.py` (harness stages), `run.py` (records), `score.py` (completion classes and gates), `analyze.py` (tables), `corpus_author.py` (dev corpus), `holdout_author.py` (sealed holdout), `app_latency.py` (real app). Architecture: `docs/plans/HARNESS_FIRST_EDGE_ARCHITECTURE_MAP.md`.

Real components on the path: TurnFrame builder, approval resumption `classify_confirmation`, conversational classifier patterns, lifecycle grammar, M36 `negated`, RAR, S1 `build_clarification`/`render_template`/`presented_options`, S6 `evaluate_intelligence_route`, `translate_tool_calls`, `evaluate_gates`, `SystemPerformanceTool`. Edge transports: EPQ-1 `NeedleAdapter` and `OllamaAdapter` (Granite `granite4:350m-h` JSON mode, GPU). Main Brain: local `qwen3.5:9b`, `think: false`, Ollama, no metered spend.

Test doubles: execution of every action except `system_performance` (Gmail, Drive, web, file reads are doubles; writes and approval-required actions are held, never run); session context from corpus fixtures; Edge runtime inventory profile; declared wrong-binding impact per action (read-only = RECOVERABLE, others CONSEQUENTIAL); extraction/label schemas supplied by the corpus (no live producer exists, X-P1).

## 3. Corpus (H3)

322 development cases: 238 from the EPQ-1 **dev** split (route-kind dropped; the EPQ-1 holdout was never read) and 84 new end-to-end cases: 36 trivial conversational, 6 trivial-wrapped real requests, 14 pending-approval follow-ups, 3 lifecycle, 16 multi-turn session references, 8 Main-only, 4 adversarial targets. Fixture repair, documented in code: 27 EPQ-1 cases that say a file is "attached" get that file in their session.

## 4. Results, run 2 (after repair round 1)

| Config | Correct | HARNESS_COMPLETE | +EDGE | +MAIN | CLARIFY | SAFE_FAIL | False success | Bypassed S1 clarify | Wrong binding | Wrong extract/label accepted | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| main_only (no harness) | 253 (0.786) | 0 | 0 | 223 | 49 | 50 | 24 | **11** | 0 | 16 | 538 | 1,209 |
| current_proxy (approval resumption + Main) | 262 (0.814) | 9 | 0 | 222 | 48 | 43 | 23 | **11** | 0 | 16 | 534 | 1,200 |
| harness_only | 61 (0.189) | 38 | 0 | 0 | 25 | 259 | **0** | **0** | **0** | 0 | 0.9 | 1.2 |
| **harness_main** | **287 (0.891)** | 38 | 0 | 191 | 55 | 38 | 11 | **0** | 0 | 16 | 738 | 1,397 |
| harness_granite_json | 229 (0.711) | 38 | 159 | 55 | 45 | 25 | 53 | 0 | 0 | 32 | 185 | 1,214 |
| harness_needle | 249 (0.773) | 38 | 94 | 114 | 48 | 28 | 38 | 0 | 0 | 28 | 840 | 2,021 |

`current_proxy` and `main_only` use this experiment's compact prompt (median 844 prompt tokens), so their latency is far below the real app; the real app is measured in §5. "Correct escalation" is 1.0 for every config that ends in Main; Granite 0.75 and Needle 0.91 (they executed some work that needed the Main Brain). Unauthorised actions: 0 in every config (writes and approval actions are held by construction). Invented candidate IDs: 0 (every executed identifier came from a RAR/S1 binding, a session candidate or a verbatim span; model-supplied values were discarded, e.g. a model proposing `evil.pdf` was replaced by the bound file).

## 5. Latency: trivial and bounded turns

**Real app** (`869fae5`+Needle off, scratch backend on 127.0.0.1:8765, fresh test user, local qwen3.5:9b, machine otherwise idle, 3 runs per turn):

| Turn | Median ms | Main reasoning s | Main drafting s | Prompt tokens |
|---|---|---|---|---|
| hello | 19,279 (first run 50,011, cold) | 16.6-31.0 | 2.3-18.8 | 9,345 |
| thanks / ok / hey there / good night | 18,456-19,067 | ~16.7 | ~2.3 | ~9,350 |
| What can you do? | 22,954 | 16.2 | 6.6 | 14,383 |
| How much memory is this computer using right now? | 19,455 | 17.4 | 2.6 | 9,385, status **unavailable** |
| Search the web for NAAC criterion 3 guidelines. | 19,830 | 17.2 | 2.7 | 9,361, status **unavailable** |

The repository already recorded the same pattern ("Trace C": reasoning 8.9 s + drafting 4.7 s = 14.2 s, `test_m33_3_fix_a_telemetry_reconciliation.py`). Every trivial turn makes two Main Brain calls over a ~9,350-token prompt.

**Harness-first** (run 2): 26 of 36 trivial turns finish in the harness, p50 **0.2 ms**, max 1.1 ms, no model call. The other 10 natural variants ("hey there", "Thank you so much!", "namaste") go to the Main Brain on a prepared prompt: trivial p95 0.58 s, max 2.2 s. Deterministic turns (approvals, lifecycle) 0.2 ms. Main Brain on the prepared residue: median 834 ms, p95 1,459 ms, median 839 prompt tokens (about 11x smaller than the real app's prompt, one call instead of two). Harness stages themselves: median 1 ms, max 3.3 ms.

## 6. Edge evidence per job (only residues the harness admitted)

| Model | Job | Invoked | Accepted by URI | Correct when accepted | Abstained | False success | p50 ms |
|---|---|---|---|---|---|---|---|
| Granite (JSON, GPU) | SELECT_ACTION | 134 | 103 | 0.48 | 15 | 51 | 180 |
| Granite | EXTRACT | 32 | 27 | 0.44 | 0 | 0 | 192 |
| Granite | LABEL | 30 | 30 | 0.50 | 0 | 0 | 64 |
| Needle (CPU) | SELECT_ACTION | 134 | 69 | 0.46 | 35 | 35 | 858 |
| Needle | EXTRACT | 32 | 15 | 0.33 | 0 | 0 | 493 |
| Needle | LABEL | 30 | 10 | 0.30 | 0 | 0 | 157 |
| Main (qwen3.5:9b), harness_main, for comparison | label group / extract group | 30 / 22 | | 28/30 and 13/22 correct | | | ~560 / ~1,400 |

- **No Edge job is qualifiable on this evidence.** Precision when URI accepts the Edge output is 0.30-0.50 for every model and job. The harness+Edge configurations are less correct and less safe than harness+Main (false success 38-53 vs 11).
- **Combining specialists:** accepting a selection only when Needle and Granite agree gives 26 right and 13 wrong (precision 0.67, run 1). Still far below a gate.
- **Small-talk residue:** given a `reply_small_talk` option, Needle never used it (it chose ask-clarification or decline on all 10), and Granite ran `system_performance` on all 10. Neither handled conversational residue; the Main Brain answered them.
- What the harness removed from the models worked: across all configurations S1-required clarifications were never bypassed and no wrong binding executed, while the Main Brain without the harness bypassed 11 required clarifications.

## 7. Failure analysis (H4) and repairs

| Failure class | Seen in | Cause | Repair |
|---|---|---|---|
| Negated turn skipped a required S1 clarification; Main then executed against an unresolved reference (1 case, run 1) | harness configs | my pipeline let negation skip the S1 stop | **R1 repaired**: S1 CLARIFY stops the turn regardless of negation. Run 2: 0 |
| Fixture invented file names from phrases such as "attached file to some other format" (2 cases) | corpus | my fixture-repair regex | **R2 repaired** |
| Unsupported request runs the nearest read-only tool (e.g. "Wipe my Gmail trash permanently" -> `web_search`) | Main 5, Edge 10-12 | real URI tools take the raw `request_text`, so argument checks cannot reject them; nothing declares which operation a tool performs | **Not repaired.** Needs declared operation metadata per capability (live-registry change, Edge pair r2 P-1) |
| Underspecified request runs (e.g. "Search my mail.") | Main 5, Edge 11 | tools have no required slots beyond `request_text` | **Not repaired.** Needs required-slot declarations per capability |
| Wrong extraction or label passes validation | Main 16, Edge 28-32 | verbatim-span and enum checks prove form, not correctness; injected decoys are verbatim spans | **Not repaired.** No deterministic oracle; values stay candidates needing confirmation for consequential use |
| Edge selection errors (wrong tool, tool for chit-chat) | Edge | model capability | Not a harness defect; Edge not assigned |

Reproducibility (run 1 vs run 2, same corpus apart from the two repairs): harness_only 2 flips (both the repaired cases), harness_main 2, Main-only 1, Granite 10, Needle 9 outcome changes out of 322. Granite's SELECT latency fell from p50 803 ms (run 1) to 180 ms (run 2) with no code change to that path; cause not established, so run-1 Edge latency is treated as unreliable.

## 8. Holdout (H5)

`corpus/hf_holdout_sealed.json`, 68 new cases, sha256 `a5219249d967649cc243fca16033e5cbd291d51b8d6a22081ef592c2a3f63e36` (`corpus/MANIFEST_holdout.json`). Frozen before any run of it. Not run. Intended for an independent H6 thread against a frozen pipeline commit.

## 9. Corrections to my own earlier statements

- In this thread's working notes I first read the run-1 trivial-group result (harness_needle 36/36) as Needle handling conversational residue. The per-case records show Needle abstained on every one and the Main Brain answered. Corrected in §6.
- The architecture map (§4.1) predicted no deterministic text-to-capability mapping; confirmed: the harness alone completes 0 of 45 tool-action cases.

## 10. Reproduce

```
cd experiments/harness_first
python corpus_author.py                       # corpus/hf_dev.json
python run.py --out runs/dev_rN.jsonl --edge granite_json,needle
python analyze.py runs/dev_r2.jsonl --rerun runs/dev_r1.jsonl --app runs/app_latency.jsonl
python app_latency.py --base http://127.0.0.1:8765 --out runs/app_latency.jsonl --repeats 3   # needs a scratch backend
```

## 11. Recommendation for the next stage (evidence only)

1. **Next integration candidate is harness + prepared Main Brain, not harness + Edge.** On this corpus it is the most correct configuration (0.891 vs 0.786 for Main alone), removes all S1 clarification bypasses (0 vs 11), completes most trivial and all deterministic turns in under 2 ms, and its Main calls use about one-eleventh of the real app's prompt in one call instead of two. The latency problem is mostly the app's two ~9,350-token Main calls per turn, not the absence of an Edge model.
2. **Do not assign any job to Needle or Granite.** Both measured 0.30-0.50 precision on every bounded job, consistent with the isolated EPQ-1 holdout. Keep the Edge research open on jobs not yet tested here: conversational wording of an already-decided reply, and another ≤1B candidate.
3. **The remaining false successes are Main Brain errors the harness cannot see**, because live tools take raw request text and declare no operation or required slots. Closing them needs capability metadata in the live registry (operation identity, required slots, impact). That is a live-app change and a decision for Chetan.
4. Before any of this reaches `/ask`: independent audit of this branch, then the H6 holdout run.

## 12. Self-review against §0

R-1: every table comes from `analyze.py` over committed runs. R-2: §2 lists the doubles; `current_proxy` latency is explicitly not the real app. R-3: §4 reports every gate for every configuration. R-4: §9. R-5: §11 cites §4-§7 only. Not verified: live Gmail/Drive behaviour (doubles), Windows UI behaviour of any new path (none wired), and whether results hold for corpus authors other than me.
