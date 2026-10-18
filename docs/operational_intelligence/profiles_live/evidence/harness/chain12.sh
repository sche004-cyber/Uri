#!/usr/bin/env bash
# Chain 12 (2026-10-18, integration D1/D3): bound live switch P2 -> P3 -> P2 with conversation continuity on the
# final candidate code c3fc8bbc (runtime-f, installation rp-f), after the D3 SELECTABLE guard.
cd /d/uri-dev/uri-profiles-live || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | tail -12; }
step env URI_LIVE_RT=f timeout 1800 runtime-f/.venv/Scripts/python.exe -B -I tools/switch_live.py sw6
echo "##### chain12 done $(date +%H:%M:%S)"
