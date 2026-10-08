#!/usr/bin/env bash
# Phase C experiments (sequential; one GPU owner at a time). Research only.
# Usage: bash run_phase_c.sh <deadline_epoch>
set -u
cd "$(dirname "$0")"
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
B11510="C:/Users/cheta/Development/uri-adaptive-lab/runtime/b11510-vulkan"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"   # hash-identical NVMe copies of the pinned files
DL=${1:-0}

summ() {
  $PY - "$1" <<'EOF'
import json, glob, sys
f = sorted(glob.glob(f"evidence/{sys.argv[1]}_*.json"))[-1]
r = json.load(open(f))
d = r.get("decode", {}); dc = r.get("decision", {}); e = r.get("end", {}); a = r.get("after_load", {}); pf = r.get("prefill", {})
print("SUMMARY", sys.argv[1], "load", r.get("load_seconds"), "waited", r.get("gpu_release_wait_before_start_s"),
      "decode_tps_p50", (d.get("tps") or {}).get("p50"), "decision_total_p50", (dc.get("total") or {}).get("p50"),
      "decision_ttft_p50", (dc.get("ttft") or {}).get("p50"),
      "pp30k", (pf.get("30000") or {}).get("fresh", {}).get("prompt_per_second"),
      "gpu_after_load", a.get("server_gpu_memory_mib"), "gpu_end", e.get("server_gpu_memory_mib"),
      "vram_peak", e.get("peak_vram_dedicated_mib"), "rss", e.get("server_rss_now_mib"), "fatal", r.get("fatal"))
EOF
}

run() {  # name binary_dir extra-args...
  local name=$1 bin=$2; shift 2
  echo "=== $name $(date -u +%H:%M:%SZ)"
  $PY bench_runtime.py --name "$name" --binary-dir "$bin" --model-dir "$MD" --deadline-epoch "$DL" "$@" 2>&1 | grep -E "decode [0-9]|decision [0-9]|prefill|healthy|FATAL|wrote|cancel|timeout|stability|vision"
  summ "$name"
}

# E-M: frozen config with the Vulkan memory logger: how much is requested device-local vs host-visible
run expM_b11425_memlog "$B11425" --env GGML_VK_MEMORY_LOGGER=1 --skip prefill,decision,cancel,stability,vision --decode-rounds 2
# E-A: frozen config + Vulkan memory priority (all ggml allocations priority 1.0), pinned binary
run expA_b11425_memprio "$B11425" --env GGML_VK_ENABLE_MEMORY_PRIORITY=1 --skip cancel,stability --decode-rounds 4 --decision-rounds 6
# E-U: frozen config but -ub 512 (smaller compute buffers; prefill cost to be measured)
run expU_b11425_ub512 "$B11425" --extra "-ub 512" --skip cancel,stability --decode-rounds 4 --decision-rounds 6
# E-N: frozen config but the vision projector stays on the CPU (stock --no-mmproj-offload): frees ~0.84 GB VRAM
run expN_b11425_mmproj_cpu "$B11425" --extra "--no-mmproj-offload" --skip cancel,stability --decode-rounds 4 --decision-rounds 6
# E-B: upstream b11510, frozen flags, no env
run expB_b11510_plain "$B11510" --skip cancel,stability --decode-rounds 4 --decision-rounds 6
# E-C: upstream b11510 + memory priority
run expC_b11510_memprio "$B11510" --env GGML_VK_ENABLE_MEMORY_PRIORITY=1 --skip cancel,stability --decode-rounds 4 --decision-rounds 6
echo "=== DONE $(date -u +%H:%M:%SZ)"
