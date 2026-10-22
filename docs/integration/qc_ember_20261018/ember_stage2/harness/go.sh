#!/usr/bin/env bash
# BRAIN-QC live chain: one session host + one UI runner per run. The session waits for the announced window
# (--not-before) and a FREE GPU lease; the production Brain host then takes the lease itself (no override).
# Usage: go.sh <label> <qc|uiv2|dry> [not-before HH:MM]
H=/d/uri-dev/uri-integ-live/combined/harness
RT=/d/uri-dev/uri-integ-rt-e
PY=$RT/.venv/Scripts/python.exe
SYS=/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe
L=$1; K=$2; NB=$3
OUT=$H/../live/$L
mkdir -p $OUT
SA="--minutes 45"; [ -n "$HOST_PROFILE" ] && SA="$SA --profile $HOST_PROFILE"; [ -n "$NB" ] && SA="$SA --not-before $NB"; [ "$K" = dry ] && SA="$SA --no-brain"
$PY -B -I $H/qc_session.py $L $SA > $OUT/session.out 2> $OUT/session.err &
SP=$!
UA="--ui-first"; [ "$K" = uiv2 ] && UA="--driver uiv2 --mode main --fresh-prefs"; [ "$K" = dry ] && UA="--dry"
[ "$K" = ember ] && UA="--ui-first --driver ember"
PP=""; if [ "$K" = ember ]; then $SYS -B -I $H/win_probe.py $L > $OUT/probe.out 2> $OUT/probe.err & PP=$!; fi
$SYS -B -I $H/run_qc_ui.py $L $UA > $OUT/ui.out 2> $OUT/ui.err
wait $SP
[ -n "$PP" ] && kill $PP 2>/dev/null
echo "DONE $L $(date +%T)" >> $OUT/go.log
