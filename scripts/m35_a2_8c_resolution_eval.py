"""M35 URIv1 Batch A2.8C — Resolution-Path Discovery Live Evaluation Script.

Executes all 16 benchmark cases across:
- Qwen3.5-2B (Mode A & Mode B)
- Qwen3.5-9B (Mode A & Mode B)
- LFM2.5-350M (Mode A & Mode B probe)

Saves complete machine-readable telemetry to:
scripts/m35_a2_8c_resolution_results.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from typing import Any, Dict, List

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from uri_v1.arn.a2_8c_benchmark import A2_8C_BENCHMARK_CASES, ResolutionTestCase
from uri_v1.arn.a2_8c_evaluator import ResolutionEvaluator, ResolutionExecutionMetric


def run_evaluation() -> None:
    print("=" * 80)
    print("M35 URIv1 Batch A2.8C — Resolution-Path Discovery & Capability-Grounding")
    print("=" * 80)

    endpoint = "http://127.0.0.1:1234/v1"
    evaluator = ResolutionEvaluator(endpoint=endpoint, timeout=35.0)

    models = [
        ("qwen3.5-2b", True),
        ("qwen3.5-9b", True),
        ("lfm2.5-350m", False),
    ]

    all_results: List[Dict[str, Any]] = []

    for model_name, is_qwen in models:
        print(f"\nEvaluating Model: {model_name} (is_qwen={is_qwen})")
        print("-" * 60)

        for mode_name, eval_fn in [
            ("MODE_A_DIRECT", evaluator.evaluate_case_mode_a),
            ("MODE_B_STRUCTURED", evaluator.evaluate_case_mode_b),
        ]:
            print(f"\n  Running Mode: {mode_name} ...")
            mode_t0 = time.perf_counter()

            for idx, case in enumerate(A2_8C_BENCHMARK_CASES, 1):
                metric = eval_fn(model_name=model_name, case=case, is_qwen=is_qwen)

                # Format compact display
                chosen = (
                    metric.raw_response.get("matched_capability")
                    if mode_name == "MODE_B_STRUCTURED"
                    else metric.raw_response.get("selected_capability")
                )
                status = "PASS" if metric.scores.get("final_task_path_success") else "FAIL"
                fail_reason = f" ({metric.failure_attribution})" if metric.failure_attribution else ""

                print(
                    f"    [{idx:02d}/16] {case.case_id:<10} | {case.category:<20} | "
                    f"Chosen: {str(chosen):<25} | {status}{fail_reason} ({metric.total_latency_ms:.0f}ms)"
                )

                all_results.append(asdict(metric))

            mode_duration = time.perf_counter() - mode_t0
            print(f"  Mode {mode_name} finished in {mode_duration:.2f}s")

    # Persist JSON telemetry
    out_path = os.path.join(repo_root, "scripts", "m35_a2_8c_resolution_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved {len(all_results)} evaluation records to {out_path}")

    # Generate Summary Metrics
    print("\n" + "=" * 80)
    print("M35 A2.8C SUMMARY AGGREGATE RESULTS")
    print("=" * 80)

    header = (
        f"{'Model':<12} | {'Mode':<18} | {'RPS':<6} | {'CJA':<6} | {'CapAcc':<6} | "
        f"{'WrongCap':<8} | {'Unnec':<6} | {'NoTool':<6} | {'AskUser':<7} | {'Strat':<6} | "
        f"{'Success':<7} | {'AvgLat':<7}"
    )
    print(header)
    print("-" * len(header))

    for model_name, _ in models:
        for mode_name in ["MODE_A_DIRECT", "MODE_B_STRUCTURED"]:
            records = [r for r in all_results if r["model_name"] == model_name and r["mode"] == mode_name]
            n = len(records)
            if not n:
                continue

            rps = sum(1 for r in records if r["scores"].get("resolution_path_sufficiency")) / n * 100.0
            cja = sum(1 for r in records if r["scores"].get("capability_justification_accuracy")) / n * 100.0
            cap_acc = sum(1 for r in records if r["scores"].get("capability_selection_accuracy")) / n * 100.0
            wrong_cap = sum(1 for r in records if r["scores"].get("wrong_capability")) / n * 100.0
            unnec = sum(1 for r in records if r["scores"].get("unnecessary_capability_invocation")) / n * 100.0

            no_tool_recs = [r for r in records if r["scores"].get("correct_no_tool") is not None]
            no_tool_acc = (
                sum(1 for r in no_tool_recs if r["scores"]["correct_no_tool"]) / len(no_tool_recs) * 100.0
                if no_tool_recs
                else 0.0
            )

            ask_user_recs = [r for r in records if r["scores"].get("correct_ask_user") is not None]
            ask_user_acc = (
                sum(1 for r in ask_user_recs if r["scores"]["correct_ask_user"]) / len(ask_user_recs) * 100.0
                if ask_user_recs
                else 0.0
            )

            strat_recs = [r for r in records if r["scores"].get("correct_strategy_discovery") is not None]
            strat_acc = (
                sum(1 for r in strat_recs if r["scores"]["correct_strategy_discovery"]) / len(strat_recs) * 100.0
                if strat_recs
                else 0.0
            )

            success = sum(1 for r in records if r["scores"].get("final_task_path_success")) / n * 100.0
            avg_lat = sum(r["total_latency_ms"] for r in records) / n

            mode_short = "Direct (Mode A)" if "DIRECT" in mode_name else "Structured (B)"
            print(
                f"{model_name:<12} | {mode_short:<18} | {rps:5.1f}% | {cja:5.1f}% | {cap_acc:5.1f}% | "
                f"{wrong_cap:7.1f}% | {unnec:5.1f}% | {no_tool_acc:5.1f}% | {ask_user_acc:6.1f}% | {strat_acc:5.1f}% | "
                f"{success:6.1f}% | {avg_lat:6.0f}ms"
            )


if __name__ == "__main__":
    run_evaluation()
