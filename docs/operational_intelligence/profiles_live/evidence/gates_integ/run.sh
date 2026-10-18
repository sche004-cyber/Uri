#!/usr/bin/env bash
# Regression gates for the integration candidate vs canonical 348677b7 (same interpreter, same suites).
PY=D:/uri-dev/uri-profiles-live/runtime-e/.venv/Scripts/python.exe
OUT=D:/uri-dev/uri-profiles-live/evidence/gates-integ
SUITES="tests/ws tests/oi tests/ssrf tests/web tests/a2ui tests/assist tests/office/test_worker_isolation.py tests/governance tests/dev_workflow"
for pair in "cand:D:/uri-dev/uri-runtime-profiles-integ" "canon:D:/uri-dev/uri-canon-348677b7"; do
  name=${pair%%:*}; dir=${pair#*:}
  echo "== $name $(git -C $dir rev-parse HEAD) $(date +%H:%M:%S)"
  (cd $dir && timeout 5400 $PY -B -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q -p no:cacheprovider \
     --junitxml=$OUT/$name.xml $SUITES > $OUT/$name.log 2>&1; echo "rc=$?" >> $OUT/$name.log)
  tail -2 $OUT/$name.log
  git -C $dir status --porcelain | head -5
done
echo "gates done $(date +%H:%M:%S)"
