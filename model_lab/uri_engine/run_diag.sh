#!/bin/bash
# After variants3 (ALL_DONE4): checkpoint diagnostics with verbose logs, then self-built stock vs rs-seq patched
# llama-server speculative runs (CPU builds first).
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
OUT4="$1"
if [ -n "$OUT4" ]; then until grep -q ALL_DONE4 "$OUT4" 2>/dev/null; do sleep 30; done; fi
echo "=== checkpoint diagnostics"
$PY model_lab/uri_engine/diag_ckpt.py 2>&1 | tail -60
echo "=== build stock"
powershell -NoProfile -ExecutionPolicy Bypass -File model_lab/uri_engine/build_vulkan.ps1 -Name stock 2>&1 | tail -8
echo "=== build rsseq"
powershell -NoProfile -ExecutionPolicy Bypass -File model_lab/uri_engine/build_vulkan.ps1 -Name rsseq -Source D:/uri-model-lab/strata_research/llamacpp-rsseq 2>&1 | tail -8
S="model_lab/uri_engine/bench_spec.py"
BASE="-b 2048 -ub 1024 --cache-ram 1024"
ST=D:/uri-model-lab/build/stock/bin/llama-server.exe
RS=D:/uri-model-lab/build/rsseq/bin/llama-server.exe
run() { name=$1; shift; echo "=== $name: $*"; $PY $S --name "$name" "$@" 2>&1 | tail -12; }
if [ -f "$ST" ]; then
  run sb_spec_off      --binary $ST --extra "$BASE"
  run sb_ngram_simple8 --binary $ST --extra "$BASE --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 8 --spec-draft-n-max 8"
fi
if [ -f "$RS" ]; then
  run rs_ngram_simple8 --binary $RS --extra "$BASE --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 8 --spec-draft-n-max 8"
  run rs_ngram_simple4 --binary $RS --extra "$BASE --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 4 --spec-draft-n-max 4"
  run rs_ngram_mod8    --binary $RS --extra "$BASE --spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-draft-n-max 8"
  $PY $S --compare sb_spec_off sb_ngram_simple8 rs_ngram_simple8 rs_ngram_simple4 rs_ngram_mod8 2>&1 | tail -60
fi
echo ALL_DONE5
