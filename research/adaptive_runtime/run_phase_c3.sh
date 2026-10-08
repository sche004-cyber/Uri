#!/usr/bin/env bash
# Phase C part 3: controlled VRAM pressure. A research-owned second llama-server (small embedding model, GPU
# offloaded, oversized batch/context so it holds ~1-1.5 GB of VRAM) stands in for "another GPU consumer"; the
# frozen configuration, the vision-on-CPU variant and the memory-priority variant are then loaded next to it.
# Usage: bash run_phase_c3.sh <deadline_epoch>
set -u
cd "$(dirname "$0")"
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
SMALL="C:/Users/cheta/Development/uri-innovation-lab/.lab/models/nomic-embed-text-v1.5.Q8_0.gguf"   # read-only use
DL=${1:-0}
export URI_BENCH_IDLE_CEILING_MIB=3500

vram() { powershell -NoProfile -Command "[int]((Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Maximum).Maximum/1MB"; }

summ() {
  $PY - "$1" <<'EOF'
import json, glob, sys
f = sorted(glob.glob(f"evidence/{sys.argv[1]}_*.json"))[-1]
r = json.load(open(f))
d = r.get("decode", {}); dc = r.get("decision", {}); e = r.get("end", {}); v = r.get("vision") or {}
m = e.get("server_gpu_memory_mib") or {}
print("PRESSURE", sys.argv[1], "load", r.get("load_seconds"), "vram_at_start", r.get("vram_dedicated_at_start_mib"),
      "decode_tps_p50", (d.get("tps") or {}).get("p50"), "decision_total_p50", (dc.get("total") or {}).get("p50"),
      "vision_p50", (v.get("total") or {}).get("p50") if isinstance(v, dict) else None,
      "local", m.get("local usage"), "nonlocal", m.get("non local usage"), "vram_peak", e.get("peak_vram_dedicated_mib"), "fatal", r.get("fatal"))
EOF
}

echo "=== pressure consumer start $(date -u +%H:%M:%SZ) idle VRAM $(vram) MiB"
"$B11425/llama-server.exe" -m "$SMALL" --embeddings --pooling mean -ngl 99 -c 8192 -b 8192 -ub 8192 -np 6 \
  --host 127.0.0.1 --port 18498 --no-webui > evidence/pressure_consumer.log 2>&1 &
CPID=$!
for i in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18498/health 2>/dev/null | grep -q 200 && break; sleep 1; done
# touch it once so its compute buffers are allocated
curl -s -o /dev/null -X POST http://127.0.0.1:18498/v1/embeddings -H "Content-Type: application/json" -d '{"input":"warm up the consumer"}'
sleep 2
echo "=== consumer pid $CPID healthy; VRAM now $(vram) MiB $(date -u +%H:%M:%SZ)"

for v in "expP_pressure_plain:" "expP_pressure_mmprojcpu:--extra=--no-mmproj-offload" "expP_pressure_memprio:--env GGML_VK_ENABLE_MEMORY_PRIORITY=1"; do
  n=${v%%:*}; a=${v#*:}
  echo "=== $n $(date -u +%H:%M:%SZ) VRAM before $(vram) MiB"
  $PY bench_runtime.py --name "$n" --binary-dir "$B11425" --model-dir "$MD" --deadline-epoch "$DL" $a \
    --skip prefill,cancel,stability --decode-rounds 3 --decision-rounds 4 2>&1 | grep -E "healthy|FATAL|vision [0-9]"
  summ "$n"
done

kill $CPID 2>/dev/null; sleep 3
echo "=== consumer stopped; VRAM $(vram) MiB; DONE4 $(date -u +%H:%M:%SZ)"
