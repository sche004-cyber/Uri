#!/usr/bin/env bash
# One EMBER-V21-INTEG live run: wait for a FREE machine-wide GPU lease (never stop another holder), start the session
# host (server; Brain after ui-ready), the Win32 probe, then the native UI driver.
# Usage: go.sh <label> <first|returning> [--fresh-prefs] [--no-brain]
R=/d/uri-dev/uri-ember-live
L=$1; M=$2; F=$3; NB=$4
cd $R
mkdir -p evidence/live/$L
PY=/d/uri-dev/uri-ember-rt2/.venv/Scripts/python.exe
SYS=/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe
until $PY -B -c "import sys; sys.path.insert(0, r'D:\uri-dev\uri-ember-v21-integ'); from uri_operational_intelligence import gpu_lease as G; sys.exit(0 if G.peek().get('state') == 'FREE' else 1)"; do sleep 30; done
echo "lease free $(date +%T)" > evidence/live/$L/go.log
$PY -B -I tools/live_session.py $L --minutes 80 $NB > evidence/live/$L/session.out 2> evidence/live/$L/session.err &
SP=$!
until grep -q server_listening evidence/live/$L/session.out 2>/dev/null; do sleep 2; kill -0 $SP 2>/dev/null || { echo "SESSION EXITED" >> evidence/live/$L/go.log; exit 2; }; done
grep -q '"server_listening": true' evidence/live/$L/session.out || { echo "SERVER NOT LISTENING" >> evidence/live/$L/go.log; wait $SP; exit 3; }
$SYS -B -I tools/win_probe.py $L > evidence/live/$L/probe.out 2> evidence/live/$L/probe.err &
PP=$!
$SYS -B -I tools/run_live_ui.py $L $M $F > evidence/live/$L/ui.out 2> evidence/live/$L/ui.err
wait $SP
kill $PP 2>/dev/null
echo "DONE $L $(date +%T)" >> evidence/live/$L/go.log
