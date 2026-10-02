"""Run the frozen polish qualification set against one explicitly named model."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from config import load_config
from polish import Polisher
from qualification.score import score_item, summarize


ROOT = Path(__file__).resolve().parent.parent
SET_PATH = Path(__file__).with_name("polish_set.jsonl")


def load_set(path: Path = SET_PATH) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def set_sha(path: Path = SET_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def run(model: str, runs: int) -> dict[str, Any]:
    config = load_config(ROOT / "config.json")
    polisher = Polisher(True, model, config.polish_timeout_s, config.polish_num_ctx, config.polish_keep_alive)
    records: list[dict[str, Any]] = []
    for run_number in range(1, runs + 1):
        for item in load_set():
            started = time.perf_counter()
            result = polisher.polish(item["input"])
            latency_ms = (time.perf_counter() - started) * 1000
            score = score_item(item, result)
            records.append({"id": item["id"], "category": item["category"], "run": run_number,
                            "pass": score["pass"], "reasons": score["reasons"],
                            "latency_ms": round(latency_ms, 3), "output": result.text})
    summary = summarize(records)
    latencies = [record["latency_ms"] for record in records]
    summary.update({"p50_latency_ms": _percentile(latencies, 0.50),
                    "p95_latency_ms": _percentile(latencies, 0.95)})
    payload = {"model": model, "runs": runs, "set_sha": set_sha(), "results": records, "summary": summary}
    destination = Path(__file__).with_name(f"results_{model.replace(':', '_')}.json")
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--set-sha", action="store_true", help="print the frozen set SHA-256 before running")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.set_sha:
        print(f"set_sha={set_sha()}")
    payload = run(args.model, args.runs)
    print(json.dumps({"set_sha": payload["set_sha"], **payload["summary"]}, indent=2))


if __name__ == "__main__":
    main()
