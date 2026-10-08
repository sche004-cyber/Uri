#!/usr/bin/env bash
# R2 remaining chain, unattended, each step behind the GPU-owner + host-CPU guard:
#  1. rerun of the planner-profile validation next to the consumer (first run confounded by a CPU-saturating render)
#  2. late-pressure tests (Brain first, consumer later)
#  3. NVMe vs HDD loads
#  4. regression suites: 128 MiB idle, 128 MiB pressure, default pressure, vision_cpu_no_mtp pressure
set -u
cd "$(dirname "$0")/.."
PY=/c/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe
guard() { $PY r2/gpu_guard.py --min-mib 1500 --allow ollama --timeout -1 --interval 20 --quiet-s "${1:-0}" --block-cmd uri_operational_intelligence.host --max-cpu 30 --json; }
S128="--env GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728"
echo "=== R2 chain start $(date -u +%H:%M:%SZ)"
PFX=r2W bash r2/run_r2_profiles.sh pressure
for v in "r2L_full_default_r1:" "r2L_full_sub128_r1:$S128" "r2L_full_default_r2:" "r2L_full_sub128_r2:$S128" \
         "r2L_vision_cpu_r1:--extra=--no-mmproj-offload" "r2L_vision_cpu_r2:--extra=--no-mmproj-offload"; do
  n=${v%%:*}; a=${v#*:}
  guard 60 > /dev/null
  echo "=== $n $(date -u +%H:%M:%SZ)"
  $PY r2/residency_watchdog.py --port 18497 --seconds 900 --interval 5 --expected-tps 110 --out "evidence/r2_watch/$n" --stop-when-gone > "evidence/r2_watch/$n.console.txt" 2>&1 &
  WD=$!
  $PY r2/late_pressure.py --name "$n" $a 2>&1 | grep -E "R2LATE|FATAL"
  wait $WD
done
bash r2/run_r2_nvme.sh
bash r2/run_r2_suites.sh all
bash r2/run_r2_suites.sh prof_vision_cpu_no_mtp
echo "=== R2CHAIN_DONE $(date -u +%H:%M:%SZ)"
