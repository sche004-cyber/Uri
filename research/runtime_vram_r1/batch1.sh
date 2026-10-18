#!/usr/bin/env bash
# Batch 1 of URI-RUNTIME-VRAM-R1 profile probes (one load per profile, lease per load, sequential).
cd "$(dirname "$0")" || exit 1
run() { echo "=== $1 $(date +%H:%M:%S)"; timeout 590 python -I run_probe.py "$@" 2>&1 | tail -3; }
run frozen-exact --ctx 32768 --vision gpu --expected-mib 15626
run p64-nomtp-novis --ctx 65536 --no-mtp --vision off --expected-mib 13660
run p64-mtp-viscpu --ctx 65536 --vision cpu --expected-mib 15045
run p64-nomtp-visgpu --ctx 65536 --no-mtp --vision gpu --expected-mib 14770
run p128-nomtp-novis --ctx 131072 --no-mtp --vision off --expected-mib 14470
run p16-mtp-novis --ctx 16384 --vision off --expected-mib 14270
run p64-mtp-novis-dkvq8 --ctx 65536 --vision off --draft-kv q8_0 --expected-mib 14980
run p32-mtp-visgpu-rep --ctx 32768 --vision gpu --expected-mib 15626
echo "=== done $(date +%H:%M:%S)"
