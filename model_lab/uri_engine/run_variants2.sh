#!/bin/bash
# Serialization / ubatch variants. Waits for run_variants.sh to finish (ALL_DONE marker in its output).
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
L="4000,16000,29000"
OUT1="$1"
if [ -n "$OUT1" ]; then until grep -q ALL_DONE "$OUT1" 2>/dev/null; do sleep 30; done; fi
run() { name=$1; serial=$2; shift 2; echo "=== $name ($serial): $*"; $PY model_lab/uri_engine/bench_uri.py --name "$name" --serial "$serial" --long "$L" --skip long,vision,decode --extra "$*" 2>&1 | tail -3; }
run serial_stable  stable -b 2048 -ub 1024 --cache-ram 1024
run serial_lab     lab    -b 2048 -ub 1024 --cache-ram 1024
run ub512_stable   stable -b 2048 -ub 512 --cache-ram 1024
run ub256_stable   stable -b 2048 -ub 256 --cache-ram 1024
echo ALL_DONE2
