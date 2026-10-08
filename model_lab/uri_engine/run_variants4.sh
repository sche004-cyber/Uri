#!/bin/bash
# URI-workload (bench_uri) under speculative decoding: distinct decision turns, so n-gram pools learn only
# cross-turn structure, not identical outputs. Waits for correctness.sh (ALL_DONE6).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT6="$1"
if [ -n "$OUT6" ]; then until grep -q ALL_DONE6 "$OUT6" 2>/dev/null; do sleep 30; done; fi
BASE="-b 2048 -ub 1024 --cache-ram 1024"
MTP="D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
run() { name=$1; shift; echo "=== $name: $*"; $PY model_lab/uri_engine/bench_uri.py --name "$name" --skip long,vision "$@" 2>&1 | tail -3; }
run uri_ngram_mod    --extra "$BASE --spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64"
run uri_ngram_mod16  --extra "$BASE --spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 8 --spec-ngram-mod-n-max 16"
run uri_ngram_simple --extra "$BASE --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 8 --spec-draft-n-max 8"
run uri_mtp3_16k     --ctx 16384 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU"
run uri_base_16k     --ctx 16384 --extra "$BASE"
echo ALL_DONE7
