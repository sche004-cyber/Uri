"""M35 URIv1 A2.9-R1 -- frozen scenario harness-conformance rerun.

Writes separate R1 telemetry and embeds reproducibility metadata without
altering the original A2.9 telemetry or log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scratch.m35_a2_9_native_trace_harness import (
    MODEL_MAX_TOKENS,
    MODEL_TEMPERATURE,
    SYSTEM_PROMPT,
    run_scenario,
)
from scratch.m35_a2_9_native_trace_scenarios import A2_9_SCENARIOS


SCRATCH_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SCRATCH_DIR / "m35_a2_9_native_trace_r1_results.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_json(url: str) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return {
                "payload": payload,
                "headers": dict(response.headers.items()),
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return {"status": "UNMEASURED", "detail": str(exc)}


def _metadata(endpoint: str, model: str) -> Dict[str, Any]:
    models_url = endpoint.rsplit("/chat/completions", 1)[0] + "/models"
    source_names = (
        "m35_a2_9_native_trace_world.py",
        "m35_a2_9_native_trace_harness.py",
        "m35_a2_9_native_trace_scenarios.py",
        "m35_a2_9_native_trace_scoring.py",
        "m35_a2_9_r1_run_pilot.py",
        "test_m35_a2_9_native_trace.py",
    )
    original_evidence = (
        "m35_a2_9_native_trace_results.json",
        "m35_a2_9_pilot_run.log",
    )
    return {
        "model_identifier": model,
        "model_artifact": "UNMEASURED: OpenAI-compatible /v1/models exposes no artifact hash or path.",
        "lm_studio_models_endpoint": models_url,
        "lm_studio_models_response": _get_json(models_url),
        "lm_studio_server_version": "UNMEASURED: no version endpoint or identifying version header exposed.",
        "lm_studio_server_config": "UNMEASURED: no server configuration endpoint exposed.",
        "client_generation_config": {
            "temperature": MODEL_TEMPERATURE,
            "max_tokens": MODEL_MAX_TOKENS,
            "response_format": "strict JSON schema depot_action",
            "endpoint": endpoint,
        },
        "seed": "UNMEASURED: no seed was supplied or exposed by the endpoint.",
        "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "source_sha256": {name: _sha256(SCRATCH_DIR / name) for name in source_names},
        "original_evidence_sha256": {name: _sha256(SCRATCH_DIR / name) for name in original_evidence},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="M35 URIv1 A2.9-R1 frozen scenario conformance rerun")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.5-9b")
    parser.add_argument("--step-cap", type=int, default=10)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()

    scenario_results = []
    all_events = []
    total_prompt_tokens = total_completion_tokens = total_calls = 0
    total_latency_ms = total_wall_clock = 0.0

    print(f"M35 A2.9-R1 pilot -- model={args.model} endpoint={args.endpoint} step_cap={args.step_cap}")
    for spec in A2_9_SCENARIOS:
        print(f"  running {spec.scenario_id} ({spec.name})...", end=" ", flush=True)
        result, events = run_scenario(spec, step_cap=args.step_cap, model=args.model, endpoint=args.endpoint)
        scenario_results.append(result)
        all_events.extend(events)
        total_calls += len(events)
        total_wall_clock += result["wall_clock_seconds"]
        total_prompt_tokens += sum(event.get("prompt_tokens") or 0 for event in events)
        total_completion_tokens += sum(event.get("completion_tokens") or 0 for event in events)
        total_latency_ms += sum(event.get("latency_ms") or 0.0 for event in events)
        print(f"steps={result['steps_taken']} pass={result['deterministic_score']['pass']}")

    output = {
        "pilot_id": "M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_R1",
        "r1_purpose": "Frozen per-scenario harness-conformance rerun; original A2.9 evidence is preserved separately.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "endpoint": args.endpoint,
        "step_safety_cap": args.step_cap,
        "scenarios": scenario_results,
        "events": all_events,
        "aggregate": {
            "total_calls": total_calls,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "avg_latency_ms": (total_latency_ms / total_calls) if total_calls else 0.0,
            "total_wall_clock_seconds": total_wall_clock,
        },
        "reproducibility_metadata": _metadata(args.endpoint, args.model),
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\nR1 results written to {output_path}")
    passes = sum(1 for result in scenario_results if result["deterministic_score"]["pass"])
    print(f"Summary: {passes}/{len(scenario_results)} scenarios passed deterministic scoring.")
    for result in scenario_results:
        print(
            f"  {result['scenario_id']} {result['scenario_name']}: "
            f"pass={result['deterministic_score']['pass']} steps={result['steps_taken']} "
            f"hit_cap={result['hit_safety_cap']}"
        )


if __name__ == "__main__":
    main()
