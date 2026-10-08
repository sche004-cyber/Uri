"""Aggregate rescored results across runs: latest run wins per (model, path, suite).

Writes evidence/comparison.json and prints a compact table. Runs listed in INVALID are skipped
for the named paths (documented harness artifacts, kept on disk for audit).
"""
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_bench import summarize  # noqa: E402

# (model, run stamp, path) -> reason. Evidence retained; excluded from comparison.
INVALID = {
    ("gemma4-26b-a4b-qat", "20261005-223612", "deep"): "thinking truncated by 600-700 token caps (finish=length)",
    ("gptoss-20b", "20261005-234119", "fast:P"): "pre-fix adapter (no clarification routing, wrong p10 expectation)",
    ("gptoss-20b", "20261005-234119", "fast:L"): "600-token cap consumed by mandatory reasoning",
    ("gptoss-20b", "20261005-234119", "fast:O"): "800-token cap with mandatory reasoning",
    ("gptoss-20b", "20261005-235144", "normal:P"): "pre-fix adapter; thinking starved 200-token interpreter",
    ("gptoss-20b", "20261005-235144", "deep:P"): "pre-fix adapter; thinking starved 200-token interpreter",
}


def main():
    latest = {}
    for f in sorted(glob.glob(str(HERE / "evidence/runs/*/*/results.rescored.jsonl"))):
        model, stamp = Path(f).parent.parent.name, Path(f).parent.name
        if model.startswith("dbg"):
            continue
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        by = {}
        for r in rows:
            by.setdefault((r["path"], r["suite"]), []).append(r)
        for (path, suite), rs in by.items():
            if (model, stamp, path) in INVALID or (model, stamp, f"{path}:{suite}") in INVALID:
                continue
            latest[(model, path, suite)] = (stamp, rs)
    out = {}
    for (model, path, suite), (stamp, rs) in sorted(latest.items()):
        s = summarize(rs)[f"{path}/{suite}"]
        s["run"] = stamp
        out.setdefault(model, {})[f"{path}/{suite}"] = s
    (HERE / "evidence" / "comparison.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    suites = ["F", "D", "DG", "C", "H", "S", "O", "R", "RH", "L", "P", "V"]
    for model, d in out.items():
        for path in ("fast", "normal", "deep"):
            cells = []
            for su in suites:
                v = d.get(f"{path}/{su}")
                if v:
                    lat = v.get("total_p50")
                    cells.append(f"{su}={v['score']:.2f}" + (f"({lat:.1f}s)" if lat is not None and su in ("D", "DG", "R", "RH", "L", "F") else ""))
            if cells:
                print(f"{model:28s} {path:6s} " + " ".join(cells))


if __name__ == "__main__":
    main()


