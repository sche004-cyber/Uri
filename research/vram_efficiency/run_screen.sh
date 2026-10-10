#!/usr/bin/env bash
# VRAM efficiency screening (research only). Each variant = one load of the pinned Runtime v1 server through the R1
# harness (bench_runtime.py), NVMe model copies, idle desktop, inside ONE machine-wide GPU lease (purpose benchmark).
# Usage: gpu_lease run --purpose benchmark --label "..." -- bash run_screen.sh <variant...>
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
AR="$HERE/../adaptive_runtime"
BIN=D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64
MODELS=C:/Users/cheta/Development/uri-adaptive-lab/models
PY=${PY:-python}
EXP='blk\.40\.ffn_(up|gate|down)_exps\.weight=CPU'
run() {   # name, then bench_runtime args
  local name=$1; shift
  echo "=== $(date -u +%H:%M:%SZ) $name"
  GGML_VK_MEMORY_LOGGER=1 "$PY" "$AR/bench_runtime.py" --name "$name" --binary-dir "$BIN" --model-dir "$MODELS" \
    --decode-rounds 3 --decision-rounds 6 --stability-rounds 0 --skip cancel,stability "$@"
  echo "=== $(date -u +%H:%M:%SZ) $name rc=$?"
}
for v in "$@"; do
  case $v in
    base)        run vS_base ;;
    draftexp)    run vS_draftexp --extra "-otd $EXP" ;;
    draftexpout) run vS_draftexpout --extra "-otd $EXP,output\.weight=CPU" ;;
    ncmoe1)      run vS_ncmoe1_draftexp --extra "-otd $EXP --n-cpu-moe 1" ;;
    kvq4)        run vS_kvq4_draftexp --extra "-otd $EXP -ctk q4_0 -ctv q4_0" ;;
    visioncpu)   run vS_visioncpu_draftexp --extra "-otd $EXP --no-mmproj-offload" ;;
    *) echo "unknown variant $v"; exit 2 ;;
  esac
done
