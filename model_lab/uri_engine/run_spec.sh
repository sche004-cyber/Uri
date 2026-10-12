#!/bin/bash
# Speculative decoding runs (GPU exclusive) after run_variants2.sh (ALL_DONE2 marker), then imatrix expert stats.
# $1 = output file of run_variants2.sh to wait on; $2 = optional file to append ALL_DONE3 to (releases run_variants3.sh).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT2="$1"; REL="$2"
if [ -n "$OUT2" ]; then until grep -q ALL_DONE2 "$OUT2" 2>/dev/null; do sleep 30; done; fi
S="model_lab/uri_engine/bench_spec.py"
BASE="-b 2048 -ub 1024 --cache-ram 1024"
MTP="D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
run() { name=$1; shift; echo "=== $name: $*"; $PY $S --name "$name" "$@" 2>&1 | tail -12; }
run spec_off        --extra "$BASE"
run ngram_mod       --extra "$BASE --spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64"
run ngram_simple8   --extra "$BASE --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 8 --spec-draft-n-max 8"
run ngram_mapk8     --extra "$BASE --spec-type ngram-map-k --spec-ngram-map-k-size-n 12 --spec-ngram-map-k-size-m 8 --spec-draft-n-max 8"
run mtp3_16k_vision --ctx 16384 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU"
run spec_off_16k_vision --ctx 16384 --extra "$BASE"
run mtp3_32k_novis  --no-mmproj --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU"
run mtp2_32k_novis  --no-mmproj --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
run spec_off_32k_novis --no-mmproj --extra "$BASE"
$PY $S --compare spec_off ngram_mod ngram_simple8 ngram_mapk8 2>&1 | tail -40
$PY $S --compare spec_off_16k_vision mtp3_16k_vision 2>&1 | tail -20
$PY $S --compare spec_off_32k_novis mtp3_32k_novis mtp2_32k_novis 2>&1 | tail -30
echo "=== imatrix expert stats"
IM=/d/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64/llama-imatrix.exe
M="D:/uri-model-lab/models/unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ3_S.gguf"
$IM -m "$M" -f D:/uri-model-lab/uri_engine/corpus_uri.txt -o D:/uri-model-lab/uri_engine/imatrix_uri.gguf -ngl 999 -c 2048 -b 2048 -ub 1024 -fa on --no-ppl --parse-special 2>&1 | tail -5
$IM -m "$M" -f D:/uri-model-lab/uri_engine/corpus_generic.txt -o D:/uri-model-lab/uri_engine/imatrix_generic.gguf -ngl 999 -c 2048 -b 2048 -ub 1024 -fa on --no-ppl 2>&1 | tail -5
$PY model_lab/uri_engine/expert_stats.py D:/uri-model-lab/uri_engine/imatrix_uri.gguf uri 2>&1 | tail -15
$PY model_lab/uri_engine/expert_stats.py D:/uri-model-lab/uri_engine/imatrix_generic.gguf generic 2>&1 | tail -15
echo ALL_DONE3
if [ -n "$REL" ]; then echo ALL_DONE3 >> "$REL"; fi
