#!/usr/bin/env bash
# Phase C part 3: controlled VRAM pressure. The installed Ollama service holds an already-pulled 0.8B model
# (~1-1.5 GB of VRAM) as a stand-in for "another GPU consumer"; the frozen configuration, the vision-on-CPU
# variant and the memory-priority variant are then loaded next to it.
# Usage: bash run_phase_c3.sh <deadline_epoch>
set -u
cd "$(dirname "$0")"
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
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
# Consumer: the already-installed Ollama service loads its already-pulled qwen3.5:0.8b (ROCm/Vulkan, ~1-1.5 GB of VRAM)
# and keeps it resident for 40 minutes. Nothing is pulled or written; the model is unloaded at the end (keep_alive 0).
curl -s -o evidence/pressure_consumer_ollama.json -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json"   -d '{"model":"qwen3.5:0.8b","prompt":"Say OK.","stream":false,"keep_alive":"40m","options":{"num_predict":4}}'
sleep 3
curl -s http://127.0.0.1:11434/api/ps > evidence/pressure_consumer_ps.json; cat evidence/pressure_consumer_ps.json; echo
echo "=== consumer resident; VRAM now $(vram) MiB $(date -u +%H:%M:%SZ)"

for v in "expP_pressure_plain:" "expP_pressure_mmprojcpu:--extra=--no-mmproj-offload" "expP_pressure_memprio:--env GGML_VK_ENABLE_MEMORY_PRIORITY=1"; do
  n=${v%%:*}; a=${v#*:}
  echo "=== $n $(date -u +%H:%M:%SZ) VRAM before $(vram) MiB"
  $PY bench_runtime.py --name "$n" --binary-dir "$B11425" --model-dir "$MD" --deadline-epoch "$DL" $a \
    --skip prefill,cancel,stability --decode-rounds 3 --decision-rounds 4 2>&1 | grep -E "healthy|FATAL|vision [0-9]"
  summ "$n"
done

curl -s -o /dev/null -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" -d '{"model":"qwen3.5:0.8b","keep_alive":0}'; sleep 5
echo "=== consumer stopped; VRAM $(vram) MiB; DONE4 $(date -u +%H:%M:%SZ)"
