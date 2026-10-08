"""Crash-resilient experiment queue for the URI Engine research (research only, no Core changes).

Why: the 2026-10-06 PC crash (Kernel-Power 41, no bugcheck) interrupted a chain of shell scripts whose only
completion signal was an ALL_DONE marker in a scratch file. Recovering the state meant re-deriving it from
file timestamps. This runner keeps a manifest on disk so that "what completed" is never in doubt.

  python model_lab/uri_engine/queue_runner.py --init        # create the manifest from QUEUE (no-op if present)
  python model_lab/uri_engine/queue_runner.py --status      # table
  python model_lab/uri_engine/queue_runner.py --run         # run every pending entry in order
  python model_lab/uri_engine/queue_runner.py --run --retry # also re-run failed/interrupted/timed_out entries
  python model_lab/uri_engine/queue_runner.py --block ID "reason" / --unblock ID / --skip ID

Guarantees per entry: the manifest is rewritten atomically (tmp + os.replace) before the command starts
(status=running, start timestamp, attempt count, host free RAM/VRAM) and after it ends (exit code, end
timestamp, required outputs verified to exist, be newer than the start and parse as JSON, sha256 of the
model and of the llama-server binary used). An entry is "done" only when all of that holds. On startup any
entry still marked "running" is re-marked "interrupted" (the previous process cannot have survived a crash).
A silence watchdog kills a llama-server whose newest server log has not grown for --silence seconds (the
stock ngram-mod hang of 2026-10-06), and a hard per-entry timeout kills the whole entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import psutil  # noqa: E402

from lab.runtime import file_sha256, gpu_dedicated_mib, gpu_util_pct  # noqa: E402

EVID = LAB / "evidence" / "uri_engine"
MANIFEST = EVID / "queue_manifest.json"
LOGS = EVID / "queue_logs"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
MODEL = CFG["model"]["path"]
RELEASE = CFG["runtime"]["binary"]
STOCK = "D:/uri-model-lab/build/stock/bin/llama-server.exe"
UX = "D:/uri-model-lab/build/rsseq/bin/llama-server.exe"
STOCK2 = "D:/uri-model-lab/build/stock2/bin/llama-server.exe"   # rebuilt with Vulkan SDK 1.4.363.0 glslc (coopmat / int-dot)
UX2 = "D:/uri-model-lab/build/rsseq2/bin/llama-server.exe"
PROD = "-b 2048 -ub 1024 --cache-ram 1024"
MTP = "D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
MM = CFG["model"]["mmproj"]
# Runtime v1 candidate flags (stock): cache-aware context layout "final" + always-save prompt cache + 16 checkpoints
CAND = "-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16"
CAND_MTP = f"{CAND} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"

def ctx(name, extra, binary=None, layout="single", timeout=2400):
    cmd = [PY, "model_lab/uri_engine/bench_context_reuse.py", "--name", name, "--extra", extra, "--layout", layout]
    if binary:
        cmd += ["--binary", binary]
    return {"id": name, "group": "context_reuse", "cmd": cmd, "binary": binary or RELEASE, "timeout_s": timeout,
            "required_outputs": [f"model_lab/evidence/uri_engine/context_reuse/{name}_*.json"]}

def uri(name, extra, binary=None, more=(), timeout=1500):
    cmd = [PY, "model_lab/uri_engine/bench_uri.py", "--name", name, "--extra", extra, *more]
    if binary:
        cmd += ["--binary", binary]
    return {"id": name, "group": "bench_uri", "cmd": cmd, "binary": binary or RELEASE, "timeout_s": timeout,
            "required_outputs": [f"model_lab/evidence/uri_engine/runs/{name}_*.json"]}

def spec(name, extra, binary=None, more=(), timeout=1500):
    cmd = [PY, "model_lab/uri_engine/bench_spec.py", "--name", name, "--extra", extra, *more]
    if binary:
        cmd += ["--binary", binary]
    return {"id": name, "group": "bench_spec", "cmd": cmd, "binary": binary or RELEASE, "timeout_s": timeout,
            "required_outputs": [f"model_lab/evidence/uri_engine/spec/{name}.json"]}

def suite(name, extra, ctx_n, lsizes, timeout=3600, suites="F,D,DG,C,H,S,O,R,RH,L,P,V"):
    cmd = [PY, "model_lab/run_bench.py", "--name", f"ue_{name}", "--model", MODEL, "--mmproj", MM, "--family", "qwen",
           "--ctx", str(ctx_n), "--ngl", "999", "--paths", "fast", "--suites", suites, "--l-sizes", lsizes,
           "--extra", extra, "--port", "18481"]
    return {"id": f"ue_{name}", "group": "correctness", "cmd": cmd, "binary": RELEASE, "timeout_s": timeout,
            "required_outputs": [f"model_lab/evidence/runs/ue_{name}/*/summary.json"]}

# The post-crash queue: only experiments that were missing, interrupted or invalid on 2026-10-06 13:50,
# ordered by the research priority (prefix/state reuse first, speculative decoding last).
QUEUE = [
    {"id": "freeze_start", "group": "safety", "cmd": [PY, "model_lab/verify_freeze.py"], "timeout_s": 300,
     "stdout_to": "model_lab/evidence/uri_engine/freeze_check_recovery_start.json",
     "required_outputs": ["model_lab/evidence/uri_engine/freeze_check_recovery_start.json"]},
    {"id": "determinism_probe", "group": "correctness", "cmd": [PY, "model_lab/uri_engine/determinism_probe.py"],
     "binary": RELEASE, "timeout_s": 1500, "required_outputs": ["model_lab/evidence/uri_engine/determinism_probe.json"]},
    ctx("ctx_control", "-b 2048 -ub 1024 --cache-ram 0 --ctx-checkpoints 0"),
    ctx("ctx_prod", PROD),
    ctx("ctx_prod_split", PROD, layout="split"),
    ctx("ctx_ckpt1024", PROD + " --checkpoint-min-step 1024 --ctx-checkpoints 16"),
    # ctx_prod evicted the 16k/30k A state after D/E ("making room for prompt cache entry, removing oldest entry (543 MiB)"):
    # does a larger host-RAM prompt cache keep A_after_E cheap?
    ctx("ctx_cache4096", "-b 2048 -ub 1024 --cache-ram 4096"),
    # stock mechanism, URI-side prompt shaping: evidence as 4 acknowledged user messages -> a checkpoint before each part
    ctx("ctx_prod_multi", PROD, layout="multi"),
    # ctx_prod_multi showed that user-start checkpoints closer than --checkpoint-min-step (default 8192) to the previous
    # one are skipped (server-context.cpp: pos > checkpoints.back().n_tokens + checkpoint_min_step), so the 16k parts
    # got no boundary checkpoint. Stock flags only: multi layout + min-step 512 + always-save + 4 GiB cache.
    ctx("ctx_prod_multi_ms512", "-b 2048 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 32", layout="multi"),
    # stock mechanism: server-context.cpp saves the slot state to the prompt cache only when the next prompt keeps
    # < 50% of it (f_keep); on a hybrid model the partially kept state is unusable past the last checkpoint, so the
    # A state is lost before D. --slot-prompt-similarity 0 forces the LRU path, which always saves before loading.
    ctx("ctx_sim0_cache4096", "-b 2048 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0"),
    # best-candidate combination on the patched build: fine checkpoints + always-save + larger cache + split layout.
    # ctx_ux_fine1024 (8 checkpoints, min-step 512) lost the system-boundary checkpoint at 16k/30k (ring eviction),
    # so the budget here covers the whole 32k context: 32 checkpoints x 1024-token spacing (~63 MiB host RAM each).
    ctx("ctx_ux_best_split", "-b 1024 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 32",
        binary=UX, layout="split"),
    # ctx_ux_best_split was mis-configured: the patch enables fine checkpoints only when min-step < n_ubatch (1024 < 1024
    # is false), so D did not improve there. Corrected: ub 2048 with min-step 1024 -> a checkpoint at every 2048-token
    # ubatch boundary, 32 of them cover the whole 32k context without evicting the system boundary.
    ctx("ctx_ux_best2_split", "-b 2048 -ub 2048 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 32",
        binary=UX, layout="split"),
    ctx("ctx_sb_prod", PROD, binary=STOCK),
    ctx("ctx_ux_fine1024", "-b 1024 -ub 1024 --cache-ram 1024 --checkpoint-min-step 512 --ctx-checkpoints 8", binary=UX),
    ctx("ctx_ux_fine512", "-b 512 -ub 512 --cache-ram 1024 --checkpoint-min-step 256 --ctx-checkpoints 16", binary=UX),
    {"id": "determinism_probe2", "group": "correctness", "cmd": [PY, "model_lab/uri_engine/determinism_probe2.py"],
     "binary": RELEASE, "timeout_s": 1500, "required_outputs": ["model_lab/evidence/uri_engine/determinism_probe2.json"]},
    uri("uri_base_16k", PROD, more=("--ctx", "16384", "--skip", "long,vision")),
    uri("uri_mtp3_16k", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU",
        more=("--ctx", "16384", "--skip", "long,vision")),
    suite("base16k", PROD, 16384, "4000,12000"),
    suite("mtp3_16k", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU", 16384, "4000,12000"),
    suite("base16k_rep", PROD, 16384, "4000,12000"),
    spec("mtp2_32k_vision", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU", more=("--ctx", "32768", "--repeats", "1")),
    spec("mtp3_24k_vision", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 3 -otd token_embd.weight=CPU", more=("--ctx", "24576", "--repeats", "1")),
    spec("mtp2_16k_vision", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU", more=("--ctx", "16384", "--repeats", "1")),
    spec("mtp4_16k_vision", f"{PROD} -md {MTP} --spec-type draft-mtp --spec-draft-n-max 4 -otd token_embd.weight=CPU", more=("--ctx", "16384", "--repeats", "1")),
    {"id": "stream_overhead", "group": "overhead", "cmd": [PY, "model_lab/uri_engine/stream_overhead.py"], "binary": RELEASE,
     "timeout_s": 900, "required_outputs": ["model_lab/evidence/uri_engine/stream_overhead.json"]},
    # stream_overhead found ~0.22 s between non-streaming wall and streamed TTFT; this splits client vs server
    {"id": "stream_probe2", "group": "overhead", "cmd": [PY, "model_lab/uri_engine/stream_probe2.py"], "binary": RELEASE,
     "timeout_s": 900, "required_outputs": ["model_lab/evidence/uri_engine/stream_probe2.json"]},
    uri("sb_prod_canon", PROD, binary=STOCK, more=("--serial", "canonical", "--skip", "long,vision,decode")),
    uri("ux_prod_canon", PROD, binary=UX, more=("--serial", "canonical", "--skip", "long,vision,decode")),
    uri("uri_ngram_simple", f"{PROD} --spec-type ngram-simple --spec-ngram-simple-size-n 12 --spec-ngram-simple-size-m 8 --spec-draft-n-max 8",
        more=("--skip", "long,vision")),
    # Blocked until the crash risk is understood: ngram-mod on the hybrid model hung the stock server at 11:46-12:05
    # and the machine stopped ~55 s into the next ngram-mod run (uri_ngram_mod16). Cause unknown; correlation only.
    {**uri("uri_ngram_mod16", f"{PROD} --spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 8 --spec-ngram-mod-n-max 16",
           more=("--skip", "long,vision")), "status": "blocked",
     "block_reason": "identical settings to the run in progress at the crash (stock ngram-mod on a hybrid model); needs user decision"},
    {**spec("ux_ngram_mod8", f"{PROD} --spec-type ngram-mod --spec-ngram-mod-n-match 16 --spec-ngram-mod-n-min 4 --spec-ngram-mod-n-max 8 --spec-draft-n-max 8",
            binary=UX), "status": "blocked",
     "block_reason": "n-gram speculation on the hybrid model (patched rs-seq path); crash-adjacent class, needs user decision"},
    {"id": "freeze_end", "group": "safety", "cmd": [PY, "model_lab/verify_freeze.py"], "timeout_s": 300,
     "stdout_to": "model_lab/evidence/uri_engine/freeze_check_recovery_end.json",
     "required_outputs": ["model_lab/evidence/uri_engine/freeze_check_recovery_end.json"]},
    # ---- Final closure milestone (pass 4): fair builds, final layout, candidate qualification, soak -------------
    ctx("ctx_sb2_prod", PROD, binary=STOCK2),                       # parity of the SDK-built stock binary with the release binary
    ctx("ctx_rel_final", CAND, layout="final"),                     # release binary, candidate flags, final layout
    ctx("ctx_sb2_final", CAND, binary=STOCK2, layout="final"),      # SDK-built stock, same
    ctx("ctx_ux2_final", "-b 2048 -ub 2048 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 16",
        binary=UX2, layout="final"),                                # SDK-built patched: ubatch-granular checkpoints
    ctx("ctx_ux2_final_ub1024", "-b 1024 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 32",
        binary=UX2, layout="final"),                                # patched, finer (32 x 1024)
    suite("cand", CAND, 32768, "4000,12000,28000"),                 # candidate, no MTP, 32k + vision, fast path, all suites incl. V
    suite("cand_mtp2", CAND_MTP, 32768, "4000,12000,28000"),        # candidate + MTP n_max 2
    {"id": "ue_cand_normal", "group": "correctness", "cmd": [PY, "model_lab/run_bench.py", "--name", "ue_cand_normal", "--model", MODEL, "--mmproj", MM,
     "--family", "qwen", "--ctx", "32768", "--ngl", "999", "--paths", "normal", "--suites", "R,RH", "--extra", CAND, "--port", "18481"],
     "binary": RELEASE, "timeout_s": 3600, "required_outputs": ["model_lab/evidence/runs/ue_cand_normal/*/summary.json"]},
    {"id": "ue_cand_mtp2_normal", "group": "correctness", "cmd": [PY, "model_lab/run_bench.py", "--name", "ue_cand_mtp2_normal", "--model", MODEL, "--mmproj", MM,
     "--family", "qwen", "--ctx", "32768", "--ngl", "999", "--paths", "normal", "--suites", "R,RH", "--extra", CAND_MTP, "--port", "18481"],
     "binary": RELEASE, "timeout_s": 3600, "required_outputs": ["model_lab/evidence/runs/ue_cand_mtp2_normal/*/summary.json"]},
    uri("uri_cand_mtp2", CAND_MTP, more=("--skip", "long")),         # decision-turn latency of the exact candidate (vision cases on)
    {"id": "soak_final", "group": "stability", "cmd": [PY, "model_lab/uri_engine/soak_final.py", "--minutes", "75"], "binary": RELEASE,
     "timeout_s": 7200, "required_outputs": ["model_lab/evidence/uri_engine/soak_final.json"]},
    {"id": "freeze_final_v1", "group": "safety", "cmd": [PY, "model_lab/verify_freeze.py"], "timeout_s": 300,
     "stdout_to": "model_lab/evidence/uri_engine/freeze_check_runtime_v1.json",
     "required_outputs": ["model_lab/evidence/uri_engine/freeze_check_runtime_v1.json"]},
    # the production integration adapter itself (local_brain.py with the persistent BrainClient) on the pinned v1
    # config from local_brain.json: real Phase 1 paired loop 12/12 + tiers + vision + 60-call soak
    {"id": "prove_v1", "group": "correctness", "cmd": [PY, "model_lab/integration/prove_integration.py", "60"], "binary": RELEASE,
     "timeout_s": 2400, "required_outputs": ["model_lab/evidence/integration_proof.json"]},
    {"id": "freeze_after_prove_v1", "group": "safety", "cmd": [PY, "model_lab/verify_freeze.py"], "timeout_s": 300,
     "stdout_to": "model_lab/evidence/uri_engine/freeze_check_after_prove_v1.json",
     "required_outputs": ["model_lab/evidence/uri_engine/freeze_check_after_prove_v1.json"]},
]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def atomic_write(path: Path, obj):
    """tmp + fsync + os.replace: after the 2026-10-06 14:25 freeze the runner's lock file held 4 NUL bytes (NTFS had
    allocated the cluster but the data never reached the disk), so every manifest write is fsynced before the rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, indent=1))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def boot_time():
    return dt.datetime.fromtimestamp(psutil.boot_time()).isoformat(timespec="seconds")


