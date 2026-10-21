#!/usr/bin/env bash
# UI-CONTROLS-TYPO live chain (copy of the BRAIN-QC go.sh): one session host + one UI runner per run. The session waits
# for a FREE GPU lease; the production Brain host then takes the lease itself (no override).
# Usage: go.sh <label> <ui|uiv2> [host profile, e.g. 32768,gpu,0]      (ui = the controls/typography driver with one injected failed start of Long)
H=/d/uri-dev/uri-ui-typo-live/harness
RT=/d/uri-dev/uri-ui-typo-live/runtime
PY=$RT/.venv/Scripts/python.exe
SYS=/c/Users/cheta/AppData/Local/Programs/Python/Python313/python.exe
L=$1; K=$2; HP=$3
OUT=$H/../live/$L
mkdir -p $OUT
SA="--minutes 50"; [ -n "$HP" ] && SA="$SA --host-profile $HP"; [ "$K" = ui ] && SA="$SA --inject-fail-once c64k-visoff-mtpoff"
$PY -B -I $H/qc_session.py $L $SA > $OUT/session.out 2> $OUT/session.err &
SP=$!
UA="--ui-first"; [ "$K" = uiv2 ] && UA="--driver uiv2 --mode main --fresh-prefs"
$SYS -B -I $H/run_qc_ui.py $L $UA > $OUT/ui.out 2> $OUT/ui.err
wait $SP
echo "DONE $L $(date +%T)" >> $OUT/go.log
