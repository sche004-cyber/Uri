"""Launch and measure a local llama-server (llama.cpp) instance for benchmarking.

Nothing here touches URI Core. A ServerConfig fully describes one runtime configuration so a
benchmark result can be reproduced from its evidence record.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import httpx
import psutil

LAB = Path(os.environ.get("URI_MODEL_LAB", r"D:\uri-model-lab"))
VULKAN = LAB / "runtime" / "llama-b11425-bin-win-vulkan-x64" / "llama-server.exe"


@dataclasses.dataclass
class ServerConfig:
    name: str
    model: str                      # path to the GGUF
    ctx: int = 16384
    ngl: int = 999
    n_cpu_moe: int = 0
    cache_k: str = "q8_0"
    cache_v: str = "q8_0"
    flash_attn: str = "on"
    parallel: int = 1
    port: int = 18480
    mmproj: str | None = None
    load_mode: str = "none"    # mmap keeps a full host copy resident; "none" frees it after upload
    extra: tuple = ()
    binary: str = os.environ.get("URI_LAB_BINARY", str(VULKAN))   # research override: a self-built llama-server

    def argv(self):
        a = [self.binary, "-m", self.model, "-c", str(self.ctx)]
        # ngl < 0: let llama.cpp --fit choose GPU layers / CPU-resident MoE experts for this device.
        a += ["--fit", "on", "--fit-ctx", str(self.ctx)] if self.ngl < 0 else ["-ngl", str(self.ngl)]
        a += ["-fa", self.flash_attn, "-ctk", self.cache_k, "-ctv", self.cache_v,
             "-np", str(self.parallel), "--port", str(self.port), "--host", "127.0.0.1",
             "--jinja", "--reasoning-format", "deepseek", "--metrics", "--no-webui", "--load-mode", self.load_mode]
        if self.n_cpu_moe:
            a += ["--n-cpu-moe", str(self.n_cpu_moe)]
        if self.mmproj:
            a += ["--mmproj", self.mmproj]
        else:
            a += ["--no-mmproj"]
        return a + list(self.extra)


def gpu_dedicated_mib():
    """Total dedicated VRAM in use on the adapter (Windows perf counter, vendor-neutral)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | "
             "Measure-Object -Property CookedValue -Maximum | Select-Object -ExpandProperty Maximum"],
            capture_output=True, text=True, timeout=20)
        return round(float(out.stdout.strip()) / 2**20, 1)
    except Exception:
        return None


def gpu_util_pct():
    """3D/compute engine utilisation summed over engine instances, capped at 100."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$s=(Get-Counter '\\GPU Engine(*engtype_Compute*)\\Utilization Percentage','\\GPU Engine(*engtype_3D*)\\Utilization Percentage').CounterSamples;"
             "($s | Measure-Object -Property CookedValue -Sum).Sum"],
            capture_output=True, text=True, timeout=20)
        return min(100.0, round(float(out.stdout.strip()), 1))
    except Exception:
        return None


class Sampler(threading.Thread):
    """Background sampler of process RSS, system RAM, CPU, and VRAM peaks."""

    def __init__(self, pid, interval=2.0):
        super().__init__(daemon=True)
        self.pid, self.interval = pid, interval
        self.stop_evt = threading.Event()
        self.peak_rss = 0.0
        self.peak_vram = 0.0
        self.min_avail_ram = float("inf")
        self.cpu = []
        self.gpu = []

    def run(self):
        try:
            proc = psutil.Process(self.pid)
            proc.cpu_percent(None)
        except Exception:
            return
        while not self.stop_evt.is_set():
            try:
                self.peak_rss = max(self.peak_rss, proc.memory_info().rss / 2**20)
                self.cpu.append(proc.cpu_percent(None) / psutil.cpu_count())
            except Exception:
                pass
            self.min_avail_ram = min(self.min_avail_ram, psutil.virtual_memory().available / 2**20)
            v = gpu_dedicated_mib()
            if v:
                self.peak_vram = max(self.peak_vram, v)
            self.stop_evt.wait(self.interval)

    def summary(self):
        return {"peak_server_rss_mib": round(self.peak_rss, 1), "peak_vram_dedicated_mib": self.peak_vram,
                "min_system_available_ram_mib": round(self.min_avail_ram, 1) if self.cpu else None,
                "mean_server_cpu_pct_of_machine": round(sum(self.cpu) / len(self.cpu), 1) if self.cpu else None}


def file_sha256(path, cache_dir=LAB / "hashcache"):
    """sha256 with a size+mtime keyed cache (model files are tens of GB)."""
    p = Path(path)
    st = p.stat()
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:24]
    c = cache_dir / key
    if c.exists():
        return c.read_text().strip()
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    c.write_text(h.hexdigest())
    return h.hexdigest()


class Server:
    def __init__(self, cfg: ServerConfig, log_dir: Path):
        self.cfg, self.log_dir = cfg, log_dir
        self.proc = None
        self.sampler = None
        self.load_seconds = None
        self.vram_idle_before = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.cfg.port}"

    def start(self, timeout=900):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.vram_idle_before = gpu_dedicated_mib()
        log = open(self.log_dir / f"server_{self.cfg.name}.log", "w", encoding="utf-8", errors="replace")
        t0 = time.monotonic()
        self.proc = subprocess.Popen(self.cfg.argv(), stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.sampler = Sampler(self.proc.pid)
        self.sampler.start()
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server exited rc={self.proc.returncode}; see log")
            try:
                r = httpx.get(self.url + "/health", timeout=2)
                if r.status_code == 200:
                    self.load_seconds = round(time.monotonic() - t0, 2)
                    return self
            except Exception:
                pass
            time.sleep(0.5)
        self.stop()
        raise TimeoutError("server did not become healthy")

    def props(self):
        try:
            return httpx.get(self.url + "/props", timeout=10).json()
        except Exception:
            return {}

    def resource_snapshot(self):
        snap = {"load_seconds": self.load_seconds, "vram_dedicated_before_load_mib": self.vram_idle_before,
                "vram_dedicated_now_mib": gpu_dedicated_mib()}
        try:
            snap["server_rss_now_mib"] = round(psutil.Process(self.proc.pid).memory_info().rss / 2**20, 1)
        except Exception:
            pass
        snap["system_available_ram_mib"] = round(psutil.virtual_memory().available / 2**20, 1)
        if self.sampler:
            snap.update(self.sampler.summary())
        return snap

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


