"""M35 URIv1 Batch A2.8B — RAR + ARN Model Amplification Evaluation Driver.

Evaluates:
- 3 models: LFM2.5-350M, Qwen3.5-2B, Qwen3.5-9B
- 4 modes: Mode A (RAW), Mode B (RAR), Mode C (RAR + ARN), Mode D (FULL HARNESS)
- 12 benchmark cases (144 evaluation runs total)

Measures semantic accuracy across all 13 dimensions, latencies, tokens, calls,
calculates RAR Gain, ARN Gain, Full Harness Gain, and persists machine-readable
results to scripts/m35_a2_8b_amplification_results.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from uri_v1.arn.a2_8b_benchmark import AmplificationTestCase, build_a2_8b_benchmark_suite
from uri_v1.arn.a2_8b_evaluator import AmplificationEvaluator, ExecutionMetric


MODELS = [
    {"name": "lfm2.5-350m", "is_qwen": False, "desc": "350M Lower-bound probe"},
    {"name": "qwen3.5-2b", "is_qwen": True, "desc": "2B Sub-threshold candidate"},
    {"name": "qwen3.5-9b", "is_qwen": True, "desc": "9B Qualified Resident Main-Brain provider"},
]


def run_amplification_evaluation(
    endpoint: str = "http://127.0.0.1:1234/v1",
    models_to_test: Sequence[str] = ("lfm2.5-350m", "qwen3.5-2b", "qwen3.5-9b"),
) -> Dict[str, Any]:
    print("=" * 80)
    print("M35 URIv1 Batch A2.8B — RAR + ARN Model Amplification Qualification")
    print(f"Endpoint: {endpoint}")
    print(f"Models: {models_to_test}")
    print("=" * 80)

    suite = build_a2_8b_benchmark_suite()
    evaluator = AmplificationEvaluator(endpoint=endpoint)

    results: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "benchmark_cases_count": len(suite),
        "models": {},
        "summary_matrix": {},
    }

    for m_info in MODELS:
        m_name = m_info["name"]
        if m_name not in models_to_test:
            continue

        is_qwen = m_info["is_qwen"]
        print(f"\n>>> Evaluating Model: {m_name} ({m_info['desc']}) <<<")

        model_results: Dict[str, Any] = {
            "model_name": m_name,
            "description": m_info["desc"],
            "modes": {
                "MODE_A_RAW": [],
                "MODE_B_RAR": [],
                "MODE_C_RAR_ARN": [],
                "MODE_D_FULL_HARNESS": [],
            },
            "metrics": {},
        }

        for case in suite:
            print(f"  [{case.case_id}] {case.user_text}")

            # Mode A
            res_a = evaluator.evaluate_case_mode_a(m_name, case, is_qwen=is_qwen)
            model_results["modes"]["MODE_A_RAW"].append({
                "case_id": case.case_id,
                "latency_ms": res_a.total_latency_ms,
                "tokens": res_a.prompt_tokens + res_a.completion_tokens,
                "critical_semantic_ok": res_a.scores.get("critical_semantic_ok", False),
                "scores": res_a.scores,
                "error": res_a.error,
            })

            # Mode B
            res_b = evaluator.evaluate_case_mode_b(m_name, case, is_qwen=is_qwen)
            model_results["modes"]["MODE_B_RAR"].append({
                "case_id": case.case_id,
                "latency_ms": res_b.total_latency_ms,
                "tokens": res_b.prompt_tokens + res_b.completion_tokens,
                "critical_semantic_ok": res_b.scores.get("critical_semantic_ok", False),
                "scores": res_b.scores,
                "error": res_b.error,
            })

            # Mode C
            res_c = evaluator.evaluate_case_mode_c(m_name, case, is_qwen=is_qwen)
            model_results["modes"]["MODE_C_RAR_ARN"].append({
                "case_id": case.case_id,
                "latency_ms": res_c.total_latency_ms,
                "tokens": res_c.prompt_tokens + res_c.completion_tokens,
                "critical_semantic_ok": res_c.scores.get("critical_semantic_ok", False),
                "scores": res_c.scores,
                "error": res_c.error,
            })

            # Mode D
            res_d = evaluator.evaluate_case_mode_d(m_name, case, is_qwen=is_qwen)
            model_results["modes"]["MODE_D_FULL_HARNESS"].append({
                "case_id": case.case_id,
                "latency_ms": res_d.total_latency_ms,
                "tokens": res_d.prompt_tokens + res_d.completion_tokens,
                "critical_semantic_ok": res_d.scores.get("critical_semantic_ok", False),
                "scores": res_d.scores,
                "error": res_d.error,
            })

            print(
                f"    -> Mode A: {'PASS' if res_a.scores.get('critical_semantic_ok') else 'FAIL'} ({res_a.total_latency_ms:.0f}ms) | "
                f"Mode B: {'PASS' if res_b.scores.get('critical_semantic_ok') else 'FAIL'} ({res_b.total_latency_ms:.0f}ms) | "
                f"Mode C: {'PASS' if res_c.scores.get('critical_semantic_ok') else 'FAIL'} ({res_c.total_latency_ms:.0f}ms) | "
                f"Mode D: {'PASS' if res_d.scores.get('critical_semantic_ok') else 'FAIL'} ({res_d.total_latency_ms:.0f}ms)"
            )

        # Calculate Mode Summaries
        for mode_key in ("MODE_A_RAW", "MODE_B_RAR", "MODE_C_RAR_ARN", "MODE_D_FULL_HARNESS"):
            records = model_results["modes"][mode_key]
            total_cases = len(records)
            critical_passes = sum(1 for r in records if r["critical_semantic_ok"])
            req_passes = sum(1 for r in records if r["scores"].get("req_ops_ok", False))
            pro_passes = sum(1 for r in records if r["scores"].get("pro_ops_ok", False))
            polarity_inversions = sum(1 for r in records if r["scores"].get("polarity_inverted", False))
            hallucinations = sum(1 for r in records if r["scores"].get("hallucination", False))
            target_binding_passes = sum(1 for r in records if r["scores"].get("target_binding_ok", False))
            unresolved_passes = sum(1 for r in records if r["scores"].get("unresolved_honesty", False))

            mean_lat = sum(r["latency_ms"] for r in records) / max(total_cases, 1)
            mean_tok = sum(r["tokens"] for r in records) / max(total_cases, 1)

            model_results["metrics"][mode_key] = {
                "critical_semantic_accuracy_pct": (critical_passes / total_cases) * 100.0,
                "critical_passes": critical_passes,
                "total_cases": total_cases,
                "requested_ops_accuracy_pct": (req_passes / total_cases) * 100.0,
                "prohibited_ops_accuracy_pct": (pro_passes / total_cases) * 100.0,
                "polarity_inversions_count": polarity_inversions,
                "hallucinations_count": hallucinations,
                "target_binding_accuracy_pct": (target_binding_passes / total_cases) * 100.0,
                "unresolved_honesty_pct": (unresolved_passes / total_cases) * 100.0,
                "mean_latency_ms": mean_lat,
                "mean_tokens_per_turn": mean_tok,
            }

        # Calculate Gains
        acc_a = model_results["metrics"]["MODE_A_RAW"]["critical_semantic_accuracy_pct"]
        acc_b = model_results["metrics"]["MODE_B_RAR"]["critical_semantic_accuracy_pct"]
        acc_c = model_results["metrics"]["MODE_C_RAR_ARN"]["critical_semantic_accuracy_pct"]
        acc_d = model_results["metrics"]["MODE_D_FULL_HARNESS"]["critical_semantic_accuracy_pct"]

        model_results["metrics"]["gains"] = {
            "rar_gain_pct": acc_b - acc_a,
            "arn_gain_pct": acc_c - acc_b,
            "full_harness_gain_pct": acc_d - acc_a,
        }

        results["models"][m_name] = model_results
        results["summary_matrix"][m_name] = {
            "Mode_A_Raw": f"{acc_a:.1f}%",
            "Mode_B_RAR": f"{acc_b:.1f}%",
            "Mode_C_RAR_ARN": f"{acc_c:.1f}%",
            "Mode_D_Full_Harness": f"{acc_d:.1f}%",
            "RAR_Gain": f"{acc_b - acc_a:+.1f}%",
            "ARN_Gain": f"{acc_c - acc_b:+.1f}%",
            "Full_Harness_Gain": f"{acc_d - acc_a:+.1f}%",
        }

    # Summary table print
    print("\n" + "=" * 80)
    print("A2.8B AMPLIFICATION QUALIFICATION SUMMARY MATRIX")
    print("=" * 80)
    print(f"{'Model':<12} | {'Raw (A)':<10} | {'+RAR (B)':<10} | {'+ARN (C)':<10} | {'Full (D)':<10} | {'Full Gain':<10}")
    print("-" * 75)
    for m_name, row in results["summary_matrix"].items():
        print(f"{m_name:<12} | {row['Mode_A_Raw']:<10} | {row['Mode_B_RAR']:<10} | {row['Mode_C_RAR_ARN']:<10} | {row['Mode_D_Full_Harness']:<10} | {row['Full_Harness_Gain']:<10}")
    print("=" * 80)

    out_path = REPO_ROOT / "scripts" / "m35_a2_8b_amplification_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nMachine-readable benchmark results persisted to: {out_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="M35 A2.8B Model Amplification Benchmark")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--models", nargs="+", default=["lfm2.5-350m", "qwen3.5-2b", "qwen3.5-9b"])
    args = parser.parse_args()

    run_amplification_evaluation(endpoint=args.endpoint, models_to_test=args.models)
