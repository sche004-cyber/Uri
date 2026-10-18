#!/usr/bin/env bash
# BRAIN-QC-CLOSURE live chain on runtime6 (materialized from the closure candidate). Lease-gated; no override.
export URI_QC_RT='D:\uri-dev\qc-closure-live\runtime6'
export URI_QC_RT_POSIX=/d/uri-dev/qc-closure-live/runtime6
H=/d/uri-dev/uri-brain-qc-closure/docs/operational_intelligence/brain_quick_controls/evidence/harness
SYS=/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe
for spec in "$@"; do
  L=${spec%%:*}; K=${spec#*:}
  [ -e /d/uri-dev/qc-closure-live/yield ] && { echo "YIELD $(date +%T)"; exit 0; }
  echo "##### $L $K $(date +%T)"
  bash $H/go.sh $L $K
  $SYS -B -I $H/summarize.py $L 2>&1 | tail -12
done
echo "##### chain done $(date +%T)"
