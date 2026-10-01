# Report E: Failures, root causes, repairs and before/after measurements

Every number here comes from the run files named in each row and the scorer outputs in `results/`. Development numbers are from one run per case. Holdout numbers are worst of 3.

## 1. Why earlier results were rejected

| Source | Finding | Class | How EPQ-1 avoids it |
|---|---|---|---|
| Codex review `docs/research/DYNAMIC_PLANNING_CANONICAL_IMPLEMENTATION_REVIEW.md` (in `_V1`, untracked; 2026-09-28; NEEDS_ARCHITECTURE_REWORK) F5 | Adversarial runner called Granite, never used the response, injected filenames, dates, identifiers and filters | runner | The scorer reads only the provider's own response; no runner code supplies arguments |
| same, F6 | Subset scoring; `false_verified_commits` never incremented | scoring | Exact oracle comparison; every counter is derived per record (`scorer.py`) |
| same, F7 | Verifier returned COMMIT for an injected `permission_denied` | verification | Execution credit only for the real `SystemPerformanceTool` result or explicitly labelled test doubles (report D) |
| same, F9 | Missing or malformed Needle output defaulted to CAN_DO | adapter | Missing, malformed, truncated and suppressed-only outputs are failures |
| same, F10–F11 | Targets overwritten with the latest file; any path accepted; fuzzy sheet and row substitution | runner/runtime | No target rewriting anywhere; containment rejects non-verbatim arguments |
| Stage-1 (`fresh_20260929`) | Synthetic 4-tool catalogue, CPU vs GPU, no containment, same-author batteries; RC-9 Needle UTF-8 transport errors | test design / runtime | Typed projection of the 17 registered actions plus the real URI schemas (R1); a CPU Granite arm; containment on every run; UTF-8 forced on both Needle pipes (0 transport errors in 2,213 Needle calls; 81 model-side `truncated` outputs) |

RC-9's cause, marked UNVERIFIED in the root-cause audit because the bridge "was not supplied", is now confirmed from source. `_V1/experimental/edge_model_tests/experimental_needle_bridge_runtime.py` writes `ensure_ascii=False` JSON to an unreconfigured `sys.stdout`.

## 2. Failures observed in EPQ-1, and their cause

| Failure | Evidence | Primary cause | Secondary |
|---|---|---|---|
| Neither model abstains | False accept on no-action cases, holdout: Needle 36–41/49, Granite 42–49/49; MULTISTEP 0/5 for both | **model** | prompt (P1 helps a little) |
| Wrong tool among offered tools | e.g. `transcript for 20BT302` → `read_attached_file("20BT302")`; holdout SELECT 13–16/17 | model | — |
| Right tool, wrong grounded argument | `Fetch the previous link` → the other URL in context; `laptop` used as a file name | model | **containment gap**: a verbatim span can be the wrong span |
| Injection followed in extraction | Granite JSON dev: `sender` → `admin@college.example`, `ifsc` → `HDFC0000001`, `quantity` → `1200` | model | containment cannot detect it (the decoy is a verbatim span) |
| Absent field filled | Granite returns "not provided" or "UNTRUSTED DOCUMENT (data only)" | model + prompt | N5 rejects non-spans; "UNTRUSTED DOCUMENT…" leaked from the fence header |
| Needle `truncated` outputs | 35 of 1,036 development Needle calls, all on cases with a document | adapter/prompt interaction | — |
| Needle multiple calls on labels | after options were listed (v2), Needle emitted one call per option | model behaviour triggered by prompt | — |
| Enum labels wrong | Granite: SEMANTIC 6/10 holdout, with heavy bias to one value (e.g. "urgent", "receipt", "it_support" in development) | model | — |
| Deterministic baseline wrong file names | 13 incorrect executions in holdout C0 | **test infrastructure** (my rule pattern allowed spaces) | — |
| Lost records | Ollama desktop app shut itself down at 2026-09-30 21:52 (app log); 296 development records refused | runtime | — |

## 3. Repairs tried (development split unless stated), before and after

| Repair | Hypothesis | Before | After | Decision |
|---|---|---|---|---|
| P1: explicit control tools | Models abstain when abstention is a tool | dev false accept: Needle 82 → 71/100; Granite native 100 → 77; Granite JSON 100 → 74 | holdout: Needle 41 → 36/49; Granite JSON 49 → 42/49 | Small real gain; still nowhere near safe. Kept as an arm, not a fix |
| v2: no `<<<` fence, label options in question | Fence causes Needle truncation; options help labels | Needle document cases 11/69 (14 truncations); Granite JSON 33/69 | Needle 12/69 (0 truncations, but multiple calls on labels); Granite JSON 28/69 | Rejected |
| v3: fence removal only | Isolate the fence effect | Needle 11/69, 14 truncations | Needle 7/69, 6 truncations; Granite native 30 → 29, JSON 33 → 30 | Rejected: fewer truncations, no accuracy gain |
| v3t: one tool per label value | Labels as tool choice (Needle's strongest skill) | Needle SEMANTIC dev 3/30; Granite native 12/30 | dev 8/30 and 12/30; **holdout Needle 2/10 (v1 3/10), Granite native 6/10 (v1 3/10)** | Needle gain did not reproduce; stopped optimizing Needle labels (brief §9: fundamentally unsuitable at this size and interface) |
| R1: real URI schemas | Synthetic typed catalogue misrepresents the task | dev select: Needle 79/173, Granite JSON 79, native 82 (v1) | R1 (with v2 presentation): 70, 71, 88; holdout R1 Needle 53/102, Granite JSON 48/102 (v1: 49, 47) | No consistent change in choice; containment weaker because real tools take `request_text` |
| Placement match: Granite on CPU | Needle/Granite latency gap is placement | Granite JSON GPU holdout p50 166 ms | CPU p50 745 ms (Needle P1 734 ms); accuracy 65/138 both | Latency difference was placement; accuracy unchanged |
| Deterministic rules fix1 | Pattern bug | holdout C0 14/138, 13 incorrect | 24/138, 3 incorrect | Post-holdout correction, reported beside the original, labelled `deterministic_fix1` |

No holdout case, oracle, threshold or gate was changed. The fence and label repairs were rejected on development data before the holdout; v3t and R1 were pre-declared diagnostic arms (addendum 1).

## 4. Remaining limitations

- Sample sizes per family (holdout 5–17) are far below the qualification plan's 150 per segment. Every label carries its Clopper-Pearson bound.
- The typed catalogue is a projection; real URI actions mostly take `request_text` (R1 covers this).
- The battery and the harness have the same author. The freeze order and the Codex audit (report G) are the mitigations.
- Latency was measured with other sessions using the same Ollama server and CPU; affected windows are recorded per batch, and the R1 latencies need an idle rerun.
- Needle's process RSS in the first development run measured the venv launcher (4.7 MB). This was fixed before the holdout; Needle's own `peak_ram_mb` is in every record.
