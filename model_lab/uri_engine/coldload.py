"""Cold vs warm model load from HDD (D:) and NVMe (C:), with hash-verification time.

"Cold" is approximated without admin rights by evicting the OS standby list: read `--evict-gib` GiB of other
files (buffered) from `--evict-dir` so the model pages fall out of the file cache (LRU), then start llama-server
and time /health. Then a warm load (same files, now cached). Writes evidence/uri_engine/coldload_<label>.json.

  python model_lab/uri_engine/coldload.py --label hdd --model D:/.../Qwen3.6-35B-A3B-UD-IQ3_S.gguf --mmproj D:/.../mmproj-F16.gguf
  python model_lab/uri_engine/coldload.py --label nvme --model C:/uri-model-lab-nvme/models/Qwen3.6-35B-A3B-UD-IQ3_S.gguf --mmproj C:/uri-model-lab-nvme/models/mmproj-F16.gguf
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB))
from lab.runtime import Server, ServerConfig  # noqa: E402

EVID = LAB / "evidence" / "uri_engine"


def evict(evict_dir, gib, exclude=()):
    """Buffered sequential reads of large files under evict_dir until `gib` GiB were read (never the
    files under test, which would re-cache them)."""
    target = gib * 2**30
    done = 0
    t0 = time.perf_counter()
    ex = {Path(e).resolve() for e in exclude}
    files = sorted((p for p in Path(evict_dir).rglob("*") if p.is_file() and p.stat().st_size > 64 * 2**20 and p.resolve() not in ex),
                   key=lambda p: -p.stat().st_size)
    for p in files:
        try:
            with open(p, "rb", buffering=0) as f:
                while True:
                    b = f.read(32 * 2**20)
                    if not b:
                        break
                    done += len(b)
                    if done >= target:
                        return {"evicted_gib": round(done / 2**30, 2), "seconds": round(time.perf_counter() - t0, 1), "files": str(p)}
        except OSError:
            continue
    return {"evicted_gib": round(done / 2**30, 2), "seconds": round(time.perf_counter() - t0, 1), "exhausted": True}


def sha256_time(path):
    h = hashlib.sha256()
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest(), round(time.perf_counter() - t0, 2)


def load_once(model, mmproj, port, log_dir):
    cfg = ServerConfig(name="coldload", model=model, ctx=32768, ngl=999, port=port, load_mode="none", mmproj=mmproj,
                       extra=("-b", "2048", "-ub", "1024", "--cache-ram", "1024"))
    srv = Server(cfg, log_dir).start(timeout=1200)
    snap = srv.resource_snapshot()
    srv.stop()
    return {"load_seconds": srv.load_seconds, **snap}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--mmproj", required=True)
    ap.add_argument("--evict-dir", default=r"D:\uri-model-lab\models")
    ap.add_argument("--evict-gib", type=float, default=30)
    ap.add_argument("--port", type=int, default=18497)
    ap.add_argument("--skip-evict", action="store_true")
    a = ap.parse_args()
    out = {"label": a.label, "model": a.model, "mmproj": a.mmproj, "evict": None}
    if not a.skip_evict:
        out["evict"] = evict(a.evict_dir, a.evict_gib, (a.model, a.mmproj))
        print("evicted", out["evict"])
    h, t = sha256_time(a.model)
    out["hash_cold"] = {"sha256": h, "seconds": t}
    print("hash cold", t)
    if not a.skip_evict:
        out["evict2"] = evict(a.evict_dir, a.evict_gib, (a.model, a.mmproj))
    out["load_cold"] = load_once(a.model, a.mmproj, a.port, EVID / "coldload_logs")
    print("load cold", out["load_cold"]["load_seconds"])
    out["load_warm"] = load_once(a.model, a.mmproj, a.port, EVID / "coldload_logs")
    print("load warm", out["load_warm"]["load_seconds"])
    h2, t2 = sha256_time(a.model)
    out["hash_warm"] = {"sha256": h2, "seconds": t2}
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / f"coldload_{a.label}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "model"}, indent=1))


if __name__ == "__main__":
    main()
