#!/bin/bash
# Correctness/regression: full qualification suites (run_bench.py, real Core seams) for the production flags
# and for each candidate line in candidates.txt ("name|extra flags|binary-or-empty"), then case-by-case diffs.
# $1 = output file to wait on for ALL_DONE5 (run_diag.sh).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT5="$1"
if [ -n "$OUT5" ]; then until grep -q ALL_DONE5 "$OUT5" 2>/dev/null; do sleep 30; done; fi
M="D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ3_S.gguf"
MM="D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/mmproj-F16.gguf"
SUITES="F,D,DG,C,H,S,O,L,P"
run() { name=$1; extra=$2; bin=$3; echo "=== $name: $extra $bin"
  if [ -n "$bin" ]; then export URI_LAB_BINARY="$bin"; fi
  $PY model_lab/run_bench.py --name "ue_$name" --model "$M" --mmproj "$MM" --family qwen --ctx 32768 --ngl 999 --paths fast \
      --suites "$SUITES" --l-sizes 4000,16000,29000 --extra "$extra" --port 18481 2>&1 | tail -5
  unset URI_LAB_BINARY; }
run base "-b 2048 -ub 1024 --cache-ram 1024" ""
while IFS='|' read -r name extra bin; do
  [ -z "$name" ] && continue; case "$name" in \#*) continue;; esac
  run "$name" "$extra" "$bin"
done < model_lab/uri_engine/candidates.txt
BASE=$(ls -td model_lab/evidence/runs/ue_base/*/ | head -1)
for d in model_lab/evidence/runs/ue_*/; do
  n=$(basename "$d"); [ "$n" = "ue_base" ] && continue
  last=$(ls -td "$d"*/ | head -1)
  echo "=== diff base vs $n"; $PY model_lab/uri_engine/diff_outputs.py "$BASE/results.jsonl" "$last/results.jsonl" "$n" 2>&1 | tail -20
done
echo ALL_DONE6
