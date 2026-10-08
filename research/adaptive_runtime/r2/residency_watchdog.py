"""Residency watchdog (research prototype; read-only, never acts on the server).

Two signals, because R1/R2 showed that the amount of demoted memory alone does not predict the slow state
(2.7 GB non-local with 128 MiB blocks ran at 101 tok/s; 1.5 GB non-local with 256 MiB blocks ran at 45 tok/s):

  1. residency: per-process `GPU Process Memory\\Non Local Usage` minus the profile's host-visible share
     -> demoted_mib; "partially_demoted" above a warning threshold (risk signal);
  2. throughput: passive decode rate from `/metrics` deltas (`tokens_predicted_total` /
     `tokens_predicted_seconds_total`) over windows that generated at least `min_window_tokens`;
     "DEGRADED" when the rate stays below degraded_ratio x expected for `consecutive` windows; "RECOVERED"
     when it is back above recover_ratio x expected.

Optional active probe (off by default): when no window produced tokens for `probe_idle_s` and the server is
idle (`requests_processing` = 0), send one short completion and use its server-side timing as a sample.

  python residency_watchdog.py --port 18497 --seconds 300 --out evidence/r2_watch/<name>
  (writes <out>.csv samples, <out>.events.jsonl transitions, <out>.summary.json)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import psutil

_BS = chr(92)
_Q = ("$s=(Get-Counter '@@GPU Process Memory(pid_%d*)@@Local Usage','@@GPU Process Memory(pid_%d*)@@Non Local Usage',"
      "'@@GPU Adapter Memory(*)@@Dedicated Usage').CounterSamples; $s | ForEach-Object { $_.Path + '=' + [int64]($_.CookedValue/1MB) }")
_METRIC = re.compile(r"^llamacpp:([a-z_]+)(?:\{[^}]*\})?\s+([0-9.eE+-]+)\s*$", re.M)


@dataclass
class WatchConfig:
    pid: int
    url: str
    interval_s: float = 5.0
    host_visible_mib: int = 872          # by-design host-visible share of the frozen profile (R1 ledger)
    demoted_warn_mib: int = 256
    expected_decode_tps: float = 110.0   # healthy frozen profile with MTP (R1/R2 idle loads 110-127)
    degraded_ratio: float = 0.6
    recover_ratio: float = 0.8
    consecutive: int = 2
    min_window_tokens: int = 32
    active_probe: bool = False
    probe_idle_s: float = 300.0
    probe_tokens: int = 24


@dataclass
class Sample:
    ts: str
    t: float
    local_mib: int | None
    nonlocal_mib: int | None
    adapter_mib: int | None
    demoted_mib: int | None
    tokens_total: float | None
    seconds_total: float | None
    window_tokens: float | None
    window_tps: float | None
    requests_processing: float | None
    residency: str
    throughput: str
    state: str
    source: str = "passive"


def residency_for_pid(pid: int) -> dict:
    q = (_Q % (pid, pid)).replace("@@", _BS)
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True, timeout=40).stdout
    except Exception:
        return {}
    r = {"local": 0, "nonlocal": 0, "adapter": None}
    seen = False
    for line in out.splitlines():
        if "=" not in line:
            continue
        path, v = line.rsplit("=", 1)
        pl = path.lower()
        v = int(v)
        if "adapter memory" in pl:
            r["adapter"] = max(r["adapter"] or 0, v)
        elif f"pid_{pid}_" in pl:
            seen = True
            if "non local usage" in pl:
                r["nonlocal"] += v
            elif "local usage" in pl:
                r["local"] += v
    if not seen:
        r["local"] = r["nonlocal"] = None
    return r


def read_metrics(url: str, timeout=5.0) -> dict[str, float]:
    try:
        txt = httpx.get(url + "/metrics", timeout=timeout).text
    except Exception:
        return {}
    out = {}
    for m in _METRIC.finditer(txt):
        name, val = m.group(1), m.group(2)
        try:
            out[name] = out.get(name, 0.0) + float(val)
        except ValueError:
            pass
    return out


def find_pid_by_port(port: int, wait_s: float = 420.0) -> int | None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < wait_s:
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                if (p.info["name"] or "").lower().startswith("llama-server") and p.info["cmdline"] and \
                        "--port" in p.info["cmdline"] and str(port) in p.info["cmdline"][p.info["cmdline"].index("--port") + 1]:
                    return p.pid
            except Exception:
                continue
        time.sleep(1.0)
    return None


class Watchdog:
    def __init__(self, cfg: WatchConfig, out_base: Path, log=print):
        self.cfg, self.out_base, self.log = cfg, out_base, log
        self.samples: list[Sample] = []
        self.events: list[dict] = []
        self.state = "OK"
        self.throughput = "unknown"
        self.residency = "unknown"
        self._below = 0
        self._last_tokens = None
        self._last_seconds = None
        self._last_tokens_at = None
        self.t0 = time.monotonic()
        self.first_degraded_at = None
        self.first_demoted_at = None
        out_base.parent.mkdir(parents=True, exist_ok=True)
        self._csv = open(str(out_base) + ".csv", "w", encoding="utf-8")
        self._csv.write("ts,t,local_mib,nonlocal_mib,adapter_mib,demoted_mib,tokens_total,window_tokens,window_tps,requests_processing,residency,throughput,state,source\n")

    def _event(self, kind, **kw):
        ev = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "t": round(time.monotonic() - self.t0, 1), "event": kind, **kw}
        self.events.append(ev)
        self.log(f"[watchdog] {ev}")

    def classify_throughput(self, tps: float | None):
        if tps is None:
            return self.throughput
        if tps < self.cfg.degraded_ratio * self.cfg.expected_decode_tps:
            self._below += 1
            if self._below >= self.cfg.consecutive:
                return "degraded"
            return self.throughput if self.throughput in ("healthy", "degraded") else "suspect"
        self._below = 0
        if tps >= self.cfg.recover_ratio * self.cfg.expected_decode_tps:
            return "healthy"
        return "slow_but_above_threshold" if self.throughput != "degraded" else "degraded"

    def step(self, probe_fn=None) -> Sample:
        now = time.monotonic()
        res = residency_for_pid(self.cfg.pid)
        met = read_metrics(self.cfg.url)
        tokens = met.get("tokens_predicted_total")
        secs = met.get("tokens_predicted_seconds_total")
        rp = met.get("requests_processing")
        win_tokens = win_tps = None
        source = "passive"
        if tokens is not None and self._last_tokens is not None:
            win_tokens = tokens - self._last_tokens
            dsec = (secs or 0) - (self._last_seconds or 0)
            if win_tokens >= self.cfg.min_window_tokens and dsec > 0:
                win_tps = win_tokens / dsec
                self._last_tokens_at = now
        if tokens is not None:
            if self._last_tokens is None:
                self._last_tokens_at = now
            self._last_tokens, self._last_seconds = tokens, secs
        if win_tps is None and self.cfg.active_probe and probe_fn and (rp or 0) == 0 and \
                self._last_tokens_at is not None and now - self._last_tokens_at >= self.cfg.probe_idle_s:
            win_tps = probe_fn()
            source = "probe"
            self._last_tokens_at = now
            met2 = read_metrics(self.cfg.url)
            self._last_tokens, self._last_seconds = met2.get("tokens_predicted_total"), met2.get("tokens_predicted_seconds_total")
        demoted = None
        if res.get("nonlocal") is not None:
            demoted = max(0, res["nonlocal"] - self.cfg.host_visible_mib)
            residency = "partially_demoted" if demoted >= self.cfg.demoted_warn_mib else "resident"
        else:
            residency = "unknown"
        new_tp = self.classify_throughput(win_tps)
        if residency != self.residency:
            if residency == "partially_demoted" and self.first_demoted_at is None:
                self.first_demoted_at = round(now - self.t0, 1)
            self._event("residency", frm=self.residency, to=residency, demoted_mib=demoted)
            self.residency = residency
        if new_tp != self.throughput:
            self._event("throughput", frm=self.throughput, to=new_tp, window_tps=round(win_tps, 1) if win_tps else None)
            self.throughput = new_tp
        state = "DEGRADED" if self.throughput == "degraded" else ("AT_RISK" if residency == "partially_demoted" else "OK")
        if self.throughput == "healthy" and self.state == "DEGRADED":
            state = "RECOVERED"
        if state != self.state:
            if state == "DEGRADED" and self.first_degraded_at is None:
                self.first_degraded_at = round(now - self.t0, 1)
            self._event("state", frm=self.state, to=state, demoted_mib=demoted, window_tps=round(win_tps, 1) if win_tps else None)
            self.state = state
        s = Sample(dt.datetime.now().isoformat(timespec="seconds"), round(now - self.t0, 1), res.get("local"), res.get("nonlocal"),
                   res.get("adapter"), demoted, tokens, secs, win_tokens, round(win_tps, 2) if win_tps else None, rp,
                   residency, self.throughput, self.state, source)
        self.samples.append(s)
        self._csv.write(",".join("" if v is None else str(v) for v in (s.ts, s.t, s.local_mib, s.nonlocal_mib, s.adapter_mib, s.demoted_mib,
                                                                       s.tokens_total, s.window_tokens, s.window_tps, s.requests_processing,
                                                                       s.residency, s.throughput, s.state, s.source)) + "\n")
        self._csv.flush()
        return s

    def summary(self) -> dict:
        tps = [s.window_tps for s in self.samples if s.window_tps is not None]
        dem = [s.demoted_mib for s in self.samples if s.demoted_mib is not None]
        return {"pid": self.cfg.pid, "url": self.cfg.url, "config": asdict(self.cfg), "n_samples": len(self.samples),
                "final_state": self.state, "ever_degraded": any(s.state == "DEGRADED" for s in self.samples),
                "ever_at_risk": any(s.residency == "partially_demoted" for s in self.samples),
                "first_demoted_at_s": self.first_demoted_at, "first_degraded_at_s": self.first_degraded_at,
                "window_tps": {"n": len(tps), "min": round(min(tps), 1) if tps else None, "p50": round(sorted(tps)[len(tps) // 2], 1) if tps else None,
                               "max": round(max(tps), 1) if tps else None},
                "demoted_mib": {"min": min(dem) if dem else None, "max": max(dem) if dem else None},
                "local_mib_last": self.samples[-1].local_mib if self.samples else None,
                "nonlocal_mib_last": self.samples[-1].nonlocal_mib if self.samples else None,
                "events": self.events}

    def close(self):
        self._csv.close()
        Path(str(self.out_base) + ".events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.events), encoding="utf-8")
        Path(str(self.out_base) + ".summary.json").write_text(json.dumps(self.summary(), indent=1), encoding="utf-8")


def make_probe(url: str, n_tokens: int):
    def probe():
        body = {"model": "local", "messages": [{"role": "user", "content": "Count from one to forty in words."}],
                "max_tokens": n_tokens, "temperature": 0.0, "stream": False, "chat_template_kwargs": {"enable_thinking": False}}
        try:
            j = httpx.post(url + "/v1/chat/completions", json=body, timeout=120).json()
            t = j.get("timings") or {}
            return t.get("predicted_per_second")
        except Exception:
            return None
    return probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--port", type=int, help="discover the llama-server PID by its --port argument")
    ap.add_argument("--url")
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--out", required=True, help="output base path (no extension)")
    ap.add_argument("--host-visible-mib", type=int, default=872)
    ap.add_argument("--expected-tps", type=float, default=110.0)
    ap.add_argument("--demoted-warn-mib", type=int, default=256)
    ap.add_argument("--active-probe", action="store_true")
    ap.add_argument("--probe-idle-s", type=float, default=300)
    ap.add_argument("--stop-when-gone", action="store_true", help="stop when the watched process exits")
    a = ap.parse_args()
    pid = a.pid or (find_pid_by_port(a.port) if a.port else None)
    if pid is None:
        raise SystemExit("no llama-server pid found")
    url = a.url or f"http://127.0.0.1:{a.port}"
    cfg = WatchConfig(pid, url, a.interval, a.host_visible_mib, a.demoted_warn_mib, a.expected_tps,
                      active_probe=a.active_probe, probe_idle_s=a.probe_idle_s)
    wd = Watchdog(cfg, Path(a.out))
    probe = make_probe(url, cfg.probe_tokens) if a.active_probe else None
    t_end = time.monotonic() + a.seconds
    try:
        while time.monotonic() < t_end:
            if a.stop_when_gone and not psutil.pid_exists(pid):
                break
            wd.step(probe)
            time.sleep(a.interval)
    finally:
        wd.close()
        print(json.dumps({k: v for k, v in wd.summary().items() if k != "events"}))


if __name__ == "__main__":
    main()
