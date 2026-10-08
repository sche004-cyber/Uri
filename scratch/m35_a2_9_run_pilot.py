"""M35 URIv1 A2.9 -- Native Problem-Solving Trace pilot runner.

Disposable pilot harness. Not production URI code. See
docs/plans/M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md.

Usage:
    python scratch/m35_a2_9_run_pilot.py --endpoint http://127.0.0.1:1234/v1/chat/completions --model qwen3.5-9b
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scratch.m35_a2_9_native_trace_scenarios import A2_9_SCENARIOS
from scratch.m35_a2_9_native_trace_harness import run_scenario

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "m35_a2_9_native_trace_results.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="M35 URIv1 A2.9 Native Problem-Solving Trace pilot")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.5-9b")
    parser.add_argument("--step-cap", type=int, default=10)
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()

    scenario_results = []
    all_events = []
    total_calls = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_latency_ms = 0.0
    total_wall_clock = 0.0

    print(f"M35 A2.9 pilot -- model={args.model} endpoint={args.endpoint} step_cap={args.step_cap}")
    for spec in A2_9_SCENARIOS:
        print(f"  running {spec.scenario_id} ({spec.name})...", end=" ", flush=True)
        result, events = run_scenario(spec, step_cap=args.step_cap, model=args.model, endpoint=args.endpoint)
        scenario_results.append(result)
        all_events.extend(events)
        total_calls += len(events)
        total_wall_clock += result["wall_clock_seconds"]
        for ev in events:
            total_prompt_tokens += ev.get("prompt_tokens") or 0
            total_completion_tokens += ev.get("completion_tokens") or 0
            total_latency_ms += ev.get("latency_ms") or 0.0
        score = result["deterministic_score"]
        print(f"steps={result['steps_taken']} pass={score['pass']}")

    aggregate = {
        "total_calls": total_calls,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "avg_latency_ms": (total_latency_ms / total_calls) if total_calls else 0.0,
        "total_wall_clock_seconds": total_wall_clock,
    }

    output = {
        "pilot_id": "M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "endpoint": args.endpoint,
        "step_safety_cap": args.step_cap,
        "scenarios": scenario_results,
        "events": all_events,
        "aggregate": aggregate,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults written to {args.output}")
    passes = sum(1 for r in scenario_results if r["deterministic_score"]["pass"])
    print(f"Summary: {passes}/{len(scenario_results)} scenarios passed deterministic scoring.")
    for r in scenario_results:
        print(f"  {r['scenario_id']} {r['scenario_name']}: pass={r['deterministic_score']['pass']} steps={r['steps_taken']} hit_cap={r['hit_safety_cap']}")


if __name__ == "__main__":
    main()
