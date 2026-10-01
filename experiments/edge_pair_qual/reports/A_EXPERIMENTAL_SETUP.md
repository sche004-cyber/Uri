# Report A: Experimental setup (EPQ-1)

Branch `claude/project-thread-gb7z7s` on `sche004-cyber/Uri`, forked from the planning branch `claude/needle-granite-planning-nqic37` at `63557a6`. The two Claude reviews of the plan (`0be2c32` and `5f56992`, from `claude/project-thread-ux1rad`) are included under `docs/plans/`. No frozen file (M36/M37/M38 at `bd7c450`/`5bbf738`) and no live-app file (`server.py`, `file_store.py`, `uri_ui/`) was modified; every EPQ-1 file is under `experiments/edge_pair_qual/`. Frozen code is only imported (`uri_v1.memory.contracts.negated`; real `uri_core` translator, gates, tool schemas and `SystemPerformanceTool`).

## 1. Models and runtimes

| Item | Needle | Granite | Main Brain |
|---|---|---|---|
| Identity | Needle 3, `cactus-needle==3.0.2`, generation 3 | `granite4:350m-h` | `qwen3.5:9b` |
| Artifact | `needle3.cact` SHA-256 `c9d915eca282ed42d1a09b143b592adb4cc6744ffe2d294adf5cfc5548170c38`; HF snapshot `b274efcb211a9eef48c9a88da4b43bd569696a39`; `config.json` SHA-256 `32f855ed…7d25` | Ollama digest `7145075ed3d6da48bd41cafd8bed8171936abe0ece819aa1e516fd98881aa6a4`, GGUF, Q8_0, 340.33M parameters, family `granitehybrid` | Ollama digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`, Q4_K_M, 9.7B |
| Size | 121,021,910 parameters (config) | 366,214,486 bytes | 6,594,474,711 bytes |
| Runtime | Needle native engine in `C:\Users\cheta\Development\uri-agent\.venv-needle` (Python 3.13.15), driven by `needle_worker.py` over JSON lines with UTF-8 forced on both pipes | Ollama 0.34.1 (ROCm backend) | Ollama 0.34.1 |
| Placement | CPU (AMD Ryzen 9 5900X, 12 cores / 24 threads) | GPU (AMD Radeon RX 7900 GRE, 16 GiB, driver 32.0.31041.1004), fully offloaded, 427.6 MB VRAM. Placement-matched arm `granitecpu_*` uses `num_gpu: 0` | GPU, shared resident instance at the Ollama default context (262,144) |
| Context | 8,192 positions (model config) | `num_ctx` 4096 | Ollama default for the model |
| Decoding | greedy; `max_new_tokens` 256; no seed or temperature exposed | temperature 0, seed 42, `num_predict` 256 | temperature 0, seed 42, `num_predict` 256, `think: false` |
| Memory | about 102–106 MB (`peak_ram_mb` reported by Needle in every record) | 427.6 MB VRAM (`/api/ps`) | 14.2 GB VRAM at 262k context (`/api/ps`) |

Host: Windows 11 Pro 10.0.26200, 24 GiB RAM (25,690,996,736 bytes). Harness Python 3.13.15 with `httpx` 0.28.1 and `psutil` 7.2.2.

## 2. Equivalence of information

For every case all arms receive the same instruction text, the same tool definitions and the same user message (trusted conversation state, the untrusted document, then the request), produced by one function (`harness.spec`). Transports differ only where they must: Needle takes tools plus text; Granite native takes Ollama `tools`; Granite JSON takes a closed JSON schema built from the same tool list (`json_schema_for`) and the same tools rendered as text. Condition R1 replaces the typed catalogue with the real Brain-facing URI schemas from `uri_core.core.tool_schema.build_tool_schemas` (built offline with an empty multi-action registry, so no OAuth refresh).

## 3. Methodology

- Battery: 397 hand-authored cases in 12 families, oracle written as data before any harness or prompt existed, frozen at `a616680` (`battery/MANIFEST_battery.json`). Split by SHA-256 of `epq1-2026-09-30:<id>`: 259 development, 138 holdout.
- Pre-registration (`PREREGISTRATION.md`) fixes oracle rules, containment, metrics and decision rules; addendum 1 fixes the holdout arms before the holdout run. Harness frozen at `c17f593` (`battery/MANIFEST_harness.json`); `harness.py` refuses a holdout run if any frozen hash differs.
- Development split: one run per arm, used for diagnosis, repairs and the combined-configuration assignment. Holdout: run once, 3 repeats per arm; accuracy is worst-of-3.
- Scoring is deterministic code over the raw records (`scorer.py`, `compose.py`). The model gets credit for action choice only; argument values are a separate diagnostic; Needle `suppressed_calls` are never promoted.
- Concurrent load is recorded with every batch (`batch_start`, `load` every 50 calls, `batch_end`).

## 4. Reproduce

```
cd experiments/edge_pair_qual
python author_battery.py            # regenerates battery/cases.json; compare its hash with battery/MANIFEST_battery.json
python det_baseline.py --split holdout --out runs/holdout_det.jsonl
python harness.py --arms needle_P0,needle_P1,granite_native_P0,granite_native_P1,granite_json_P0,granite_json_P1,brain_P1 --split holdout --repeats 3 --out runs/holdout_main.jsonl
python scorer.py runs/holdout_main.jsonl runs/holdout_det.jsonl --out results/holdout.json
python compose.py runs/holdout_main.jsonl runs/holdout_det.jsonl --split holdout --assign battery/assignment_from_dev.json --assign-kind battery/assignment_by_kind_from_dev.json --out results/compose_holdout.json
```
Needle needs `NEEDLE_VENV_PYTHON` pointing at a Python with `cactus-needle==3.0.2` and the `needle3` weights cached for offline use. Ollama must serve the two digests above. Exact outputs from Granite and Qwen should reproduce at temperature 0 and seed 42 on the same backend; Needle is greedy. Latency will differ on other hardware.

## 5. Known setup limits

- Placement differs between Needle (CPU) and Granite (GPU); the `granitecpu_*` arm gives the placement-matched comparison.
- Another local client kept `qwen3.5:9b` resident and busy during development day 1; the Main Brain shares that instance. Ollama's desktop app shut itself down overnight (log: "shutting down ollama server", 2026-09-30 21:52); it was restarted headless (`ollama serve`, same 0.34.1 binary, same digests). Records lost to the outage are kept in `runs/FAILED_ollama_down_*.jsonl` and excluded.
- The typed tool catalogue is a projection: real URI tools mostly take `request_text` or nothing. Condition R1 measures the real schemas.
- Battery author and harness author are the same agent (Claude); independence relies on the freeze order and on the Codex audit (report G).
