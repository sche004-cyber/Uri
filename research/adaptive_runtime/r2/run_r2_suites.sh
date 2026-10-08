#!/usr/bin/env bash
# R2 regression suites on the exact frozen Runtime v1 command line (release b11425, section-2 flags, 32k, vision,
# MTP), fast path, suites F,D,DG,C,H,S,O,R,RH,L,P,V with L at 4k/12k/28k, i.e. the `ue_cand_mtp2` qualification run.
# Three runs: 128 MiB blocks on an idle desktop; 128 MiB blocks next to the 1.09 GB consumer; default blocks next to
# the consumer (control). Model files are the hash-identical NVMe copies (sha256 recorded by run_bench.py).
# Usage: bash run_r2_suites.sh [which]   which = idle128 | pressure128 | pressuredef | all (default)
set -u
cd "$(dirname "$0")/../../.."     # worktree root (run_bench.py needs the repo root for the Core seams)
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
MD="C:/Users/cheta/Development/uri-adaptive-lab/models"
M="$MD/Qwen3.6-35B-A3B-UD-IQ3_S.gguf"
MM="$MD/mmproj-F16.gguf"
EXTRA="-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 -md $MD/mtp-qwen36-35b-a3b-Q4_K_M.gguf --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
EXTRA_NOMTP="-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16"
R=research/adaptive_runtime
WHICH=${1:-all}
mkdir -p $R/evidence/r2_watch

vram() { powershell -NoProfile -Command "[int64](((Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Maximum).Maximum/1MB)"; }
guard() { $PY $R/r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --max-cpu 30 --json; }
wait_release() { local lim=$1; for i in $(seq 1 60); do v=$(vram); [ "$v" -lt "$lim" ] && break; sleep 2; done; echo "VRAM after release wait: $(vram) MiB"; }
consumer_on() {
  curl -s -o /dev/null -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" \
    -d '{"model":"qwen3.5:0.8b","prompt":"Say OK.","stream":false,"keep_alive":"180m","options":{"num_predict":4,"num_ctx":4096}}'
  sleep 3; curl -s http://127.0.0.1:11434/api/ps; echo
}
consumer_off() { curl -s -o /dev/null -X POST http://127.0.0.1:11434/api/generate -H "Content-Type: application/json" -d '{"model":"qwen3.5:0.8b","keep_alive":0}'; sleep 5; }

run_suite() {   # name blocks(1|0) release_limit [profile: full|vision_cpu|no_mtp|vision_cpu_no_mtp]
  local n=$1 blocks=$2 lim=$3 prof=${4:-full}
  local X="$EXTRA" HV=872
  case "$prof" in
    vision_cpu) X="$EXTRA --no-mmproj-offload"; HV=900 ;;
    no_mtp) X="$EXTRA_NOMTP"; HV=498 ;;
    vision_cpu_no_mtp) X="$EXTRA_NOMTP --no-mmproj-offload"; HV=498 ;;
  esac
  guard 0 > /dev/null
  wait_release "$lim"
  if [ "$blocks" = 1 ]; then export GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728; else unset GGML_VK_SUBALLOCATION_BLOCK_SIZE; fi
  echo "=== suite $n $(date -u +%H:%M:%SZ) profile=$prof blocks=$blocks VRAM before $(vram) MiB env=${GGML_VK_SUBALLOCATION_BLOCK_SIZE:-default}"
  $PY $R/r2/residency_watchdog.py --port 18481 --seconds 2400 --interval 5 --expected-tps 100 --host-visible-mib $HV --out "$R/evidence/r2_watch/$n" --stop-when-gone > "$R/evidence/r2_watch/$n.console.txt" 2>&1 &
  local WD=$!
  $PY model_lab/run_bench.py --name "$n" --model "$M" --mmproj "$MM" --family qwen --ctx 32768 --ngl 999 --paths fast \
    --suites F,D,DG,C,H,S,O,R,RH,L,P,V --l-sizes 4000,12000,28000 --port 18481 --extra "$X" > "$R/evidence/r2_suite_${n}_console.txt" 2>&1
  echo "run_bench rc=$? $(date -u +%H:%M:%SZ)"; grep -E "^EVIDENCE|Error|Traceback" "$R/evidence/r2_suite_${n}_console.txt" | tail -3
  wait $WD
  tail -c 300 "$R/evidence/r2_watch/$n.console.txt"; echo
  unset GGML_VK_SUBALLOCATION_BLOCK_SIZE
}

echo "=== R2 suites start $(date -u +%H:%M:%SZ) which=$WHICH"
guard 120
if [ "$WHICH" = all ] || [ "$WHICH" = idle128 ]; then run_suite r2S_sub128_idle 1 2500; fi
if [ "$WHICH" = all ] || [ "$WHICH" = pressure128 ] || [ "$WHICH" = pressuredef ]; then
  consumer_on
  if [ "$WHICH" != pressuredef ]; then run_suite r2S_sub128_pressure 1 3500; fi
  if [ "$WHICH" != pressure128 ]; then run_suite r2S_default_pressure 0 3500; fi
  consumer_off
fi
case "$WHICH" in
  prof_*)   # prof_<profile>: planner profile next to the consumer, default blocks
    consumer_on
    run_suite "r2S_${WHICH#prof_}_pressure" 0 3500 "${WHICH#prof_}"
    consumer_off ;;
esac
echo "=== R2SUITES_DONE $(date -u +%H:%M:%SZ) VRAM $(vram) MiB"
