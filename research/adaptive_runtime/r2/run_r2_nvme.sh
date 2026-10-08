#!/usr/bin/env bash
# R2 NVMe vs HDD placement: interleaved loads of the identical frozen configuration (default blocks, idle desktop)
# from the D: HDD originals and from the hash-identical C: NVMe copies. Load time to /health, then a short decode +
# decision check so a slow-storage load is also checked for correctness of residency. Page cache is not dropped
# (no privilege); interleaving makes the two files compete for the 24 GB of RAM, which is the realistic case.
set -u
cd "$(dirname "$0")/.."
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
export URI_BENCH_IDLE_CEILING_MIB=2500
guard() { $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --max-cpu 30 --json; }
avail() { $PY -c "import psutil;print(round(psutil.virtual_memory().available/2**20))"; }
echo "=== R2 NVMe/HDD start $(date -u +%H:%M:%SZ)"
guard 120
for i in 1 2 3; do
  for loc in hdd nvme; do
    guard 0 > /dev/null
    n="r2N_${loc}_r$i"
    echo "=== $n $(date -u +%H:%M:%SZ) RAM available $(avail) MiB"
    if [ $loc = nvme ]; then a="--model-dir $MD"; else a=""; fi
    $PY bench_runtime.py --name "$n" --binary-dir "$B11425" $a --skip prefill,cancel,stability,vision --decode-rounds 2 --decision-rounds 2 2>&1 | grep -E "healthy after|FATAL"
  done
done
echo "=== R2NVME_DONE $(date -u +%H:%M:%SZ)"
