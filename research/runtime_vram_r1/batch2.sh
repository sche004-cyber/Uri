#!/usr/bin/env bash
# Batch 2 (owner addition 2026-10-17: mutually exclusive Vision / MTP). Paired MTP on/off at identical context,
# main-only, Vision-only, 128K variants. One load per profile, lease per load, sequential.
cd "$(dirname "$0")" || exit 1
run() { if [ -e D:/uri-dev/uri-vram-r1-yield ]; then echo "YIELD $(date +%H:%M:%S)"; exit 0; fi; echo "=== $1 $(date +%H:%M:%S)"; timeout 590 python -I run_probe.py "$@" 2>&1 | tail -1; }
run p32-nomtp-novis --ctx 32768 --no-mtp --vision off --expected-mib 13400
run p32-nomtp-visgpu --ctx 32768 --no-mtp --vision gpu --expected-mib 14510
run p128-nomtp-visgpu --ctx 131072 --no-mtp --vision gpu --expected-mib 15580
run p128-mtp-novis --ctx 131072 --vision off --expected-mib 16100
run p16-nomtp-novis --ctx 16384 --no-mtp --vision off --expected-mib 13270
echo "=== done $(date +%H:%M:%S)"
