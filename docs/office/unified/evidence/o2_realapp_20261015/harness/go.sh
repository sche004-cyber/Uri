#!/usr/bin/env bash
# One O2 real-application run: wait until no other URI GPU workload holds the machine-wide lease (another session's
# Brain is never stopped), start the session host, then the native UI driver. Usage: go.sh <run> [--brain] [mode]
W=/c/Users/cheta/Development/uri-o2-live-20261015
RUN=$1; shift
BRAIN=""; if [ "$1" = "--brain" ]; then BRAIN="--brain"; shift; fi
MODE=${1:-main}
cd $W
mkdir -p evidence/live/$RUN
RTPY=runtime/.venv/Scripts/python.exe
until $RTPY -B -c "import sys; sys.path.insert(0, 'candidate'); from uri_operational_intelligence import gpu_lease as G; sys.exit(0 if G.peek().get('state') == 'FREE' else 1)"; do sleep 30; done
echo "lease free $(date +%T)"
python -B harness/make_fixtures.py $RUN > evidence/live/$RUN/fixtures.out 2>&1
$RTPY -B -I harness/o2q_session.py $RUN $BRAIN --minutes 60 > evidence/live/$RUN/session.out 2> evidence/live/$RUN/session.err &
SP=$!
until grep -q server_listening evidence/live/$RUN/session.out 2>/dev/null; do sleep 2; kill -0 $SP 2>/dev/null || { echo "SESSION EXITED"; exit 2; }; done
grep -q '"server_listening": true' evidence/live/$RUN/session.out || { echo "SERVER NOT LISTENING"; wait $SP; exit 3; }
python -B -I harness/run_ui.py $RUN $MODE > evidence/live/$RUN/ui.out 2> evidence/live/$RUN/ui.err
wait $SP
echo "DONE $RUN $(date +%T)" > evidence/live/$RUN/done
