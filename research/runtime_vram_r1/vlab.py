"""URI-RUNTIME-VRAM-R1 lab: launch one Qwen3.6 llama-server profile on a lab port under the GPU lease, account for
every device buffer, measure residency and speed, stop it.

Adapted from research/qwen38/qlab.py (branch research/qwen38-27b-brain-20261016 @9689a666) with three changes:
  * the GPU lease is held for the server's whole life (purpose "benchmark", declared expected_vram_mib, max_hold_s);
  * buffer accounting also counts the vision projector weights ("load_hparams: model size" after "CLIP using
    Vulkan0") and the CLIP compute buffer, and counts a re-reserved compute buffer of the same context once. qlab's
    parser missed the projector weights, so its "request" for vision-on-GPU profiles was ~858 MiB low;
  * a demotion estimate: device request minus process dedicated residency (positive = device buffers not resident).

Isolation: never port 18470, never edits local_brain.json or the freeze record, never runs while another llama-server
runs or another holder has the lease. Artifacts are opened read-only by llama-server (the frozen binary and the pinned
Qwen3.6 GGUF files on the NVMe copies, see memory brain-model-on-ssd-junction).
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from uri_operational_intelligence import gpu_lease  # noqa: E402

EVIDENCE = HERE / "evidence"
B11425 = r"D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\llama-server.exe"
LAB_PORT = 18572
FROZEN_PORT = 18470
MIN_SYSTEM_AVAILABLE_MIB = 3000
Q36 = Path(r"C:\uri-model-lab\models\unsloth__Qwen3.6-35B-A3B-GGUF")
MODEL = str(Q36 / "Qwen3.6-35B-A3B-UD-IQ3_S.gguf")
MMPROJ = str(Q36 / "mmproj-F16.gguf")
MTP = r"C:\uri-model-lab\mtp\mtp-qwen36-35b-a3b-Q4_K_M.gguf"


@dataclasses.dataclass
class Profile:
    name: str
    ctx: int = 32768
    ctk: str = "q8_0"
    mtp: bool = True
    mtp_n: int = 2
    vision: str = "gpu"        # off | gpu | cpu
    draft_kv: str = ""         # "" = llama.cpp default (f16) ; else -ctkd/-ctvd type
    b: int = 2048
    ub: int = 1024
    cache_ram: int = 2048
    ckpt: int = 16
    extra: tuple = ()
    env: tuple = ()            # (("NAME", "value"), ...)
    port: int = LAB_PORT

    def argv(self):
        """Frozen argv shape (runtime_v1.expected_argv) with only ctx / vision / MTP / draft-KV varied."""
        a = [B11425, "-m", MODEL, "-c", str(self.ctx), "-ngl", "999", "-fa", "on",
             "-ctk", self.ctk, "-ctv", self.ctk, "-np", "1", "--host", "127.0.0.1", "--port", str(self.port),
             "--jinja", "--reasoning-format", "deepseek", "--no-webui", "--load-mode", "none",
             "--cache-ram", str(self.cache_ram)]
        if self.vision == "off":
            a += ["--no-mmproj"]
        else:
            a += ["--mmproj", MMPROJ]
            if self.vision == "cpu":
                a += ["--no-mmproj-offload"]
        a += ["-b", str(self.b), "-ub", str(self.ub), "--slot-prompt-similarity", "0",
              "--checkpoint-min-step", "512", "--ctx-checkpoints", str(self.ckpt)]
        if self.mtp:
            a += ["-md", MTP, "--spec-type", "draft-mtp", "--spec-draft-n-max", str(self.mtp_n),
                  "-otd", "token_embd.weight=CPU"]
            if self.draft_kv:
                a += ["-ctkd", self.draft_kv, "-ctvd", self.draft_kv]
        return a + ["--metrics", "-lv", "4"] + list(self.extra)


# ------------------------------------------------------------------------------------------------ GPU counters
def _ps(cmd, timeout=40):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                          timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout


def process_gpu_mib(pid):
    out = _ps(("$d=(Get-Counter '\\GPU Process Memory(pid_%d_*)\\Dedicated Usage' -EA SilentlyContinue).CounterSamples;"
               "$n=(Get-Counter '\\GPU Process Memory(pid_%d_*)\\Non Local Usage' -EA SilentlyContinue).CounterSamples;"
               "'{0} {1}' -f ($d|Measure CookedValue -Sum).Sum,($n|Measure CookedValue -Sum).Sum") % (pid, pid))
    try:
        d, n = (float(x) / 2**20 for x in out.split())
        return {"dedicated_mib": round(d, 1), "non_local_mib": round(n, 1)}
    except ValueError:
        return {"dedicated_mib": None, "non_local_mib": None}


def census_brief():
    c = gpu_lease.census()
    if not c.get("ok"):
        return {"ok": False}
    return {"ok": True, "adapter_dedicated_mib": c.get("adapter_dedicated_mib"), "attributed_mib": c.get("attributed_mib"),
            "unattributed_mib": c.get("unattributed_mib"),
            "free_for_one_process_mib": round(c["card_mib"] - c.get("attributed_mib", 0) - c.get("unattributed_mib", 0), 1),
            "processes": [{k: p.get(k) for k in ("pid", "name", "dedicated_mib", "non_local_mib")}
                          for p in c.get("processes", []) if (p.get("dedicated_mib") or 0) >= 30]}


def llama_servers():
    return [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "llama-server.exe"]


# ------------------------------------------------------------------------------------------------ buffer accounting
def account(log_text):
    """Device (Vulkan0) and host-visible (Vulkan_Host) buffers by component, from llama-server's own log lines.

    Components: main weights / KV / recurrent state / compute; draft (MTP) weights / KV / compute; vision weights /
    vision compute. A compute buffer re-reserved for the same context at the same size is counted once (the
    scheduler reuses the buffer)."""
    phase = "main"
    seen_compute = {}
    dev, host, rows = {}, {}, []
    clip_backend = None
    for line in log_text.splitlines():
        if "loading draft model" in line:
            phase = "draft"
        elif "clip_model_loader" in line and phase != "vision":
            phase = "vision"
        elif "adding speculative implementation" in line:
            phase = "draft_reserve"
        m = re.search(r"CLIP using (\S+) backend", line)
        if m:
            clip_backend = m.group(1)
        m = re.search(r"([\w:]+):\s+(Vulkan0|Vulkan_Host|CPU)\s+(\w*)\s*buffer size\s*=\s*([\d.]+) MiB", line)
        if m:
            where, kind, what, mib = m.group(1), m.group(2), m.group(3) or "?", float(m.group(4))
            ph = "draft" if phase == "draft_reserve" else phase
            comp = f"{ph}.{what}"
            if what == "compute":
                key = (ph, kind)
                if seen_compute.get(key) == mib:
                    continue          # same-size re-reserve of the same context
                seen_compute[key] = max(seen_compute.get(key, 0), mib)
            target = dev if kind == "Vulkan0" else host
            target[comp] = round(target.get(comp, 0) + mib, 2)
            rows.append({"phase": ph, "kind": kind, "what": what, "mib": mib})
            continue
        m = re.search(r"load_hparams: model size:\s+([\d.]+) MiB", line)
        if m:
            mib = float(m.group(1))
            target = dev if (clip_backend or "").startswith("Vulkan") else host
            target["vision.model"] = round(target.get("vision.model", 0) + mib, 2)
            rows.append({"phase": "vision", "kind": clip_backend, "what": "model", "mib": mib})
    return {"device_mib": dev, "device_total_mib": round(sum(dev.values()), 1),
            "host_visible_mib": host, "host_total_mib": round(sum(host.values()), 1),
            "clip_backend": clip_backend, "rows": rows}


# ------------------------------------------------------------------------------------------------ server
class Server:
    def __init__(self, profile: Profile, run_dir: Path, max_hold_s=900, expected_mib=None):
        self.p, self.dir = profile, run_dir
        self.proc = self.lease = None
        self.max_hold_s, self.expected_mib = max_hold_s, expected_mib
        self.log_path = run_dir / f"server_{profile.name}.log"
        self.record = {"profile": dataclasses.asdict(profile), "argv": profile.argv(), "classification": "STARTED"}

    @property
    def url(self):
        return f"http://127.0.0.1:{self.p.port}"

    def start(self, timeout=600):
        if self.p.port == FROZEN_PORT:
            raise RuntimeError("REFUSED_FROZEN_PORT")
        if llama_servers():
            raise RuntimeError(f"REFUSED_OTHER_LLAMA_SERVER_RUNNING {llama_servers()}")
        avail = psutil.virtual_memory().available / 2**20
        if avail < MIN_SYSTEM_AVAILABLE_MIB:
            # host RAM guard: the server needs ~2-4 GiB resident (weights staging, prompt cache up to cache_ram)
            self.record["classification"] = "BLOCKED"
            raise RuntimeError(f"BLOCKED_HOST_RAM available={avail:.0f} MiB")
        self.lease = gpu_lease.acquire("benchmark", label=f"URI-RUNTIME-VRAM-R1 {self.p.name}",
                                       session=str(REPO), expected_vram_mib=self.expected_mib,
                                       max_hold_s=self.max_hold_s, wait_s=0)
        self.record["lease"] = {k: self.lease.record.get(k) for k in ("acquired_at", "label", "max_hold_s", "pid")}
        self.record["release_wait"] = wait_vram_released()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record["before"] = census_brief()
        self.record["before"]["system_available_mib"] = round(psutil.virtual_memory().available / 2**20)
        env = dict(os.environ)
        env.update(dict(self.p.env))
        log = open(self.log_path, "wb")
        t0 = time.monotonic()
        self.proc = subprocess.Popen(self.p.argv(), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                self.record["classification"] = "FAILED"
                self.record["failed"] = f"EXITED rc={self.proc.returncode}"
                self.record["log_tail"] = self.log_path.read_text(errors="replace")[-3000:]
                raise RuntimeError(self.record["failed"])
            try:
                if httpx.get(self.url + "/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        else:
            self.record["classification"] = "TIMED_OUT"
            self.stop()
            raise TimeoutError("NOT_HEALTHY")
        self.record["load_seconds"] = round(time.monotonic() - t0, 2)
        time.sleep(3)
        self.record["buffers"] = account(self.log_path.read_text(errors="replace"))
        self.record["loaded"] = self.memory()
        self.record["loaded_census"] = census_brief()   # who yielded memory while the server loaded
        self.record["props"] = self.props()
        return self

    def memory(self):
        snap = {"t": round(time.time(), 1), "server": process_gpu_mib(self.proc.pid)}
        req = (self.record.get("buffers") or {}).get("device_total_mib")
        d = snap["server"].get("dedicated_mib")
        if req and d is not None:
            snap["not_resident_mib"] = round(req - d, 1)
        try:
            snap["server_private_mib"] = round(psutil.Process(self.proc.pid).memory_info().private / 2**20, 1)
        except psutil.Error:
            pass
        snap["system_available_mib"] = round(psutil.virtual_memory().available / 2**20)
        return snap

    def props(self):
        try:
            p = httpx.get(self.url + "/props", timeout=10).json()
            g = p.get("default_generation_settings") or {}
            return {"model_path": p.get("model_path"), "build_info": p.get("build_info"), "n_ctx": g.get("n_ctx"),
                    "modalities": p.get("modalities")}
        except (httpx.HTTPError, ValueError):
            return {}

    def tokenize(self, text):
        return len(httpx.post(self.url + "/tokenize", json={"content": text}, timeout=120).json()["tokens"])

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)
        self.record["stopped"] = round(time.time(), 1)
        if self.lease is not None:
            self.lease.release("benchmark done")
            self.lease = None


def wait_vram_released(timeout=90, poll=2.0):
    """Wait until no process holds more than 2 GiB dedicated (a previous server's memory is released; release lags
    process exit, R1 finding). Returns the seconds waited and the last census figure."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        c = gpu_lease.census()
        big = [p for p in c.get("processes", []) if (p.get("dedicated_mib") or 0) > 2048]
        if c.get("ok") and not big:
            return {"waited_s": round(time.monotonic() - t0, 1), "attributed_mib": c.get("attributed_mib")}
        time.sleep(poll)
    return {"waited_s": round(time.monotonic() - t0, 1), "timeout": True}


def save(run_dir: Path, name, data):
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / f"{name}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p
