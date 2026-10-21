#!/usr/bin/env bash
# UI-CONTROLS-TYPO-20261018 gates on the current HEAD of the candidate worktree. Usage: gates.sh <outdir>
set -u
W=/d/uri-dev/uri-ui-controls-typo
O=$1
mkdir -p "$O"
cd $W
HEAD=$(git rev-parse HEAD)
hdr() { echo "HEAD $HEAD"; echo "STATUS_PORCELAIN_BEGIN"; git status --porcelain --untracked-files=no; echo "STATUS_PORCELAIN_END"; echo "START $(date -Is)"; }
{ hdr; timeout 2400 python -m pytest -q tests/oi tests/ws -p no:cacheprovider; echo "EXIT $?"; echo "END $(date -Is)"; } > "$O/pytest_oi_ws.log" 2>&1
{ hdr; timeout 1200 python scripts/ws_frozen_check.py; echo "EXIT $?"; echo "END $(date -Is)"; } > "$O/ws_frozen_check.log" 2>&1
cd $W/uri_ui
{ hdr; timeout 600 flutter analyze; echo "EXIT $?"; echo "END $(date -Is)"; } > "$O/flutter_analyze.log" 2>&1
{ hdr; timeout 3000 flutter test --no-pub; echo "EXIT $?"; echo "END $(date -Is)"; } > "$O/flutter_test.log" 2>&1
git -C $W checkout -- .tmp_m26_render/rebuilt_dashboard.png 2>/dev/null
{ hdr; timeout 2400 flutter build windows --release --no-pub; echo "EXIT $?"; echo "END $(date -Is)"; } > "$O/flutter_build_windows_release.log" 2>&1
echo "ALL_DONE $(date -Is)" > "$O/DONE"
