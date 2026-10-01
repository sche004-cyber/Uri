# Report G: Independent audit handoff (for Codex)

Codex is paused, so it has not been called. This package lets an independent auditor reproduce, re-score and challenge every EPQ-1 claim without relying on Claude's summaries.

## 1. What to verify first (ordered by how much the conclusions depend on it)

1. **Freeze order.** `git log --follow experiments/edge_pair_qual/battery/cases.json` shows the battery committed at `a616680`, before `harness.py` existed. `battery/MANIFEST_battery.json` hashes match the files. The frozen part of `PREREGISTRATION.md` is everything up to the line "Addenda (append only)" (see `harness.verify_manifest`). The harness was frozen at `c17f593` (`battery/MANIFEST_harness.json`) before any holdout record exists. Check the timestamps in `runs/holdout_*.jsonl`: every `batch_start` is after that commit.
2. **Re-score from raw records.** `python scorer.py runs/holdout_main.jsonl runs/holdout_det.jsonl runs/holdout_granitecpu.jsonl runs/holdout_r1.jsonl runs/holdout_v3t.jsonl --out <yours>.json`, then compare with `results/holdout.json`. The scorer is deterministic, and every model output is in the `raw` field verbatim.
3. **Recompute the configurations.** `python compose.py runs/holdout_main.jsonl runs/holdout_det.jsonl --split holdout --assign battery/assignment_from_dev.json --assign-kind battery/assignment_by_kind_from_dev.json --out <yours>.json`.
4. **Oracle validity.** Read `author_battery.py`. Contested oracles the auditor should weigh: extraction span boundaries (EX004 "9 October 2026" vs "Friday, 9 October 2026"; EX020 "06:10" vs "BLR 06:10"); `absent_count` ABSENT under the verbatim-span rule (EX019); subjective labels (`Wi-Fi is slow…` → medium). Changing any of these moves a handful of extraction or label cases. None changes the family-level labels in interim report 2, because no specialist cell is within 2 cases of a threshold except Granite native NEGATION (14/15, which has 3 incorrect executions) and SELECT (16/17).
5. **Model credit.** Confirm in `scorer.eval_select` that argument values never give credit (`arg_diag` is diagnostic only) and that `suppressed_calls` are never promoted.
6. **Run fresh.** Rerun any arm (README commands in report A) on the same digests, and compare outcomes record by record. Granite and Qwen at temperature 0 and seed 42 should reproduce. Needle is greedy, and its few flips (4/138) are in the records.

## 2. Claims to challenge

| Claim | Where | How to falsify |
|---|---|---|
| No specialist family cell reaches CANDIDATE | `results/holdout_role_labels.json` | Find a cell with ≥ 0.95 worst-of-3 and zero incorrect executions |
| Edge in front of the Brain lowers success (86 vs 109 of 138) | `results/compose_holdout.json` | Show a composition error, e.g. wrong fallback rule in `compose.stage` |
| Selective-by-kind equals Granite alone | `battery/assignment_by_kind_from_dev.json` | Show the dev assignment was computed wrongly |
| The verbatim-span check cannot stop a wrong but real span | examples in interim report 1 §5 | — |
| Latency differences are mostly placement | `runs/holdout_granitecpu.jsonl` | Re-measure on an idle machine |

## 3. Known weaknesses the auditor should weigh

- The battery author also wrote the harness; there is no independent authorship.
- Holdout family sizes are 5–17; the qualification plan's 150-per-segment gates were never reachable here (pre-registration §1).
- The typed tool catalogue is a projection; R1 uses the real schemas for selection only.
- Development and holdout runs overlapped with other sessions on the same Ollama server. Load snapshots are in every run file, and the coordinator reported pytest load around 08:40–09:00 IST.
- The deterministic rules are experimental, not a URI component; they had a filename bug corrected after the holdout (`deterministic_fix1`, reported separately).
- The URI-pipeline workflows (report D) use the real translator, gates and one real read-only tool; every other execution is a labelled test double.

## 4. Files

The complete file list with SHA-256 is in `reports/F_EVIDENCE_MANIFEST.json`. Earlier experimental evidence is not modified: `_V1/experimental/edge_model_tests/` and the Codex review stay where they are, untracked in `_V1`. Their paths and hashes are listed in report F.
