#!/usr/bin/env bash
# Chain 4: coexistence of the Vision profiles, and repeats (n=2) of the two candidate defaults.
cd "$(dirname "$0")" || exit 1
Y=D:/uri-dev/uri-vram-r1-yield
step() { if [ -e $Y ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "##### $* $(date +%H:%M:%S)"; "$@" 2>&1 | grep -vE '^\s*$' | tail -6; }
step timeout 900 python -I coexist.py co-c64k-vis --ctx 65536 --no-mtp --vision gpu
step timeout 900 python -I coexist.py co-c32k-vis --ctx 32768 --no-mtp --vision gpu
step timeout 900 python -I coexist.py co-c64k-mtpoff-r2 --ctx 65536 --no-mtp
step timeout 900 python -I coexist.py co-c32k-mtpon-r2 --ctx 32768
step timeout 900 python -I coexist.py co-c128k-mtpoff --ctx 131072 --no-mtp
echo "##### chain4 done $(date +%H:%M:%S)"
