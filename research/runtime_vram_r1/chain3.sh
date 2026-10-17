#!/usr/bin/env bash
# Chain 3: coexistence (URI UI + Chrome), URI suites on candidate profiles, long-context fill at 64K.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | grep -vE '^\s*$' | tail -12; }
R=../../model_lab/run_bench.py
SUITES=F,D,DG,C,H,S,O,R,RH,L,P
step timeout 900 python -I coexist.py co-c64k-mtpoff --ctx 65536 --no-mtp
step timeout 900 python -I coexist.py co-c64k-mtpon --ctx 65536
step timeout 900 python -I coexist.py co-c32k-mtpon --ctx 32768
step timeout 900 python -I coexist.py co-frozen --ctx 32768 --vision gpu
step timeout 1800 python -I with_profile.py --name suite-c64k-mtpoff --ctx 65536 --no-mtp -- python -I $R --name vr1_c64k_mtpoff --url {URL} --suites $SUITES --l-sizes 4000,12000,28000
step timeout 1800 python -I with_profile.py --name suite-c64k-mtpon --ctx 65536 -- python -I $R --name vr1_c64k_mtpon --url {URL} --suites $SUITES --l-sizes 4000,12000,28000
step timeout 1200 python -I with_profile.py --name suite-c64k-vis --ctx 65536 --no-mtp --vision gpu -- python -I $R --name vr1_c64k_vis --url {URL} --suites V
step timeout 1500 python -I run_longctx.py --model q36 --sizes 65536:q8_0 --label lc-mtpoff
step timeout 1500 python -I run_longctx.py --model q36 --sizes 65536:q8_0 --mtp --label lc-mtpon
echo "##### chain3 done $(date +%H:%M:%S)"
