#!/bin/bash
# Self-built stock vs URI-extension build (fine checkpoints + rs-seq n-gram) on the URI workload; verbose
# checkpoint trace with the release binary. Waits for run_stream.sh (ALL_DONE10).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT10="$1"
if [ -n "$OUT10" ]; then until grep -q ALL_DONE10 "$OUT10" 2>/dev/null; do sleep 30; done; fi
ST=D:/uri-model-lab/build/stock/bin/llama-server.exe
UX=D:/uri-model-lab/build/rsseq/bin/llama-server.exe
echo "=== verbose checkpoint trace (release binary)"; $PY model_lab/uri_engine/diag_ckpt.py 2>&1 | grep -v print_timing | tail -60
run() { name=$1; shift; echo "=== $name: $*"; $PY model_lab/uri_engine/bench_uri.py --name "$name" --skip long,vision,decode "$@" 2>&1 | tail -3; }
FINE="-b 1024 -ub 1024 --cache-ram 1024 --checkpoint-min-step 512 --ctx-checkpoints 16"
PROD="-b 2048 -ub 1024 --cache-ram 1024"
if [ -f "$ST" ]; then
  run sb_prod_canon   --binary $ST --serial canonical --extra "$PROD"
  run sb_fine_stable  --binary $ST --serial stable --extra "$FINE"
fi
if [ -f "$UX" ]; then
  run ux_prod_canon   --binary $UX --serial canonical --extra "$PROD"
  run ux_fine_stable  --binary $UX --serial stable --extra "$FINE"
  run ux_fine_canon   --binary $UX --serial canonical --extra "$FINE"
  run ux_fine_stable_ngram --binary $UX --serial stable --extra "$FINE --spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-draft-n-max 8"
fi
$PY model_lab/uri_engine/compare_runs.py --names ckpt_fine sb_prod_canon sb_fine_stable ux_prod_canon ux_fine_stable ux_fine_canon ux_fine_stable_ngram 2>&1 | cut -c1-260
echo ALL_DONE11
