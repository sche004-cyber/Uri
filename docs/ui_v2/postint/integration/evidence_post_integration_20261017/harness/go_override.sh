#!/usr/bin/env bash
# One live run: wait for a FREE machine-wide GPU lease (never stop another holder), start the session host (server +
# Brain first), then the native UI driver. Usage: go.sh <label> <mode> <visual> [--fresh-prefs]
R=/c/Users/cheta/Development/uri-ui-v2p-run
L=$1; M=$2; V=$3; F=$4
cd $R
mkdir -p evidence/live/$L
PY=$R/runtime2/.venv/Scripts/python.exe
until $PY -B -c "import sys; sys.path.insert(0, r'C:\Users\cheta\Development\uri-ui-v2p'); from uri_operational_intelligence import gpu_lease as G; sys.exit(0 if G.peek().get('state') == 'FREE' else 1)"; do sleep 30; done
echo "lease free $(date +%T)" > evidence/live/$L/go.log
$PY -B -I tools/live_session.py $L --minutes 60 --override-contention > evidence/live/$L/session.out 2> evidence/live/$L/session.err &
SP=$!
until grep -q server_listening evidence/live/$L/session.out 2>/dev/null; do sleep 2; kill -0 $SP 2>/dev/null || { echo "SESSION EXITED" >> evidence/live/$L/go.log; exit 2; }; done
grep -q '"server_listening": true' evidence/live/$L/session.out || { echo "SERVER NOT LISTENING" >> evidence/live/$L/go.log; wait $SP; exit 3; }
/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe -B -I tools/run_live_ui.py $L $M --visual $V $F > evidence/live/$L/ui.out 2> evidence/live/$L/ui.err
wait $SP
echo "DONE $L $(date +%T)" >> evidence/live/$L/go.log
