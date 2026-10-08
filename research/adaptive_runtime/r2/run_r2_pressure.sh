#!/usr/bin/env bash
# R2 pressure campaign: interleaved independent loads of the frozen Runtime v1 configuration with 128 MiB Vulkan
# suballocation blocks (candidate) and with the default 1 GiB blocks (control), next to a 1.09 GB GPU consumer
# (the installed Ollama service holding its already-pulled qwen3.5:0.8b). Every load: prefill 1k/8k/30k (fresh,
# repeat, new turn), 3 decode rounds, 4 decision turns, 2 vision turns; per-process residency at load and end;
# an isolated residency watchdog attached to each server. The GPU-owner guard runs before every load and never
# starts next to a foreign GPU process.
# Usage: bash run_r2_pressure.sh [sequence]   (default: 10 x sub128 + 5 x default, interleaved)
set -u
cd "$(dirname "$0")/.."
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
SEQ=${1:-"s128 s128 def s128 s128 def s128 s128 def s128 s128 def s128 s128 def"}
export URI_BENCH_IDLE_CEILING_MIB=3500
mkdir -p evidence/r2_watch

vram() { powershell -NoProfile -Command "[int64](((Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Maximum).Maximum/1MB)"; }
guard() { $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --max-cpu 30 --json; }
consumer_on() {
  curl -s -o evidence/r2_consumer_generate.json -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" \
    -d '{"model":"qwen3.5:0.8b","prompt":"Say OK.","stream":false,"keep_alive":"180m","options":{"num_predict":4,"num_ctx":4096}}'
  sleep 3; curl -s http://127.0.0.1:11434/api/ps | tee evidence/r2_consumer_ps_$(date -u +%H%M%S).json; echo
}
consumer_check() { curl -s http://127.0.0.1:11434/api/ps | grep -q '"size_vram"' || { echo "consumer dropped; reloading"; consumer_on; }; }
consumer_off() { curl -s -o /dev/null -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" -d '{"model":"qwen3.5:0.8b","keep_alive":0}'; sleep 5; }

summ() {
  $PY - "$1" <<'EOF'
import json, glob, sys
f = sorted(glob.glob(f"evidence/{sys.argv[1]}_*.json"))[-1]
r = json.load(open(f))
d = r.get("decode", {}); dc = r.get("decision", {}); e = r.get("end", {}); v = r.get("vision") or {}; p = r.get("prefill") or {}
al = (r.get("after_load") or {}).get("server_gpu_memory_mib") or {}
m = e.get("server_gpu_memory_mib") or {}
pf = {k: (p[k]["fresh"].get("prompt_per_second"), p[k]["fresh"].get("ttft_s"), p[k]["repeat"].get("ttft_s")) for k in p}
print("R2LOAD", sys.argv[1], "load_s", r.get("load_seconds"), "vram_at_start", r.get("vram_dedicated_at_start_mib"),
      "decode_p50", (d.get("tps") or {}).get("p50"), "decode_min", (d.get("tps") or {}).get("min"),
      "decision_p50", (dc.get("total") or {}).get("p50"), "decision_p95", (dc.get("total") or {}).get("p95"),
      "vision_p50", (v.get("total") or {}).get("p50") if isinstance(v, dict) else None,
      "prefill(pps,ttft,repeat_ttft)", pf,
      "load_local/non", al.get("local usage"), al.get("non local usage"), "end_local/non", m.get("local usage"), m.get("non local usage"),
      "errors", (d.get("errors", 0) + dc.get("errors", 0) + (v.get("errors", 0) if isinstance(v, dict) else 0)), "healthy_end", r.get("healthy_end"), "fatal", r.get("fatal"))
EOF
}

echo "=== R2 pressure campaign start $(date -u +%H:%M:%SZ); sequence: $SEQ"
guard 300
echo "=== GPU clear $(date -u +%H:%M:%SZ); idle VRAM $(vram) MiB"
$PY residency_watch.py --seconds 5400 --interval 5 --out evidence/r2_residency_pressure.csv > evidence/r2_residency_pressure_console.txt 2>&1 &
RWPID=$!
consumer_on
echo "=== consumer resident; VRAM $(vram) MiB $(date -u +%H:%M:%SZ)"
i128=0; idef=0
for k in $SEQ; do
  # never keep the consumer resident next to a foreign GPU process: drop it, wait for a quiet GPU, reload it
  if ! $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout 0 --block-cmd uri_operational_intelligence.host --max-cpu 30 --json > /dev/null 2>&1; then
    echo "=== foreign GPU owner appeared $(date -u +%H:%M:%SZ): consumer unloaded, waiting for a quiet GPU"
    consumer_off
    guard 300 > /dev/null
    consumer_on
    echo "=== consumer resident again; VRAM $(vram) MiB $(date -u +%H:%M:%SZ)"
  fi
  consumer_check
  if [ "$k" = s128 ]; then i128=$((i128+1)); n="r2P_sub128_r$i128"; a="--env GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728"; else idef=$((idef+1)); n="r2P_default_r$idef"; a=""; fi
  echo "=== $n $(date -u +%H:%M:%SZ) VRAM before $(vram) MiB"
  $PY r2/residency_watchdog.py --port 18497 --seconds 900 --interval 5 --expected-tps 110 --out "evidence/r2_watch/$n" --stop-when-gone > "evidence/r2_watch/$n.console.txt" 2>&1 &
  WD=$!
  $PY bench_runtime.py --name "$n" --binary-dir "$B11425" --model-dir "$MD" $a \
    --skip cancel,stability --sizes 1000,8000,30000 --decode-rounds 3 --decision-rounds 4 2>&1 | grep -E "healthy after|FATAL|wrote"
  wait $WD
  summ "$n"
  tail -c 400 "evidence/r2_watch/$n.console.txt"; echo
done
consumer_off
kill $RWPID 2>/dev/null
echo "=== consumer stopped; VRAM $(vram) MiB; R2PRESSURE_DONE $(date -u +%H:%M:%SZ)"
