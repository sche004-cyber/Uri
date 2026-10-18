#!/usr/bin/env bash
# Chain 7 (audit REVISE repair, 2026-10-17): accuracy reruns WITHOUT suite P, from the repo root, so each run ends
# rc=0 with summary.json; then the 64K main-only long-context rerun with classification. One queue, yield checked.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | grep -vE '^\s*$' | tail -4; }
R=D:/uri-dev/uri-runtime-vram-r1/model_lab/run_bench.py
V=D:/uri-dev/uri-runtime-vram-r1/.venv/Scripts/python.exe
ALL=D,DG,F,C,H,S,O,R,RH,L
step timeout 1800 python -I with_profile.py --name r2-ctl-frozen-dg --ctx 32768 --vision gpu -- $V -I $R --name vr1r2_ctl_frozen_dg --url {URL} --suites D,DG
step timeout 2400 python -I with_profile.py --name r2-c64k-mtpoff --ctx 65536 --no-mtp -- $V -I $R --name vr1r2_c64k_mtpoff --url {URL} --suites $ALL --l-sizes 4000,12000,28000
step timeout 2400 python -I with_profile.py --name r2-c64k-mtpon --ctx 65536 -- $V -I $R --name vr1r2_c64k_mtpon --url {URL} --suites $ALL --l-sizes 4000,12000,28000
step timeout 1500 python -I run_longctx.py --model q36 --sizes 65536:q8_0 --label r2-lc-mtpoff
echo "##### chain7 done $(date +%H:%M:%S)"
