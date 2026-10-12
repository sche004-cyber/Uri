#!/bin/bash
# Sequential llama-server flag variants over the URI workload (GPU exclusive). Evidence under evidence/uri_engine/runs.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
L="4000,16000,29000"
run() { name=$1; shift; echo "=== $name: $*"; $PY model_lab/uri_engine/bench_uri.py --name "$name" --long "$L" --extra "$*" 2>&1 | tail -3; }
run no_cache_ram   -b 2048 -ub 1024 --cache-ram 0
run no_ckpt        -b 2048 -ub 1024 --cache-ram 1024 --ctx-checkpoints 0
run ckpt_fine      -b 2048 -ub 1024 --cache-ram 1024 --checkpoint-min-step 1024 --ctx-checkpoints 16
run np3_kvu        -b 2048 -ub 1024 --cache-ram 1024 -np 3 -kvu
run b4096_ub2048   -b 4096 -ub 2048 --cache-ram 1024
echo ALL_DONE
