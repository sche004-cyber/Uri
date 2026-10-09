"""H-AC4 restart-degradation experiment (WS hardening). Run from a materialized runtime tree:

    <runtime>\\.venv\\Scripts\\python.exe restart_experiment.py <runtime_root> <out.json> [--cycles N]

Under the URI GPU lease, with the accepted RuntimeManager (frozen argv), it records:
  * cold start: load time, calibration decode (same request as ws_brain_host), per-process residency;
  * release lag: adapter dedicated memory sampled every second (typeperf) from the stop until it returns to the
    pre-start level;
  * per cycle: restart IMMEDIATELY after stop (what the old OI host did) vs restart after the measured release
    (what ws_brain_host does), each followed by the calibration decode and residency.
Nothing outside this experiment's own server is touched.
"""
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
CYCLES = int(sys.argv[sys.argv.index("--cycles") + 1]) if "--cycles" in sys.argv else 2
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from uri_operational_intelligence import gpu_lease as G  # noqa: E402
from uri_operational_intelligence import runtime_v1 as R  # noqa: E402

PROMPT = "Here is a numbered list of forty everyday household objects, one per line:\n1."
cfg = R.load_config()
STATE = ROOT / "work" / "oi" / "state-experiment"
record = {"schema": "uri.ws.restart_experiment.v1", "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "runs": []}


def adapter_luid():
    return G.census()["luid"]


class AdapterSampler:
    """typeperf: one adapter dedicated-usage sample per second, wall-clock stamped."""

    def __init__(self, luid):
        self.samples, self.stop = [], threading.Event()
        self.p = subprocess.Popen(["typeperf", r"\GPU Adapter Memory(%s_phys_0)\Dedicated Usage" % luid, "-si", "1"],
                                  stdout=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            parts = line.strip().strip('"').split('","')
            if len(parts) == 2:
                try:
                    self.samples.append((time.time(), float(parts[1]) / 2**20))
                except ValueError:
                    pass

    def close(self):
        self.p.terminate()


def calibrate():
    with httpx.Client(base_url=R.base_url(cfg), timeout=httpx.Timeout(180.0, connect=3.0)) as c:
        tims = []
        for _ in range(2):
            r = c.post("/completion", json={"prompt": PROMPT, "n_predict": 160, "temperature": 0, "cache_prompt": False,
                                            "ignore_eos": True})
            tims.append(r.json()["timings"]["predicted_per_second"])
    return [round(t, 1) for t in tims]


def residency(pid):
    c = G.census()
    me = next((p for p in c.get("processes", []) if p["pid"] == pid), {})
    return {"dedicated_mib": me.get("dedicated_mib"), "non_local_mib": me.get("non_local_mib"),
            "adapter_mib": c.get("adapter_dedicated_mib"), "unattributed_mib": c.get("unattributed_mib")}


def start(label, sampler):
    m = R.RuntimeManager(cfg, state_dir=STATE)
    t0 = time.time()
    r = m.ensure_ready()
    assert r.state == R.READY and m.owns_instance, (r.state, r.detail)
    run = {"label": label, "t_start": round(t0, 2), "load_s": round(time.time() - t0, 1), "pid": r.pid}
    run["calibration_tps"] = calibrate()
    run["residency"] = residency(r.pid)
    record["runs"].append(run)
    print(json.dumps(run), flush=True)
    return m


def stop(m, sampler, baseline, wait=True):
    t0 = time.time()
    m.stop()
    if not wait:
        return {"t_stop": round(t0, 2), "release_s": None, "waited": False}
    # release: adapter usage back within 300 MiB of the pre-start level
    released = None
    while time.time() - t0 < 120:
        recent = [v for t, v in sampler.samples if t > t0]
        if recent and recent[-1] <= baseline + 300:
            released = round(next(t for t, v in sampler.samples if t > t0 and v <= baseline + 300) - t0, 1)
            break
        time.sleep(0.5)
    curve = [(round(t - t0, 1), round(v)) for t, v in sampler.samples if t0 - 2 <= t <= t0 + 30]
    return {"t_stop": round(t0, 2), "release_s": released, "curve": curve}


def main():
    with G.acquire("restart_experiment", label="WS hardening H-AC4", expected_vram_mib=G.RUNTIME_V1_DEVICE_MIB) as lease:
        s = AdapterSampler(adapter_luid())
        time.sleep(3)
        baseline = s.samples[-1][1]
        record["baseline_adapter_mib"] = round(baseline)
        record["lease"] = lease.record["purpose"]
        try:
            m = start("cold", s)
            for i in range(CYCLES):
                st = stop(m, s, baseline, wait=False)
                record["runs"][-1]["stop"] = st
                m = start("immediate_restart_%d" % (i + 1), s)          # no wait: the old OI host's behaviour
                st = stop(m, s, baseline)
                record["runs"][-1]["stop"] = st
                # measured release (already waited inside stop) + the host's unattributed check
                c = G.census()
                record.setdefault("pre_restart_census", []).append({"unattributed_mib": c.get("unattributed_mib"),
                                                                    "since_stop_s": round(time.time() - st["t_stop"], 1)})
                m = start("restart_after_release_%d" % (i + 1), s)
            record["runs"][-1]["stop"] = stop(m, s, baseline)
        finally:
            s.close()
            record["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            OUT.write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
