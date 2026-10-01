# Report F: Qualification evidence package

Everything is under `experiments/edge_pair_qual/` on branch `claude/project-thread-gb7z7s`. `reports/F_EVIDENCE_MANIFEST.json` lists the SHA-256 and size of every file, plus the earlier evidence that stays untracked in `_V1` (the Codex review, its evidence JSON, the Stage-1 `fresh_20260929` files and the Stage-1 Needle bridge). Rebuild it with `python build_manifest.py`.

| Kind | Files |
|---|---|
| Frozen fixtures and oracle | `battery/cases.json` (397 cases), `author_battery.py`, `catalogue.py`, `battery/MANIFEST_battery.json` |
| Pre-registration | `PREREGISTRATION.md`; the frozen part ends at "Addenda (append only)", followed by addendum 1 |
| Harness freeze | `battery/MANIFEST_harness.json`, `battery/assignment_by_kind_from_dev.json`, `battery/assignment_from_dev.json` |
| Runners | `harness.py`, `needle_worker.py`, `det_baseline.py`, `integration.py`, `faults.py`, `coldstart.py`, `rar_probe.py` |
| Scoring | `scorer.py`, `compose.py`, `role_labels.py`, `make_tables.py`, `inspect_failures.py` |
| Raw model outputs and telemetry | `runs/*.jsonl` (provider responses verbatim; load snapshots every 50 calls). Development: `dev_v1`, `dev_v2`, `dev_v2_r1`, `dev_v3`, `dev_v3t`, `dev_v1_granitecpu`, `det_dev`, `dev_det_fix1`. Holdout: `holdout_main`, `holdout_granitecpu`, `holdout_r1`, `holdout_v3t`, `holdout_det`, `holdout_det_fix1`. Idle rerun: `latency_idle_holdout` (partial) |
| Excluded but preserved | `runs/FAILED_ollama_down_*.jsonl` (connection refused during the Ollama outage), `runs/SUPERSEDED_partial_dev_v1_granitecpu.jsonl` (duplicate records from a stopped process) |
| Other measurements | `runs/coldstart_*.json`, `runs/faults_*.json`, `runs/integration_*.json`, `runs/rar_probe.json` |
| Scored results | `results/dev_v1.json`, `dev_v2.json`, `dev_v3.json`, `holdout.json`, `holdout_role_labels.json`, `compose_*.json`, `holdout_tables.md`, `latency_idle_holdout.json` |
| Reports | `reports/INTERIM_1_DEV_BATCH.md`, `INTERIM_2_HOLDOUT.md`, `A`–`G` |

## Qualification-gate outcomes

| Gate | Outcome |
|---|---|
| Pre-registered role labels (§6), holdout | **No CANDIDATE for Needle or Granite in any family.** PARTIAL: Granite native ARGS (10/12), CPU Granite JSON SELECT (15/17). Everything else UNSUITABLE_AT_THIS_CONFIG (`results/holdout_role_labels.json`) |
| Zero-tolerance (incorrect execution after containment) | violated by every specialist arm in 9–11 of 12 families |
| Qualification plan G-gates (n ≥ 150 per segment) | **not evaluable**: holdout n per family is 5–17 (stated in pre-registration §1 before any run) |
| Comparative pass rule (plan §7) | No Edge-model configuration is non-inferior to the Main Brain alone (report C §2) |
| Independent audit | **not done**: Codex is paused; handoff in report G |

Status: **NOT QUALIFIED.** No model or pairing is qualified by this package.
