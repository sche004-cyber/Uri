"""Late-pressure test (research): the Brain loads on a quiet desktop first, is measured, then a 1.09 GB GPU consumer
(Ollama qwen3.5:0.8b) arrives while the Brain stays resident, and the Brain is measured again. This is the order a
real desktop produces (URI starts at login, another GPU application starts later), which none of the R1/R2
consumer-first pressure tests covered.

  python r2/late_pressure.py --name r2L_full_default_r1 [--env K=V] [--extra=--no-mmproj-offload] [--no-mtp]
Evidence: evidence/<name>_<stamp>.json (+ server log)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_runtime as br  # noqa: E402

OLLAMA = "http://127.0.0.1:11434"


def consumer(on: bool) -> dict:
    body = {"model": "qwen3.5:0.8b", "keep_alive": "60m" if on else 0}
    if on:
        body.update({"prompt": "Say OK.", "stream": False, "options": {"num_predict": 4, "num_ctx": 4096}})
    t0 = time.monotonic()
    try:
        httpx.post(OLLAMA + "/api/generate", json=body, timeout=180)
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}
    time.sleep(3)
    ps = httpx.get(OLLAMA + "/api/ps", timeout=10).json()
    return {"seconds": round(time.monotonic() - t0, 2), "ps": ps}


def measure(client, url, tag, log):
    dec = br.phase_decode(client, url, 3, lambda m: log(f"{tag} {m}"))
    dcs = br.phase_decision(client, url, 4, lambda m: log(f"{tag} {m}"))
    return {"decode": dec, "decision": dcs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--binary-dir", default="D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64")
    ap.add_argument("--model-dir", default="C:/Users/cheta/Development/uri-adaptive-lab/models")
    ap.add_argument("--port", type=int, default=18497)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--extra", default="")
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--settle-s", type=float, default=15.0)
    a = ap.parse_args()
    m = br.PINNED["model"]
    for k in ("path", "mmproj", "mtp_draft"):
        m[k] = str(Path(a.model_dir) / Path(m[k]).name)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = br.EVID / f"{a.name}_{stamp}.json"
    lines = []

    def log(msg):
        line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        lines.append(line)

    env = dict(kv.split("=", 1) for kv in a.env)
    rec = {"name": a.name, "stamp": stamp, "kind": "late_pressure", "server_env": env, "extra_args": a.extra.split(),
           "mtp": not a.no_mtp, "binary_sha256": br.sha256(str(Path(a.binary_dir) / "llama-server.exe")),
           "model_path": m["path"], "model_sha256_pinned": m["sha256"]}
    srv = br.Server(a.binary_dir, a.port, br.EVID / f"server_{a.name}_{stamp}.log", mtp=not a.no_mtp, extra_env=env,
                    extra_args=a.extra.split() if a.extra else [])
    rec["argv"] = srv.argv()
    try:
        srv.start()
        rec["load_seconds"] = srv.load_seconds
        client = httpx.Client(timeout=900.0)
        br.chat(client, srv.url, [{"role": "user", "content": "hi"}], max_tokens=4)
        rec["before_snapshot"] = srv.snapshot()
        log(f"loaded {srv.load_seconds} s; residency {rec['before_snapshot'].get('server_gpu_memory_mib')}")
        rec["before"] = measure(client, srv.url, "before", log)
        rec["consumer_on"] = consumer(True)
        log(f"consumer on: {rec['consumer_on'].get('seconds')} s")
        time.sleep(a.settle_s)
        rec["after_consumer_snapshot"] = srv.snapshot()
        log(f"residency after consumer {rec['after_consumer_snapshot'].get('server_gpu_memory_mib')}")
        rec["after"] = measure(client, srv.url, "after", log)
        rec["end"] = srv.snapshot()
        rec["healthy_end"] = srv.healthy()
    except Exception as e:  # noqa: BLE001
        rec["fatal"] = f"{type(e).__name__}: {e}"
        log("FATAL " + rec["fatal"])
    finally:
        srv.stop()
        rec["consumer_off"] = consumer(False)
        rec["log"] = lines
        out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        b, af = rec.get("before", {}), rec.get("after", {})
        print("R2LATE", a.name, "load", rec.get("load_seconds"),
              "before decode/decision", (b.get("decode") or {}).get("tps", {}).get("p50"), (b.get("decision") or {}).get("total", {}).get("p50"),
              "after", (af.get("decode") or {}).get("tps", {}).get("p50"), (af.get("decision") or {}).get("total", {}).get("p50"),
              "res before", (rec.get("before_snapshot") or {}).get("server_gpu_memory_mib"),
              "res after", (rec.get("after_consumer_snapshot") or {}).get("server_gpu_memory_mib"),
              "consumer ps", json.dumps(((rec.get("consumer_on") or {}).get("ps") or {}).get("models", [{}])[:1])[:200],
              "fatal", rec.get("fatal"), flush=True)


if __name__ == "__main__":
    main()
