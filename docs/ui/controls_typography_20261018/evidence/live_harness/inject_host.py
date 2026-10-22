"""UI-CONTROLS-TYPO-20261018 live fault injection (harness only, never part of the candidate).

    <runtime python> -B -I inject_host.py <runtime root> <profile id> <record.json> <ws_brain_host args...>

Runs the PRODUCTION Brain host (`<runtime>/scripts/ws_brain_host.py`, the candidate's code) unchanged, except that
the FIRST start of <profile id> that happens inside a profile switch fails on purpose: after the host's own GPU
fit / release wait, and BEFORE any Brain server is spawned, the start reports FAILED (detail
INJECTED_START_FAILURE). This exercises the real switch path (the running Standard Brain is really stopped) and the
real automatic restore (the previous profile is really started again on the held lease). Every later start, of any
profile, is the production start. The injection is recorded in <record.json>.
"""
import importlib.util
import json
import pathlib
import sys
import time

RT, TARGET, RECORD = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
ARGS = sys.argv[4:]
sys.path.insert(0, str(RT))
spec = importlib.util.spec_from_file_location("ws_brain_host", RT / "scripts" / "ws_brain_host.py")
host_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host_mod)

_left = {"n": 1}
_orig = host_mod.Host._start_brain


def _start_brain(self):
    pid = host_mod.RP.describe(self.cfg)["id"]
    switching = (self.report.get("profile_switch") or {}).get("result") == "IN_PROGRESS"
    if pid == TARGET and switching and _left["n"] > 0:
        _left["n"] -= 1
        if not self.wait_for_gpu():
            return False
        self.set("FAILED", detail="INJECTED_START_FAILURE",
                 explain="(live harness) injected start failure for %s, before any server was spawned." % pid)
        self.stopped_at = self.now()
        RECORD.write_text(json.dumps({"profile": pid, "t": round(time.time(), 3),
                                      "switch": self.report.get("profile_switch")}, indent=1, default=str))
        return False
    return _orig(self)


host_mod.Host._start_brain = _start_brain
sys.exit(host_mod.main(ARGS))
