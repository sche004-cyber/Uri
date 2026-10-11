#!/bin/bash
# Away-mode launcher for the URI lifecycle driver (canonical driver ce1a90c). Usage: lc-launch.sh <config.json>
# Starts `lifecycle run <config>` detached, records the python PID next to the config, prints the PID.
set -euo pipefail
CFG="$1"
case "$CFG" in /home/user/uri-wt/lifecycle-runs/*.json) ;; *) echo "config must be under lifecycle-runs" >&2; exit 2;; esac
[ -f "$CFG" ] || { echo "no such config" >&2; exit 2; }
NAME=$(basename "$CFG" .json)
N=1; while [ -e "/home/user/uri-wt/lifecycle-runs/$NAME.run$N.log" ]; do N=$((N+1)); done
LOG="/home/user/uri-wt/lifecycle-runs/$NAME.run$N.log"
cd /tmp/claude-0/lc-driver-canon
setsid nohup /tmp/claude-0/venv/bin/python -m scripts.dev_workflow.lifecycle run "$CFG" > "$LOG" 2>&1 < /dev/null &
sleep 5
PID=""
for p in $(pgrep -f "lifecycle run $CFG" || true); do [ "$(ps -o comm= -p "$p")" = "python" ] && PID=$p; done
[ -n "$PID" ] || { echo "driver did not start; see $LOG" >&2; tail -20 "$LOG" >&2; exit 1; }
echo "$PID" > "/home/user/uri-wt/lifecycle-runs/$NAME.pid"
echo "started $NAME pid=$PID log=$LOG"
