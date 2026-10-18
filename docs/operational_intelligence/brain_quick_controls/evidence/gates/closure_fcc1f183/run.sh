#!/usr/bin/env bash
OUT=D:/uri-dev/qc-closure-live/gates
PY=D:/uri-dev/uri-profiles-live/runtime-e/.venv/Scripts/python.exe
cd D:/uri-dev/uri-brain-qc-closure || exit 1
H=$(git rev-parse HEAD); echo "HEAD=$H" > $OUT/head.txt
(echo "HEAD=$H"; timeout 3600 $PY -B -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q -p no:cacheprovider tests/oi tests/ws; echo rc=$?) > $OUT/pytest_oi_ws.log 2>&1
(cd uri_ui && echo "HEAD=$H" && timeout 3600 flutter test; echo rc=$?) > $OUT/flutter_test.log 2>&1
git status --porcelain > $OUT/porcelain_after.txt
echo "gates done $(date +%H:%M:%S)" >> $OUT/head.txt
