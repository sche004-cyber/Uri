#!/bin/bash
# Correctness for the MTP candidate (needs ctx 16k to fit beside vision): full suites at 16k with and without MTP.
# $1 = output file to wait on for ALL_DONE7 (run_variants4.sh).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT7="$1"
if [ -n "$OUT7" ]; then until grep -q ALL_DONE7 "$OUT7" 2>/dev/null; do sleep 30; done; fi
M="D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ3_S.gguf"
MM="D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/mmproj-F16.gguf"
MTP="D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
SUITES="F,D,DG,C,H,S,O,L,P"
run() { name=$1; extra=$2; echo "=== $name: $extra"
  $PY model_lab/run_bench.py --name "ue_$name" --model "$M" --mmproj "$MM" --family qwen --ctx 16384 --ngl 999 --paths fast \
      --suites "$SUITES" --l-sizes 4000,12000 --extra "$extra" --port 18481 2>&1 | tail -5; }
run base16k "-b 2048 -ub 1024 --cache-ram 1024"
run mtp3_16k "-b 2048 -ub 1024 --cache-ram 1024 -md $MTP --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU"
B=$(ls -td model_lab/evidence/runs/ue_base16k/*/ | head -1); C=$(ls -td model_lab/evidence/runs/ue_mtp3_16k/*/ | head -1)
echo "=== diff base16k vs mtp3_16k"; $PY model_lab/uri_engine/diff_outputs.py "$B/results.jsonl" "$C/results.jsonl" mtp3_16k 2>&1 | tail -20
# repeat-variance control: base16k run twice -> how much greedy output differs on its own
run base16k_rep "-b 2048 -ub 1024 --cache-ram 1024"
B2=$(ls -td model_lab/evidence/runs/ue_base16k_rep/*/ | head -1)
echo "=== diff base16k vs base16k_rep"; $PY model_lab/uri_engine/diff_outputs.py "$B/results.jsonl" "$B2/results.jsonl" base16k_rep 2>&1 | tail -20
echo ALL_DONE8
