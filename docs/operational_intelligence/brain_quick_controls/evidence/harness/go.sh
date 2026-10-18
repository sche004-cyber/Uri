#!/usr/bin/env bash
# BRAIN-QC live chain: one session host + one UI runner per run. The session waits for the announced window
# (--not-before) and a FREE GPU lease; the production Brain host then takes the lease itself (no override).
# Usage: go.sh <label> <qc|uiv2|dry> [not-before HH:MM]
H=$(cd "$(dirname "$0")" && pwd)
RT=${URI_QC_RT_POSIX:-/c/Users/cheta/AppData/Local/Temp/claude/brain_qc/runtime4}
PY=$RT/.venv/Scripts/python.exe
SYS=/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe
L=$1; K=$2; NB=$3
OUT=$H/../live/$L
mkdir -p $OUT
SA="--minutes 45"; [ -n "$NB" ] && SA="$SA --not-before $NB"; [ "$K" = dry ] && SA="$SA --no-brain"
$PY -B -I $H/qc_session.py $L $SA > $OUT/session.out 2> $OUT/session.err &
SP=$!
# closure: the Quick Controls journey plus the closure steps (P3 via Draft, Assist vision on P3); required in summary
[ "$K" = closure ] && export URI_QC_CLOSURE=1
UA="--ui-first"; [ "$K" = uiv2 ] && UA="--driver uiv2 --mode main --fresh-prefs"; [ "$K" = dry ] && UA="--dry"
$SYS -B -I $H/run_qc_ui.py $L $UA > $OUT/ui.out 2> $OUT/ui.err
wait $SP
echo "DONE $L $(date +%T)" >> $OUT/go.log
