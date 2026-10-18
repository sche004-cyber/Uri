#!/usr/bin/env bash
# Chain 10 (2026-10-18): the bound live set on the integration-ready candidate f3d5eb29 (canonical 348677b7 merged),
# runtime-e / installation rp-e. Every harness refuses to run without a clean source binding (tools/binding.py).
# One queue; the yield file stops it before the next step.
cd /d/uri-dev/uri-profiles-live || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
PY=runtime-e/.venv/Scripts/python.exe
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | tail -12; }
step bash tools/go.sh e-p2-main main v2 65536,off,0 --fresh-prefs
step bash tools/go.sh e-p2-ret returning v2 65536,off,0
step bash tools/go.sh e-p3-main main v2 32768,gpu,0 --fresh-prefs
step bash tools/go.sh e-p3-ret returning v2 32768,gpu,0
step timeout 1800 $PY -B -I tools/switch_live.py sw5
step timeout 1500 $PY -B -I tools/assist_vision_app.py assist-p3-e --profile 32768,gpu,0 --reps 3
step timeout 5400 $PY -B -I tools/soak.py soak-p3-e --profile 32768,gpu,0 --minutes 60
echo "##### chain10 done $(date +%H:%M:%S)"
