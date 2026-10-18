#!/usr/bin/env bash
# Chain 6: suite P (Phase 1 production-adapter loop). It runs only from a checkout at the frozen Phase 1 baseline
# e8e3b652 (runtime_identity.BASELINE): own detached worktree D:/uri-dev/uri-vram-r1-p1 with the identical model_lab
# harness copied in (as the 2026-10-06 baseline run had it, untracked) and its own .venv.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | grep -vE '^\s*$' | tail -6; }
P1=D:/uri-dev/uri-vram-r1-p1
step timeout 1500 python -I with_profile.py --name p-frozen --ctx 32768 --vision gpu --cwd $P1 -- $P1/.venv/Scripts/python.exe -I $P1/model_lab/run_bench.py --name vr1_p_frozen --url {URL} --suites P
step timeout 1500 python -I with_profile.py --name p-c64k-mtpoff --ctx 65536 --no-mtp --cwd $P1 -- $P1/.venv/Scripts/python.exe -I $P1/model_lab/run_bench.py --name vr1_p_c64k_mtpoff --url {URL} --suites P
step timeout 1500 python -I with_profile.py --name p-c64k-mtpon --ctx 65536 --cwd $P1 -- $P1/.venv/Scripts/python.exe -I $P1/model_lab/run_bench.py --name vr1_p_c64k_mtpon --url {URL} --suites P
echo "##### chain6 done $(date +%H:%M:%S)"
