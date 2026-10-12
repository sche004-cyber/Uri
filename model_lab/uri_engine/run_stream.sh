#!/bin/bash
# Last in chain: streaming-overhead decomposition after MTP fit tests (ALL_DONE9).
cd /c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent || exit 1
PY=/c/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent/.venv/Scripts/python.exe
OUT9="$1"
if [ -n "$OUT9" ]; then until grep -q ALL_DONE9 "$OUT9" 2>/dev/null; do sleep 30; done; fi
echo "=== stream overhead"; $PY model_lab/uri_engine/stream_overhead.py 2>&1 | tail -25
echo ALL_DONE10
