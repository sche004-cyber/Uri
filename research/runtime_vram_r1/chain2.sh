#!/usr/bin/env bash
# Chain 2: batch2 probes, MTP on/off pairs at 64K and 32K, profile switch test. Yield file checked between steps.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@"; }
step bash batch2.sh
step timeout 1500 python -I mtp_pair.py --ctx 65536 --depth 24000
step timeout 1500 python -I switch_test.py --a ctx=65536,mtp=1,vision=off --b ctx=65536,mtp=0,vision=gpu --depth 20000
echo "##### chain2 done $(date +%H:%M:%S)"
