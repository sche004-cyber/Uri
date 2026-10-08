# Model research and shortlist (2026-10-05)

## Hard constraints used for shortlisting

- GPU: Radeon RX 7900 GRE, 16 368 MiB VRAM (≈15.3 GiB usable; the desktop holds ≈0.95 GiB).
- RAM: 24 GiB total. With Chrome, Claude and Windows running, ≈12–14 GiB is realistically free for a model process.
- Runtime: llama.cpp b11425 Vulkan sees the GPU. The ROCm 10.0 Windows build reports no device on this driver and was dropped. Ollama 0.34.1 (own ROCm backend) is kept as an incumbent runtime.
- Feasible footprint: weights ≤ ≈14.5 GiB fully on GPU, or MoE with ≤ ≈7 GiB of experts on CPU. Anything needing more than ≈34 GiB of total memory cannot run.

## Field surveyed

Sources: Hugging Face model API (downloads, file sizes, LFS hashes), official model cards, and community guides from 2026.

| Family | Variant considered | Architecture | Smallest sensible GGUF | Decision |
|---|---|---|---|---|
| Google Gemma 4 | 26B-A4B-it QAT Q4_0 | MoE, 25.2B total / 3.8B active, vision projector | 13.45 GiB (+1.11 GiB mmproj) | **Shortlist.** Already on disk; hash matches `lmstudio-community` Hub LFS oid `a586dac5…5389` |
| Google Gemma 4 | 31B dense | dense | QAT Q4_0 ≈ 17 GiB | Reject: does not fit VRAM, so dense CPU spill |
| Google Gemma 4 | 12B (incumbent `gemma4:12b`) | dense | 7.6 GB | **Shortlist** as incumbent control |
| Qwen 3.6 | 35B-A3B | MoE, 3B active, vision projector | UD-Q4_K_M 20.6 GiB (CPU-MoE needed) | **Shortlist** |
| Qwen 3.8 | 27B (Aug 2026) | hybrid-attention dense, native VL | UD-IQ4_XS 13.27 GiB | **Shortlist** (strongest dense that fits) |
| Qwen 3.8 | Flash-Next 125B-A6B | MoE + 51B n-gram embeddings | IQ2_XS ≈ 63 GiB | Reject on fit: exceeds the 40 GiB total memory |
| Qwen 3.8 | community "35B-A3B-Distill" | unofficial distill | — | Reject: unofficial lineage, no model card provenance |
| Qwen 3.5 | 9B (incumbent `qwen3.5:9b`) / 2B | dense | 5.2 / 1.2 GiB | **Shortlist**: incumbent and fast-tier probe |
| OpenAI | gpt-oss-20b | MoE 21B / 3.6B active, low/medium/high effort | MXFP4 12.1 GiB | **Shortlist**: native reasoning-effort control |
| NVIDIA | Nemotron-3.5-Lightning-30B-A3B (Aug 2026) | Mamba-2 + MoE hybrid | Q4_0 17.6 GiB (CPU-MoE needed) | **Shortlist**: hybrid with cheap long context |
| IBM | Granite 4.2 30B | dense | ≈ 18 GiB at Q4 | Reject: dense model larger than VRAM |
| IBM | Granite 4.2 8B / 3B | dense | — | Not shortlisted: no expected gain over the Qwen 3.5 9B / 2B controls |
| Mistral | Small 4 119B-A6B | MoE | > 60 GiB | Reject on fit |
| Mistral | Devstral Small 2 24B / Small 3.2 24B | dense | Q4_K_M ≈ 14.3 GiB | Not shortlisted: a coding specialist, or older than Gemma 4 26B / Qwen 3.8 27B at the same footprint |
| Z.ai | GLM-4.7-Flash 30B-A3B (Jan 2026) | MoE | ≈ 18 GiB | Not shortlisted: same slot as Qwen 3.6-35B-A3B and Nemotron 3.5, which are newer |
| Liquid | LFM2.5 8B-A1B / 2.6B | hybrid | small | Not shortlisted: earlier Edge qualification (M33.2 B.4) showed tiny language workers did not justify residency |

## Download record

`D:\uri-model-lab\dl\manifest.jsonl` records the repository, revision, path, size and recomputed sha256 of every downloaded file, checked against the Hub LFS oid. Pre-existing user models (Ollama store, LM Studio folder) were only read, never modified.
