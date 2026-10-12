#!/bin/bash
# bench_spec on self-built stock vs URI-extension (rs-seq rollback for n-gram drafts). Waits ALL_DONE11.
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT11="$1"
if [ -n "$OUT11" ]; then until grep -q ALL_DONE11 "$OUT11" 2>/dev/null; do sleep 30; done; fi
S="model_lab/uri_engine/bench_spec.py"
BASE="-b 2048 -ub 1024 --cache-ram 1024"
ST=D:/uri-model-lab/build/stock/bin/llama-server.exe
UX=D:/uri-model-lab/build/rsseq/bin/llama-server.exe
NG="--spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-draft-n-max 8"
run() { name=$1; shift; echo "=== $name: $*"; $PY $S --name "$name" "$@" 2>&1 | tail -12; }
run sb_spec_off   --binary $ST --extra "$BASE"
run sb_ngram_mod8 --binary $ST --extra "$BASE $NG"
run ux_ngram_mod8 --binary $UX --extra "$BASE $NG"
run ux_ngram_mod64 --binary $UX --extra "$BASE --spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64"
$PY $S --compare sb_spec_off sb_ngram_mod8 ux_ngram_mod8 ux_ngram_mod64 2>&1 | tail -60
for n in sb_spec_off sb_ngram_mod8 ux_ngram_mod8 ux_ngram_mod64; do grep -m1 "n_rs_seq" model_lab/evidence/uri_engine/spec/logs/server_$n.log | sed "s/^/$n: /"; done
echo ALL_DONE12
