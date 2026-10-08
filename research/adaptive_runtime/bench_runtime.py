"""Adaptive Runtime research: controlled llama-server profile for one runtime configuration.

Research only. Reads the pinned Runtime v1 artifacts by path (never modifies them), launches a
llama-server from a chosen binary directory on a research port, and measures what URI pays for:
prefill at ~1K/8K/32K tokens (fresh and cached), time to first token, decode throughput, end-to-end
latency of a decision-sized turn (p50/p95), cancellation/timeout behaviour, repeated-request stability,
VRAM/RSS/RAM. Every call records the server's own timings (prompt_n, cache_n, prompt_ms, predicted_ms).

  python bench_runtime.py --name base_b11425 --binary-dir D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64
  python bench_runtime.py --name b11510 --binary-dir C:/Users/cheta/Development/uri-adaptive-lab/runtime/b11510-vulkan

Evidence: research/adaptive_runtime/evidence/<name>_<stamp>.json (+ server log).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import psutil

HERE = Path(__file__).resolve().parent
EVID = HERE / "evidence"
PINNED = json.loads((HERE / "pinned_runtime_v1.json").read_text(encoding="utf-8"))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def ps(cmd: str, timeout=20):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=timeout)
    return out.stdout.strip()


def gpu_dedicated_mib():
    try:
        v = ps("(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | "
               "Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum")
        return round(float(v) / 2**20, 1)
    except Exception:
        return None


def gpu_other_owners():
    """Processes other than this harness that could hold the GPU (interference record)."""
    owners = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            n = (p.info["name"] or "").lower()
            if any(k in n for k in ("llama", "ollama", "koboldcpp", "lmstudio", "strata")):
                cmd = " ".join(p.info["cmdline"] or [])
                owners.append({"pid": p.info["pid"], "name": p.info["name"], "cmd": cmd[:300],
                               "started": dt.datetime.fromtimestamp(p.info["create_time"]).isoformat(timespec="seconds")})
        except Exception:
            pass
    return owners


class Sampler(threading.Thread):
    def __init__(self, pid, interval=2.0):
        super().__init__(daemon=True)
        self.pid, self.interval = pid, interval
        self.stop_evt = threading.Event()
        self.peak_rss = 0.0
        self.peak_vram = 0.0
        self.min_avail_ram = float("inf")
        self.samples = 0

    def run(self):
        try:
            proc = psutil.Process(self.pid)
        except Exception:
            return
        while not self.stop_evt.is_set():
            try:
                self.peak_rss = max(self.peak_rss, proc.memory_info().rss / 2**20)
            except Exception:
                pass
            self.min_avail_ram = min(self.min_avail_ram, psutil.virtual_memory().available / 2**20)
            v = gpu_dedicated_mib()
            if v:
                self.peak_vram = max(self.peak_vram, v)
            self.samples += 1
            self.stop_evt.wait(self.interval)

    def summary(self):
        return {"peak_server_rss_mib": round(self.peak_rss, 1), "peak_vram_dedicated_mib": self.peak_vram,
                "min_system_available_ram_mib": round(self.min_avail_ram, 1) if self.samples else None}


class Server:
    def __init__(self, binary_dir: str, port: int, log_path: Path, mtp: bool, extra_env: dict | None = None,
                 ctx: int | None = None, extra_args: list[str] | None = None, vision: bool = True):
        self.binary = str(Path(binary_dir) / "llama-server.exe")
        self.port, self.log_path, self.mtp = port, log_path, mtp
        self.env = dict(os.environ)
        self.env.update(extra_env or {})
        self.ctx = ctx or PINNED["ctx"]
        self.extra_args = extra_args or []
        self.vision = vision
        self.proc = None
        self.sampler = None
        self.load_seconds = None

    def argv(self):
        m = PINNED["model"]
        a = [self.binary, "-m", m["path"], "-c", str(self.ctx), "-ngl", "999", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
             "-np", "1", "--host", "127.0.0.1", "--port", str(self.port), "--jinja", "--reasoning-format", "deepseek",
             "--no-webui", "--load-mode", "none", "--metrics"]
        a += PINNED["flags_cache_batch"]
        if self.vision:
            a += ["--mmproj", m["mmproj"]]
        else:
            a += ["--no-mmproj"]
        if self.mtp:
            a += ["-md", m["mtp_draft"], "--spec-type", "draft-mtp", "--spec-draft-n-max", "2", "-otd", "token_embd.weight=CPU"]
        return a + self.extra_args

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout=600):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(self.log_path, "w", encoding="utf-8", errors="replace")
        t0 = time.monotonic()
        self.proc = subprocess.Popen(self.argv(), stdout=log, stderr=subprocess.STDOUT, env=self.env,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.sampler = Sampler(self.proc.pid)
        self.sampler.start()
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited rc={self.proc.returncode}; see {self.log_path}")
            try:
                if httpx.get(self.url + "/health", timeout=2).status_code == 200:
                    self.load_seconds = round(time.monotonic() - t0, 2)
                    return self
            except Exception:
                pass
            time.sleep(0.5)
        self.stop()
        raise TimeoutError("server did not become healthy")

    def healthy(self):
        try:
            return httpx.get(self.url + "/health", timeout=5).status_code == 200
        except Exception:
            return False

    def snapshot(self):
        s = {"load_seconds": self.load_seconds, "vram_dedicated_now_mib": gpu_dedicated_mib(),
             "system_available_ram_mib": round(psutil.virtual_memory().available / 2**20, 1)}
        try:
            s["server_rss_now_mib"] = round(psutil.Process(self.proc.pid).memory_info().rss / 2**20, 1)
        except Exception:
            pass
        if self.sampler:
            s.update(self.sampler.summary())
        return s

    def stop(self):
        if self.sampler:
            self.sampler.stop_evt.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        time.sleep(2)


# ---------------------------------------------------------------- prompts

WORDS = ("the project ledger lists every invoice, delivery note and approval that the operations team recorded "
         "during the quarter; each entry carries a date, a vendor, an amount in euros, a cost centre and a short "
         "note explaining the context, and the reviewer must reconcile these against the bank statements before "
         "the audit window closes next month").split()


def synthetic_text(n_words: int, seed: int) -> str:
    """Deterministic, non-repeating-ish prose so prompt caching cannot match across seeds."""
    out = []
    for i in range(n_words):
        w = WORDS[(i * 7 + seed * 13 + (i // 11)) % len(WORDS)]
        if i % 37 == 0:
            w = f"[record {seed}-{i // 37}] " + w
        out.append(w)
    return " ".join(out)


def tokenize_count(client: httpx.Client, url: str, text: str) -> int:
    r = client.post(url + "/tokenize", json={"content": text}, timeout=120)
    return len(r.json()["tokens"])


def build_prompt_for_tokens(client, url, target_tokens: int, seed: int) -> tuple[str, int]:
    words = int(target_tokens * 0.7)
    txt = synthetic_text(words, seed)
    n = tokenize_count(client, url, txt)
    for _ in range(3):
        if abs(n - target_tokens) / target_tokens < 0.03:
            break
        words = int(words * target_tokens / max(n, 1))
        txt = synthetic_text(words, seed)
        n = tokenize_count(client, url, txt)
    return txt, n


DECISION_SYSTEM = ("You are URI's decision proposer. Read the request context and reply with a compact JSON object "
                   "with keys route (one of conversation, clarification, action, escalate), confidence (0-1), "
                   "rationale (one sentence), and slots (object). Do not add prose outside the JSON.")


def decision_user(seed: int, filler_tokens_words: int) -> str:
    ctx = synthetic_text(filler_tokens_words, seed)
    return (f"CONTEXT_EVIDENCE:\n{ctx}\n\nUSER_TEXT: Please summarise which vendor has the largest unreconciled "
            f"amount in record set {seed} and propose the next action.")


# ---------------------------------------------------------------- calls

def chat(client: httpx.Client, url: str, messages, max_tokens=256, timeout=900.0, extra=None, stream=True,
         cancel_after_s: float | None = None):
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": 0.0, "seed": 7,
            "stream": stream, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False}}
    if extra:
        body.update(extra)
    t0 = time.monotonic()
    first = None
    n_chunks = 0
    timings = usage = None
    finish = None
    text = []
    cancelled = False
    err = None
    try:
        with client.stream("POST", url + "/v1/chat/completions", json=body, timeout=timeout) as r:
            if r.status_code != 200:
                err = f"HTTP {r.status_code}: {r.read().decode(errors='replace')[:300]}"
            else:
                for line in r.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    j = json.loads(payload)
                    if "timings" in j:
                        timings = j["timings"]
                    if j.get("usage"):
                        usage = j["usage"]
                    for ch in j.get("choices", []):
                        d = ch.get("delta", {})
                        if d.get("content"):
                            if first is None:
                                first = time.monotonic() - t0
                            text.append(d["content"])
                            n_chunks += 1
                        if ch.get("finish_reason"):
                            finish = ch["finish_reason"]
                    if cancel_after_s is not None and time.monotonic() - t0 > cancel_after_s:
                        cancelled = True
                        break
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
    total = time.monotonic() - t0
    rec = {"total_s": round(total, 4), "ttft_s": round(first, 4) if first is not None else None,
           "finish": finish, "cancelled": cancelled, "error": err, "n_content_chunks": n_chunks,
           "text_head": "".join(text)[:160]}
    if timings:
        rec.update({k: timings.get(k) for k in ("prompt_n", "cache_n", "prompt_ms", "prompt_per_second",
                                                "predicted_n", "predicted_ms", "predicted_per_second",
                                                "draft_n", "draft_n_accepted")})
    if usage:
        rec["usage"] = usage
    return rec


def pct(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[f] + (vals[c] - vals[f]) * (k - f), 4)


def summarize(rows, key):
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    return {"n": len(vals), "p50": pct(vals, 0.5), "p95": pct(vals, 0.95), "min": round(min(vals), 4) if vals else None,
            "max": round(max(vals), 4) if vals else None, "mean": round(statistics.fmean(vals), 4) if vals else None}


# ---------------------------------------------------------------- phases

def phase_prefill(client, url, sizes, log):
    out = {}
    for size in sizes:
        txt, n = build_prompt_for_tokens(client, url, size, seed=size)
        msgs = [{"role": "user", "content": txt + "\n\nIn one sentence, what is this document about?"}]
        fresh = chat(client, url, msgs, max_tokens=32)
        repeat = chat(client, url, msgs, max_tokens=32)
        # new turn on the cached context (the v1 layout's "new user turn" case)
        msgs2 = msgs + [{"role": "assistant", "content": fresh.get("text_head") or "It is a ledger."},
                        {"role": "user", "content": "Name one vendor mentioned."}]
        newturn = chat(client, url, msgs2, max_tokens=24)
        out[str(size)] = {"target_tokens": size, "measured_tokens": n, "fresh": fresh, "repeat": repeat, "new_turn": newturn}
        log(f"prefill {size}: fresh prompt_n={fresh.get('prompt_n')} cache_n={fresh.get('cache_n')} "
            f"prompt_ms={fresh.get('prompt_ms')} pps={fresh.get('prompt_per_second')} ttft={fresh.get('ttft_s')} | "
            f"repeat cache_n={repeat.get('cache_n')} ttft={repeat.get('ttft_s')} | newturn prompt_n={newturn.get('prompt_n')} ttft={newturn.get('ttft_s')}")
    return out


def phase_decode(client, url, n_rounds, log):
    rows = []
    for i in range(n_rounds):
        msgs = [{"role": "user", "content": f"Write a detailed, numbered 20-step procedure for reconciling a quarterly ledger (variant {i})."}]
        r = chat(client, url, msgs, max_tokens=256)
        rows.append(r)
        log(f"decode {i}: pred_n={r.get('predicted_n')} tps={r.get('predicted_per_second')} ttft={r.get('ttft_s')} "
            f"draft={r.get('draft_n')}/{r.get('draft_n_accepted')} finish={r.get('finish')} err={r.get('error')}")
    return {"rows": rows, "tps": summarize(rows, "predicted_per_second"), "ttft": summarize(rows, "ttft_s"),
            "errors": sum(1 for r in rows if r.get("error"))}


def phase_decision(client, url, n_rounds, log, filler_words=650):
    """Decision-sized turn: stable system prompt, ~1k-token changing user JSON-ish payload, ~150 tokens out."""
    rows = []
    for i in range(n_rounds):
        msgs = [{"role": "system", "content": DECISION_SYSTEM},
                {"role": "user", "content": decision_user(1000 + i, filler_words)}]
        r = chat(client, url, msgs, max_tokens=160)
        rows.append(r)
        log(f"decision {i}: prompt_n={r.get('prompt_n')} cache_n={r.get('cache_n')} ttft={r.get('ttft_s')} total={r.get('total_s')} "
            f"pred_n={r.get('predicted_n')} tps={r.get('predicted_per_second')} err={r.get('error')}")
    return {"rows": rows, "ttft": summarize(rows, "ttft_s"), "total": summarize(rows, "total_s"),
            "prompt_tps": summarize(rows, "prompt_per_second"), "tps": summarize(rows, "predicted_per_second"),
            "errors": sum(1 for r in rows if r.get("error"))}


def phase_cancel(client, url, srv, log):
    """Client disconnects mid-generation; then a client timeout during a long prefill; server must stay healthy."""
    res = {}
    msgs = [{"role": "user", "content": "Write a 2000-word essay on ledger reconciliation."}]
    t0 = time.monotonic()
    r = chat(client, url, msgs, max_tokens=1024, cancel_after_s=1.5)
    res["disconnect_mid_generation"] = r
    t1 = time.monotonic()
    follow = chat(client, url, [{"role": "user", "content": "Say OK."}], max_tokens=4)
    res["follow_up_after_disconnect"] = follow
    res["follow_up_wait_s"] = round(time.monotonic() - t1, 3)
    res["healthy_after_disconnect"] = srv.healthy()
    log(f"cancel: disconnected after {r['total_s']} s (chunks {r['n_content_chunks']}); follow-up total {follow.get('total_s')} s "
        f"ttft {follow.get('ttft_s')} healthy={res['healthy_after_disconnect']}")
    # client-side timeout during a fresh ~8k prefill
    txt, n = build_prompt_for_tokens(client, url, 8000, seed=777)
    r2 = chat(client, url, [{"role": "user", "content": txt + "\n\nSummarise."}], max_tokens=16, timeout=1.0)
    res["client_timeout_during_prefill"] = r2
    t2 = time.monotonic()
    follow2 = chat(client, url, [{"role": "user", "content": "Say OK again."}], max_tokens=4)
    res["follow_up_after_timeout"] = follow2
    res["follow_up_after_timeout_wait_s"] = round(time.monotonic() - t2, 3)
    res["healthy_after_timeout"] = srv.healthy()
    log(f"timeout: {r2.get('error')} ; follow-up total {follow2.get('total_s')} s healthy={res['healthy_after_timeout']}")
    return res


def phase_stability(client, url, n_rounds, log):
    rows = []
    for i in range(n_rounds):
        msgs = [{"role": "system", "content": DECISION_SYSTEM},
                {"role": "user", "content": decision_user(5000 + (i % 5), 650)}]
        r = chat(client, url, msgs, max_tokens=120)
        rows.append(r)
    first = rows[: max(1, len(rows) // 3)]
    last = rows[-max(1, len(rows) // 3):]
    s = {"n": len(rows), "errors": sum(1 for r in rows if r.get("error")), "total": summarize(rows, "total_s"),
         "first_third_total_p50": pct([r["total_s"] for r in first], 0.5),
         "last_third_total_p50": pct([r["total_s"] for r in last], 0.5),
         "tps": summarize(rows, "predicted_per_second"), "rows": rows}
    log(f"stability: n={s['n']} errors={s['errors']} total p50={s['total']['p50']} p95={s['total']['p95']} "
        f"first/last third p50 {s['first_third_total_p50']}/{s['last_third_total_p50']}")
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--binary-dir", required=True)
    ap.add_argument("--port", type=int, default=18497)
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--no-vision", action="store_true")
    ap.add_argument("--ctx", type=int, default=None)
    ap.add_argument("--sizes", default="1000,8000,30000")
    ap.add_argument("--decode-rounds", type=int, default=5)
    ap.add_argument("--decision-rounds", type=int, default=10)
    ap.add_argument("--stability-rounds", type=int, default=20)
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for the server environment")
    ap.add_argument("--extra", default="", help="extra llama-server args appended after the pinned flags")
    ap.add_argument("--skip", default="", help="comma list: prefill,decode,decision,cancel,stability")
    ap.add_argument("--deadline-epoch", type=float, default=None, help="refuse to start if past this unix time")
    args = ap.parse_args()

    if args.deadline_epoch and time.time() > args.deadline_epoch:
        print("DEADLINE PASSED - not starting", file=sys.stderr)
        sys.exit(3)

    EVID.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = EVID / f"{args.name}_{stamp}.json"
    log_lines = []

    def log(msg):
        line = f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        log_lines.append(line)

    skip = set(s for s in args.skip.split(",") if s)
    env = dict(kv.split("=", 1) for kv in args.env)
    extra_args = args.extra.split() if args.extra else []

    binary = str(Path(args.binary_dir) / "llama-server.exe")
    record = {
        "name": args.name, "stamp": stamp, "binary": binary, "binary_sha256": sha256(binary),
        "ggml_vulkan_sha256": sha256(str(Path(args.binary_dir) / "ggml-vulkan.dll")) if (Path(args.binary_dir) / "ggml-vulkan.dll").exists() else None,
        "model_path": PINNED["model"]["path"], "model_sha256_pinned": PINNED["model"]["sha256"],
        "mtp": not args.no_mtp, "vision": not args.no_vision, "ctx": args.ctx or PINNED["ctx"],
        "server_env": env, "extra_args": extra_args,
        "gpu_other_owners_before": gpu_other_owners(), "vram_dedicated_before_mib": gpu_dedicated_mib(),
        "system_available_ram_before_mib": round(psutil.virtual_memory().available / 2**20, 1),
    }
    log(f"start {args.name}; VRAM before {record['vram_dedicated_before_mib']} MiB; other GPU-ish owners: "
        f"{[(o['pid'], o['name'], o['cmd'][:60]) for o in record['gpu_other_owners_before']]}")

    srv = Server(args.binary_dir, args.port, EVID / f"server_{args.name}_{stamp}.log", mtp=not args.no_mtp,
                 extra_env=env, ctx=args.ctx, extra_args=extra_args, vision=not args.no_vision)
    record["argv"] = srv.argv()
    try:
        srv.start()
        log(f"server healthy after {srv.load_seconds} s (warm/cold not controlled: see page-cache note)")
        record["load_seconds"] = srv.load_seconds
        record["props"] = {}
        try:
            record["props"] = httpx.get(srv.url + "/props", timeout=10).json()
        except Exception:
            pass
        client = httpx.Client(http2=False, timeout=900.0, limits=httpx.Limits(max_keepalive_connections=4))
        warm = chat(client, srv.url, [{"role": "user", "content": "hi"}], max_tokens=4)
        record["warmup"] = warm
        record["after_load"] = srv.snapshot()
        sizes = [int(s) for s in args.sizes.split(",") if s]
        if "prefill" not in skip:
            record["prefill"] = phase_prefill(client, srv.url, sizes, log)
        if "decode" not in skip:
            record["decode"] = phase_decode(client, srv.url, args.decode_rounds, log)
        if "decision" not in skip:
            record["decision"] = phase_decision(client, srv.url, args.decision_rounds, log)
        if "cancel" not in skip:
            record["cancel"] = phase_cancel(client, srv.url, srv, log)
        if "stability" not in skip:
            record["stability"] = phase_stability(client, srv.url, args.stability_rounds, log)
        record["end"] = srv.snapshot()
        record["healthy_end"] = srv.healthy()
    except Exception as e:  # noqa: BLE001
        record["fatal"] = f"{type(e).__name__}: {e}"
        log(f"FATAL {record['fatal']}")
    finally:
        srv.stop()
        record["vram_dedicated_after_stop_mib"] = gpu_dedicated_mib()
        record["log"] = log_lines
        out_path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        log(f"wrote {out_path}")


if __name__ == "__main__":
    main()