def server_proc_stats():
    rss = cpu = None
    for p in llama_procs():
        try:
            rss = round(p.memory_info().rss / 2**20)
            cpu = round(p.cpu_percent(None) / psutil.cpu_count(), 1)
        except Exception:
            pass
    return rss, cpu


GPU_PS = (
    "$ErrorActionPreference='SilentlyContinue'; while ($true) { "
    "$m=(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum; "
    "$u=((Get-Counter '\\GPU Engine(*engtype_Compute*)\\Utilization Percentage','\\GPU Engine(*engtype_3D*)\\Utilization Percentage').CounterSamples | Measure-Object -Property CookedValue -Sum).Sum; "
    "Write-Output ('{0},{1}' -f [math]::Round($m/1MB,1), [math]::Round([math]::Min(100,$u),1)); "
    "[Console]::Out.Flush(); Start-Sleep -Seconds %d }"
)


def telemetry_loop(path: Path, stop: threading.Event, interval: float):
    """Host telemetry flushed + fsynced every sample so a hard freeze leaves the last VRAM/RAM state on disk.
    Columns: time, free_ram_mib, vram_dedicated_mib, gpu_util_pct, server_rss_mib, server_cpu_pct_of_machine, n_llama_procs.
    The GPU counters come from ONE long-lived PowerShell child (the first version spawned two PowerShell processes per
    sample, ~0.1 s of client-side latency per request on the 19:00-20:00 runs; see the research report, section 2)."""
    ps = None
    try:
        ps = subprocess.Popen(["powershell", "-NoProfile", "-Command", GPU_PS % max(1, int(interval))],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        ps = None
    latest = {"vram": None, "util": None}

    def reader():
        try:
            for line in ps.stdout:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    try:
                        latest["vram"], latest["util"] = float(parts[0]), float(parts[1])
                    except ValueError:
                        pass
        except Exception:
            pass

    if ps:
        threading.Thread(target=reader, daemon=True).start()
    with open(path, "w", encoding="utf-8") as f:
        f.write("time,free_ram_mib,vram_dedicated_mib,gpu_util_pct,server_rss_mib,server_cpu_pct,n_llama_procs\n")
        f.flush()
        os.fsync(f.fileno())
        for p in llama_procs():
            try:
                p.cpu_percent(None)
            except Exception:
                pass
        while not stop.is_set():
            rss, cpu = server_proc_stats()
            row = [now(), round(psutil.virtual_memory().available / 2**20), latest["vram"], latest["util"], rss, cpu, len(llama_procs())]
            f.write(",".join("" if v is None else str(v) for v in row) + "\n")
            f.flush()
            os.fsync(f.fileno())
            stop.wait(interval)
    if ps:
        try:
            ps.kill()
        except Exception:
            pass


def last_telemetry(path):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").strip().splitlines()
        if len(lines) < 2:
            return None
        hdr, last = lines[0].split(","), lines[-1].split(",")
        return {"samples": len(lines) - 1, "last": dict(zip(hdr, last))}
    except Exception:
        return None


def load():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def llama_procs():
    out = []
    for p in psutil.process_iter(["name", "pid", "create_time"]):
        if (p.info["name"] or "").lower() == "llama-server.exe":
            out.append(p)
    return out


def newest_server_log():
    files = [Path(f) for f in glob.glob(str(EVID / "**" / "server_*.log"), recursive=True)]
    files += [Path(f) for f in glob.glob(str(LAB / "evidence" / "runs" / "ue_*" / "*" / "server_*.log"))]
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


def binary_hashes(binary):
    if not binary:
        return None
    b = Path(binary)
    out = {}
    for f in [b] + [b.parent / n for n in ("llama-server-impl.dll", "llama.dll", "ggml-vulkan.dll", "ggml-base.dll")]:
        if f.exists():
            out[f.name] = file_sha256(f)
    return out


def check_outputs(entry, started):
    details = []
    ok = True
    for pat in entry.get("required_outputs", []):
        matches = sorted(glob.glob(str(ROOT / pat)), key=os.path.getmtime)
        fresh = [m for m in matches if os.path.getmtime(m) >= started - 1]
        if not fresh:
            ok = False
            details.append({"pattern": pat, "ok": False, "reason": "no file newer than start"})
            continue
        f = fresh[-1]
        d = {"pattern": pat, "file": os.path.relpath(f, ROOT), "size": os.path.getsize(f)}
        if f.endswith(".json"):
            try:
                json.loads(Path(f).read_text(encoding="utf-8-sig"))
                d["ok"] = True
            except Exception as exc:
                d["ok"] = False
                d["reason"] = f"invalid JSON: {exc}"
                ok = False
        else:
            d["ok"] = True
        details.append(d)
    return ok, details


def kill_tree(proc):
    try:
        parent = psutil.Process(proc.pid)
        for c in parent.children(recursive=True):
            c.kill()
        parent.kill()
    except Exception:
        pass


def run_entry(m, e, silence_s):
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log = LOGS / f"{e['id']}_{stamp}.log"
    telem = LOGS / f"telemetry_{e['id']}_{stamp}.csv"
    e.update({"status": "running", "start": now(), "attempts": e.get("attempts", 0) + 1, "log": os.path.relpath(log, ROOT),
              "telemetry": os.path.relpath(telem, ROOT), "boot_time": boot_time(),
              "host_before": {"free_ram_mib": round(psutil.virtual_memory().available / 2**20), "vram_mib": gpu_dedicated_mib()},
              "model_sha256": file_sha256(MODEL), "binary_sha256": binary_hashes(e.get("binary"))})
    for k in ("end", "exit_code", "elapsed_s", "outputs", "host_after", "last_telemetry", "telemetry_summary"):
        e.pop(k, None)
    atomic_write(MANIFEST, m)
    started = time.time()
    tstop = threading.Event()
    tth = threading.Thread(target=telemetry_loop, args=(telem, tstop, 3.0), daemon=True)
    tth.start()
    stdout_to = e.get("stdout_to")
    out_f = open(ROOT / stdout_to, "w", encoding="utf-8") if stdout_to else open(log, "w", encoding="utf-8", errors="replace")
    err_f = open(log, "w", encoding="utf-8", errors="replace") if stdout_to else subprocess.STDOUT
    proc = subprocess.Popen(e["cmd"], cwd=str(ROOT), stdout=out_f, stderr=err_f)
    events = []
    stop = threading.Event()

    def watchdog():
        while not stop.is_set():
            if time.time() - started > e.get("timeout_s", 3600):
                events.append({"t": now(), "event": "timeout", "detail": f"> {e.get('timeout_s')} s"})
                for p in llama_procs():
                    p.kill()
                kill_tree(proc)
                return
            f = newest_server_log()
            if f and f.stat().st_mtime > started and llama_procs():
                age = time.time() - f.stat().st_mtime
                if age > silence_s:
                    for p in llama_procs():
                        events.append({"t": now(), "event": "watchdog_kill", "detail": f"llama-server pid {p.pid} silent {int(age)} s on {f.name}"})
                        p.kill()
                    time.sleep(10)
            stop.wait(15)

    th = threading.Thread(target=watchdog, daemon=True)
    th.start()
    rc = proc.wait()
    stop.set()
    th.join(timeout=5)
    tstop.set()
    tth.join(timeout=10)
    out_f.close()
    if stdout_to:
        err_f.close()
    time.sleep(2)
    for p in llama_procs():  # never leave an experimental server behind
        events.append({"t": now(), "event": "stale_server_killed", "detail": f"pid {p.pid}"})
        p.kill()
    ok, details = check_outputs(e, started)
    timed_out = any(ev["event"] == "timeout" for ev in events)
    tsum = last_telemetry(telem)
    peak = None
    try:
        rows = Path(telem).read_text(encoding="utf-8").strip().splitlines()[1:]
        vr = [float(r.split(",")[2]) for r in rows if r.split(",")[2]]
        fr = [float(r.split(",")[1]) for r in rows if r.split(",")[1]]
        peak = {"peak_vram_mib": max(vr) if vr else None, "min_free_ram_mib": min(fr) if fr else None, "samples": len(rows)}
    except Exception:
        pass
    e.update({"end": now(), "exit_code": rc, "elapsed_s": round(time.time() - started, 1), "outputs": details, "events": events,
              "host_after": {"free_ram_mib": round(psutil.virtual_memory().available / 2**20), "vram_mib": gpu_dedicated_mib()},
              "telemetry_summary": peak, "last_telemetry": tsum,
              "status": "timed_out" if timed_out else ("done" if rc == 0 and ok else "failed")})
    atomic_write(MANIFEST, m)
    return e["status"]


def status_table(m):
    w = max(len(e["id"]) for e in m["entries"])
    for e in m["entries"]:
        print(f"{e['id'].ljust(w)}  {e.get('status','pending'):12s} attempts={e.get('attempts',0)} start={e.get('start','-')} "
              f"end={e.get('end','-')} rc={e.get('exit_code','-')} elapsed={e.get('elapsed_s','-')} {e.get('block_reason','')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--retry", action="store_true", help="also run failed / interrupted / timed_out entries")
    ap.add_argument("--only", nargs="*", help="restrict --run to these ids")
    ap.add_argument("--block", nargs=2, metavar=("ID", "REASON"))
    ap.add_argument("--unblock")
    ap.add_argument("--skip")
    ap.add_argument("--add-missing", action="store_true", help="insert QUEUE entries that the manifest lacks (new experiments after a recovery)")
    ap.add_argument("--silence", type=int, default=420, help="kill llama-server after this many seconds without log output")
    a = ap.parse_args()
    EVID.mkdir(parents=True, exist_ok=True)
    if a.init or not MANIFEST.exists():
        if MANIFEST.exists():
            print("manifest exists; not overwriting")
        else:
            m = {"created": now(), "note": "post-crash queue (2026-10-06); see crash_recovery_20261006.json",
                 "entries": [dict({"status": "pending", "attempts": 0}, **e) for e in QUEUE]}
            atomic_write(MANIFEST, m)
            print(f"created {MANIFEST} with {len(m['entries'])} entries")
    m = load()
    changed = False
    # single-runner lock: a second instance (e.g. --status while a run is in progress) must never touch the manifest
    lock = EVID / "queue_runner.lock"
    other = None
    if lock.exists():
        try:
            other = int(lock.read_text().strip())
            if not psutil.pid_exists(other):
                other = None
        except Exception:
            other = None
    if other:
        if a.run or a.block or a.unblock or a.skip:
            print(f"another queue_runner (pid {other}) is active; read-only")
        status_table(m)
        return 3 if a.run else 0
    for e in m["entries"]:  # no runner is alive, so "running" can only be a crash leftover
        if e.get("status") == "running":
            e["status"] = "interrupted"
            ev = {"t": now(), "event": "marked_interrupted_on_startup", "boot_time_now": boot_time(), "boot_time_at_start": e.get("boot_time"),
                  "rebooted_since_start": bool(e.get("boot_time")) and e.get("boot_time") != boot_time()}
            if e.get("telemetry"):
                ev["last_telemetry"] = last_telemetry(ROOT / e["telemetry"])
            e.setdefault("events", []).append(ev)
            changed = True
    if a.block:
        for e in m["entries"]:
            if e["id"] == a.block[0]:
                e["status"], e["block_reason"], changed = "blocked", a.block[1], True
    if a.unblock:
        for e in m["entries"]:
            if e["id"] == a.unblock and e.get("status") == "blocked":
                e["status"], changed = "pending", True
                e.pop("block_reason", None)
    if a.skip:
        for e in m["entries"]:
            if e["id"] == a.skip:
                e["status"], changed = "skipped", True
    if a.add_missing:
        have = {e["id"] for e in m["entries"]}
        for i, q in enumerate(QUEUE):
            if q["id"] in have:
                continue
            prev = QUEUE[i - 1]["id"] if i else None
            pos = next((j + 1 for j, e in enumerate(m["entries"]) if e["id"] == prev), len(m["entries"]))
            m["entries"].insert(pos, dict({"status": "pending", "attempts": 0}, **q))
            have.add(q["id"])
            changed = True
            print(f"added {q['id']} at position {pos}")
    if changed:
        atomic_write(MANIFEST, m)
    if a.status or not a.run:
        status_table(m)
    if not a.run:
        return 0
    if llama_procs():
        print("refusing to start: a llama-server.exe is already running (pids %s)" % [p.pid for p in llama_procs()])
        return 2
    runnable = {"pending"} | ({"failed", "interrupted", "timed_out"} if a.retry else set())
    with open(lock, "w", encoding="utf-8") as lf:
        lf.write(str(os.getpid()))
        lf.flush()
        os.fsync(lf.fileno())
    try:
        for e in m["entries"]:
            if a.only and e["id"] not in a.only:
                continue
            if e.get("status", "pending") not in runnable:
                continue
            print(f"=== {now()} START {e['id']}: {' '.join(e['cmd'])}", flush=True)
            st = run_entry(m, e, a.silence)
            print(f"=== {now()} END {e['id']}: {st} rc={e.get('exit_code')} elapsed={e.get('elapsed_s')} s", flush=True)
    finally:
        lock.unlink(missing_ok=True)
    status_table(m)
    print("QUEUE_FINISHED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
