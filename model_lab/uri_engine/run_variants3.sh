#!/bin/bash
# Third GPU batch: CPU-expert offload, flash-attn/KV-type, grammar cost, request overhead, cold-load tests.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
OUT3="$1"
if [ -n "$OUT3" ]; then until grep -q ALL_DONE3 "$OUT3" 2>/dev/null; do sleep 30; done; fi
L="4000,16000,29000"
run() { name=$1; shift; echo "=== $name: $*"; $PY model_lab/uri_engine/bench_uri.py --name "$name" --long "$L" --skip long,vision "$@" 2>&1 | tail -3; }
run ncmoe4      --extra "-b 2048 -ub 1024 --cache-ram 1024 --n-cpu-moe 4"
run kv_f16      --extra "-b 2048 -ub 1024 --cache-ram 1024 -ctk f16 -ctv f16"
run nogrammar   --no-grammar --extra "-b 2048 -ub 1024 --cache-ram 1024"
echo "=== overhead"; $PY model_lab/uri_engine/overhead.py 2>&1 | tail -60
echo "=== coldload hdd"; $PY model_lab/uri_engine/coldload.py --label hdd --model "D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ3_S.gguf" --mmproj "D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/mmproj-F16.gguf" 2>&1 | tail -30
echo "=== coldload nvme"; $PY model_lab/uri_engine/coldload.py --label nvme --model "C:/uri-model-lab-nvme/models/Qwen3.6-35B-A3B-UD-IQ3_S.gguf" --mmproj "C:/uri-model-lab-nvme/models/mmproj-F16.gguf" 2>&1 | tail -30
echo ALL_DONE4
