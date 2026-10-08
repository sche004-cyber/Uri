#!/usr/bin/env bash
# Frame-timing evidence for UI_TEST_EVIDENCE.md.
# Runs the living preview in a PROFILE build (flutter run --profile) for
# ~70 s per scenario with URI_LIVING_PERF=1, which makes lib/living/perf_logger.dart
# print one "[perf] ..." summary every 5 s; the logs land in docs/ui_phase/perf/.
# "q" is piped to flutter run after the sampling window so it exits cleanly.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
UI="$HERE/../../../uri_ui"
OUT="$HERE/../perf"
mkdir -p "$OUT"
cd "$UI"

run_scenario() {
  local name="$1"; shift
  echo "=== $name"
  (sleep "${SAMPLE_SECONDS:-70}"; echo q) | env "$@" URI_LIVING_PERF=1 URI_LIVING_SKIP_ONBOARDING=1 \
    flutter run --profile -d windows -t lib/main_living.dart 2>&1 \
    | grep -E "\[perf\]|Impeller|rror|Exception" > "$OUT/$name.log"
  tail -n 12 "$OUT/$name.log"
}

# The first scenario includes the profile compile; give it longer.
SAMPLE_SECONDS=${SAMPLE_SECONDS:-70}
run_scenario companion_idle_profile URI_LIVING_START_MODE=companion
run_scenario dashboard_profile URI_LIVING_START_MODE=dashboard
run_scenario companion_reduced_profile URI_LIVING_START_MODE=companion URI_LIVING_REDUCED_EFFECTS=1
run_scenario companion_working_profile URI_LIVING_START_MODE=companion URI_LIVING_DEMO_STATE=working
run_scenario orb_swarm_profile URI_LIVING_START_MODE=companion URI_LIVING_ORB_VARIANT=swarm
run_scenario orb_mesh_profile URI_LIVING_START_MODE=companion URI_LIVING_ORB_VARIANT=mesh
run_scenario orb_flow_profile URI_LIVING_START_MODE=companion URI_LIVING_ORB_VARIANT=flow
run_scenario orb_glass_profile URI_LIVING_START_MODE=companion URI_LIVING_ORB_VARIANT=glass
echo DONE
