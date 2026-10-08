#!/usr/bin/env bash
# Phase C part 2: repeated-load placement distribution (frozen config vs memory priority), kernel-level
# llama-bench on both binaries. Research only. Usage: bash run_phase_c2.sh <deadline_epoch>
set -u
cd "$(dirname "$0")"
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
B11510="C:/Users/cheta/Development/uri-adaptive-lab/runtime/b11510-vulkan"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
DL=${1:-0}

summ() {
  $PY - "$1" <<'EOF'
import json, glob, sys
f = sorted(glob.glob(f"evidence/{sys.argv[1]}_*.json"))[-1]
r = json.load(open(f))
d = r.get("decode", {}); e = r.get("end", {})
m = e.get("server_gpu_memory_mib") or {}
print("REPEAT", sys.argv[1], "load", r.get("load_seconds"), "decode_tps_p50", (d.get("tps") or {}).get("p50"),
      "local", m.get("local usage"), "nonlocal", m.get("non local usage"), "vram_peak", e.get("peak_vram_dedicated_mib"), "fatal", r.get("fatal"))
EOF
}

# N (re-run; argparse needs --extra=): vision encoder on the CPU, frees ~1.08 GiB device memory
echo "=== expN_b11425_mmproj_cpu $(date -u +%H:%M:%SZ)"
$PY bench_runtime.py --name expN_b11425_mmproj_cpu --binary-dir "$B11425" --model-dir "$MD" --deadline-epoch "$DL" --extra=--no-mmproj-offload --skip cancel,stability --decode-rounds 4 --decision-rounds 6 2>&1 | grep -E "decode [0-9]|decision [0-9]|prefill|healthy|FATAL|wrote|vision"
summ expN_b11425_mmproj_cpu

# R: 4 alternating loads of the frozen configuration without and with GGML_VK_ENABLE_MEMORY_PRIORITY=1
for i in 1 2 3 4; do
  for v in plain memprio; do
    name="rep${i}_${v}"
    if [ "$v" = "memprio" ]; then envarg="--env GGML_VK_ENABLE_MEMORY_PRIORITY=1"; else envarg=""; fi
    echo "=== $name $(date -u +%H:%M:%SZ)"
    $PY bench_runtime.py --name "$name" --binary-dir "$B11425" --model-dir "$MD" --deadline-epoch "$DL" $envarg \
      --skip prefill,decision,cancel,stability,vision --decode-rounds 2 2>&1 | grep -E "FATAL|healthy"
    summ "$name"
  done
done

# K: kernel-level throughput, both binaries (pp 1k/8k/32k, tg 128)
for b in "base_b11425:$B11425" "b11510:$B11510"; do
  n=${b%%:*}; d=${b#*:}
  echo "=== llama-bench $n $(date -u +%H:%M:%SZ)"
  $PY run_llama_bench.py --name "$n" --binary-dir "$d" --deadline-epoch "$DL" 2>&1 | tail -8
done
echo "=== DONE2 $(date -u +%H:%M:%SZ)"

# S: short soak of the memory-priority candidate (200 decision turns + vision + cancel), frozen flags
echo "=== expS_memprio_soak $(date -u +%H:%M:%SZ)"
$PY bench_runtime.py --name expS_memprio_soak --binary-dir "$B11425" --model-dir "$MD" --deadline-epoch "$DL" --env GGML_VK_ENABLE_MEMORY_PRIORITY=1 --skip prefill,decode,decision --stability-rounds 200 2>&1 | grep -E "stability|healthy|FATAL|wrote|vision|cancel|timeout"
summ expS_memprio_soak
echo "=== DONE3 $(date -u +%H:%M:%SZ)"
