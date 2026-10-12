#!/bin/bash
# VRAM fit tests for MTP next to vision at larger contexts, and MTP with n_max 2. Waits for correctness2 (ALL_DONE8).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT8="$1"
if [ -n "$OUT8" ]; then until grep -q ALL_DONE8 "$OUT8" 2>/dev/null; do sleep 30; done; fi
S="model_lab/uri_engine/bench_spec.py"
BASE="-b 2048 -ub 1024 --cache-ram 1024"
MTP="D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
run() { name=$1; shift; echo "=== $name: $*"; $PY $S --name "$name" --repeats 1 "$@" 2>&1 | tail -10; }
run mtp2_32k_vision --ctx 32768 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
run mtp3_24k_vision --ctx 24576 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU"
run mtp2_16k_vision --ctx 16384 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
run mtp4_16k_vision --ctx 16384 --extra "$BASE -md $MTP --spec-type draft-mtp --spec-draft-n-max 4 -otd token_embd.weight=CPU"
for n in mtp2_32k_vision mtp3_24k_vision mtp2_16k_vision mtp4_16k_vision; do
  f=model_lab/evidence/uri_engine/spec/$n.json; [ -f "$f" ] && $PY -c "import json;v=json.load(open('$f'));print('$n', v['resources'].get('peak_vram_dedicated_mib'), v['resources'].get('peak_server_rss_mib'), [round(r['gen_tps'] or 0) for r in v['rows']])" || echo "$n: no result (did not start/fit)"
  grep -i -E "failed to allocate|out of memory|ErrorOutOfDeviceMemory|abort" model_lab/evidence/uri_engine/spec/logs/server_$n.log 2>/dev/null | head -2
done
echo ALL_DONE9
