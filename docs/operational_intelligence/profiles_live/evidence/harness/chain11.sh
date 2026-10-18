#!/usr/bin/env bash
# Chain 11 (2026-10-18): review RPI-R3 finding R3-01 - the bound 60-minute P2 soak that LQ-3 requires.
# Runtime-e (materialized from f3d5eb29); the candidate head may be an evidence-only commit on top (binding.py).
cd /d/uri-dev/uri-profiles-live || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
PY=runtime-e/.venv/Scripts/python.exe
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | tail -12; }
step timeout 5400 $PY -B -I tools/soak.py soak-p2-e --profile 65536,off,0 --minutes 60
echo "##### chain11 done $(date +%H:%M:%S)"
