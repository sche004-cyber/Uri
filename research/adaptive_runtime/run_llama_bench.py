"""Kernel-level throughput with llama-bench (no server, no MTP): prompt processing at 1K/8K/32K and
text generation, for one binary directory. Pinned model, pinned KV/batch settings.

  python run_llama_bench.py --name base_b11425 --binary-dir D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVID = HERE / "evidence"
PINNED = json.loads((HERE / "pinned_runtime_v1.json").read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--binary-dir", required=True)
    ap.add_argument("--pp", default="1024,8192")
    ap.add_argument("--pp-long", default="32768", help="long prompt sizes run with fewer repetitions")
    ap.add_argument("--tg", default="128")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--reps-long", type=int, default=2)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--extra", default="")
    ap.add_argument("--deadline-epoch", type=float, default=None)
    args = ap.parse_args()
    if args.deadline_epoch and time.time() > args.deadline_epoch:
        print("DEADLINE PASSED", file=sys.stderr)
        sys.exit(3)
    EVID.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(dict(kv.split("=", 1) for kv in args.env))
    exe = str(Path(args.binary_dir) / "llama-bench.exe")
    base = [exe, "-m", PINNED["model"]["path"], "-ngl", "99", "-fa", "1", "-ctk", "q8_0", "-ctv", "q8_0",
            "-b", "2048", "-ub", "1024", "-o", "json"] + (args.extra.split() if args.extra else [])
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rec = {"name": args.name, "stamp": stamp, "binary": exe, "binary_sha256": sha256(exe), "env": {k: env[k] for k in env if k.startswith("GGML_")},
           "runs": []}
    plans = [(args.pp, args.tg, args.reps), (args.pp_long, "0", args.reps_long)]
    for pp, tg, reps in plans:
        if not pp:
            continue
        cmd = base + ["-p", pp, "-n", tg, "-r", str(reps)]
        t0 = time.monotonic()
        out = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600)
        wall = round(time.monotonic() - t0, 1)
        try:
            data = json.loads(out.stdout)
        except Exception:
            data = None
        rec["runs"].append({"cmd": cmd, "wall_s": wall, "rc": out.returncode, "json": data,
                            "stderr_tail": out.stderr[-2000:]})
        if data:
            for row in data:
                print(f"{row.get('n_prompt')}/{row.get('n_gen')}: {row.get('avg_ts')} +- {row.get('stddev_ts')} t/s  (build {row.get('build_commit')})", flush=True)
        else:
            print(f"rc={out.returncode}\n{out.stdout[-800:]}\n{out.stderr[-800:]}", flush=True)
    p = EVID / f"llama_bench_{args.name}_{stamp}.json"
    p.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print("wrote", p)


if __name__ == "__main__":
    main()
