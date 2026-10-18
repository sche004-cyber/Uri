#!/usr/bin/env bash
# Chain 5 (owner resume 2026-10-17): same-environment control and the D/DG/P rerun with the harness run from the repo
# root (CWD-1), then the live Brain host --profile check. One queue, yield file checked before every step.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | grep -vE '^\s*$' | tail -6; }
R=D:/uri-dev/uri-runtime-vram-r1/model_lab/run_bench.py
V=D:/uri-dev/uri-runtime-vram-r1/.venv/Scripts/python.exe
step timeout 1800 python -I with_profile.py --name ctl-frozen-dgp --ctx 32768 --vision gpu -- $V -I $R --name vr1_ctl_frozen_dgp --url {URL} --suites D,DG,P
step timeout 1800 python -I with_profile.py --name dgp-c64k-mtpoff --ctx 65536 --no-mtp -- $V -I $R --name vr1_c64k_mtpoff_dgp --url {URL} --suites D,DG,P
step timeout 1800 python -I with_profile.py --name dgp-c64k-mtpon --ctx 65536 -- $V -I $R --name vr1_c64k_mtpon_dgp --url {URL} --suites D,DG,P
step timeout 1500 python -I host_live.py --profile 65536,off,0
echo "##### chain5 done $(date +%H:%M:%S)"
