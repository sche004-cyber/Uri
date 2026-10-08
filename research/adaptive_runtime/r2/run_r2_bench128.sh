#!/usr/bin/env bash
# R2 isolation of the 128 MiB prefill cost: (1) llama-bench (no server, no vision, no MTP; request ~13.2 GB, fully
# resident on the idle desktop) default vs 128 MiB blocks, interleaved x2; (2) llama-server idle loads of the
# vision_cpu profile (fits, ~0 demoted) with 128 MiB blocks, so a prefill difference can be attributed either to the
# block size itself or to demotion.
set -u
cd "$(dirname "$0")/.."
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
export URI_BENCH_IDLE_CEILING_MIB=2500
guard() { $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --json; }
S128="GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728"
echo "=== R2 bench128 start $(date -u +%H:%M:%SZ)"
guard 120
for i in 1 2; do
  guard 0 > /dev/null; echo "=== llama-bench default r$i $(date -u +%H:%M:%SZ)"
  $PY run_llama_bench.py --name "r2B_default_r$i" --binary-dir "$B11425" --pp 1024,8192 --pp-long 16384,32768 2>&1 | tail -4
  guard 0 > /dev/null; echo "=== llama-bench sub128 r$i $(date -u +%H:%M:%SZ)"
  $PY run_llama_bench.py --name "r2B_sub128_r$i" --binary-dir "$B11425" --env "$S128" --pp 1024,8192 --pp-long 16384,32768 2>&1 | tail -4
done
for i in 1 2; do
  guard 0 > /dev/null; n="r2I_vision_cpu_sub128_r$i"; echo "=== $n $(date -u +%H:%M:%SZ)"
  $PY bench_runtime.py --name "$n" --binary-dir "$B11425" --model-dir "$MD" --env "$S128" --extra=--no-mmproj-offload \
    --skip cancel,stability --sizes 1000,8000,30000 --decode-rounds 3 --decision-rounds 4 2>&1 | grep -E "healthy after|FATAL|prefill 30000"
done
echo "=== R2BENCH128_DONE $(date -u +%H:%M:%SZ)"
