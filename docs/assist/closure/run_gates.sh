#!/bin/bash
# Usage: run_gates.sh <worktree> <label>   -> writes <worktree>/docs/assist/closure/evidence/gates_<label>.txt
set -u
WT="$1"; LABEL="$2"
OUT="$WT/docs/assist/closure/evidence"; mkdir -p "$OUT"
PY=/tmp/claude-0/venv/bin/python
export PATH=/tmp/claude-0/flutter/bin:$PATH
cd "$WT" || exit 2
{
  date -u +%FT%TZ; git rev-parse HEAD; git status --porcelain | head
  echo "== combined python (ws oi a2ui web assist)"
  $PY -m pytest -c scripts/phase2d_pytest.ini --rootdir=. tests/ws tests/oi tests/a2ui tests/web tests/assist -q 2>&1 | grep -E "^(FAILED|ERROR) |passed|failed" | sort
  echo "== web+assist"
  $PY -m pytest -c scripts/phase2d_pytest.ini --rootdir=. tests/web tests/assist -q 2>&1 | tail -3
  echo "== frozen check"
  $PY scripts/ws_frozen_check.py 2>&1 | tail -15
  echo "== flutter test"
  (cd uri_ui && flutter test 2>&1 | tail -4)
} > "$OUT/gates_$LABEL.txt" 2>&1
echo "$OUT/gates_$LABEL.txt"
