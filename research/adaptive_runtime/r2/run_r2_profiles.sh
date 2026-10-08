#!/usr/bin/env bash
# R2 phase 2: (a) idle-desktop comparison of 128 MiB blocks vs default (AC3, with prefill 1k/8k/30k and vision);
# (b) validation of the planner's fit-under-budget profiles next to the 1.09 GB consumer and on the idle desktop
# (default blocks): vision_cpu (--no-mmproj-offload), no_mtp, vision_cpu_no_mtp. Same binary, flags, hashes, prompts.
# Usage: bash run_r2_profiles.sh [idle|pressure|all]
set -u
cd "$(dirname "$0")/.."
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
B11425="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64"
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
WHICH=${1:-all}
export URI_BENCH_IDLE_CEILING_MIB=3500
mkdir -p evidence/r2_watch
vram() { powershell -NoProfile -Command "[int64](((Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Maximum).Maximum/1MB)"; }
guard() { $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --max-cpu 30 --json; }
consumer_on() { curl -s -o /dev/null -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" -d '{"model":"qwen3.5:0.8b","prompt":"Say OK.","stream":false,"keep_alive":"180m","options":{"num_predict":4,"num_ctx":4096}}'; sleep 3; curl -s http://127.0.0.1:11434/api/ps | head -c 200; echo; }
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
pf = {k: (round(p[k]["fresh"].get("prompt_per_second") or 0), p[k]["fresh"].get("ttft_s")) for k in p}
print("R2LOAD", sys.argv[1], "load_s", r.get("load_seconds"), "vram_at_start", r.get("vram_dedicated_at_start_mib"),
      "decode_p50", (d.get("tps") or {}).get("p50"), "decision_p50", (dc.get("total") or {}).get("p50"),
      "vision_p50", (v.get("total") or {}).get("p50") if isinstance(v, dict) else None, "prefill(pps,ttft)", pf,
      "load_local/non", al.get("local usage"), al.get("non local usage"), "end_local/non", m.get("local usage"), m.get("non local usage"),
      "healthy_end", r.get("healthy_end"), "fatal", r.get("fatal"))
EOF
}
one() {   # name args...
  local n=$1; shift
  guard 0 > /dev/null
  echo "=== $n $(date -u +%H:%M:%SZ) VRAM before $(vram) MiB"
  local HV=872 ET=110
  case "$n" in *no_mtp*) HV=498; ET=100 ;; *vision_cpu*) HV=900 ;; esac
  $PY r2/residency_watchdog.py --port 18497 --seconds 900 --interval 5 --expected-tps $ET --host-visible-mib $HV --out "evidence/r2_watch/$n" --stop-when-gone > "evidence/r2_watch/$n.console.txt" 2>&1 &
  local WD=$!
  $PY bench_runtime.py --name "$n" --binary-dir "$B11425" --model-dir "$MD" "$@" \
    --skip cancel,stability --sizes 1000,8000,30000 --decode-rounds 3 --decision-rounds 4 2>&1 | grep -E "healthy after|FATAL|wrote"
  wait $WD
  summ "$n"
}
S128="--env GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728"
echo "=== R2 profiles start $(date -u +%H:%M:%SZ) which=$WHICH"
guard 300
if [ "$WHICH" = all ] || [ "$WHICH" = idle ]; then
  export URI_BENCH_IDLE_CEILING_MIB=2500
  echo "=== idle phase; VRAM $(vram) MiB"
  for i in 1 2 3; do
    one "r2I_sub128_r$i" $S128
    one "r2I_default_r$i"
  done
  one "r2I_vision_cpu_r1" --extra=--no-mmproj-offload
  one "r2I_vision_cpu_r2" --extra=--no-mmproj-offload
  one "r2I_no_mtp_r1" --no-mtp
fi
if [ "$WHICH" = all ] || [ "$WHICH" = pressure ]; then
  export URI_BENCH_IDLE_CEILING_MIB=3500
  guard 0 > /dev/null
  consumer_on
  echo "=== pressure phase; VRAM $(vram) MiB $(date -u +%H:%M:%SZ)"
  for i in 1 2 3; do
    consumer_check
    one "${PFX:-r2V}_vision_cpu_no_mtp_r$i" --extra=--no-mmproj-offload --no-mtp
  done
  for i in 1 2; do
    consumer_check
    one "${PFX:-r2V}_vision_cpu_r$i" --extra=--no-mmproj-offload
    consumer_check
    one "${PFX:-r2V}_no_mtp_r$i" --no-mtp
  done
  consumer_check
  one "${PFX:-r2V}_vision_cpu_no_mtp_sub128_r1" --extra=--no-mmproj-offload --no-mtp $S128
  consumer_off
fi
echo "=== R2PROFILES_DONE $(date -u +%H:%M:%SZ) VRAM $(vram) MiB"
