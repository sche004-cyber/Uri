"""Child process for Phase 2B crash tests: build a bridge, verify a SYNTHETIC ticket, execute it.

Config is one JSON argv. URI_SUPERVISOR_CRASH_AT (inherited) kills the supervisor inside the bridge at a named
point with os._exit(137). Prints one JSON line with the result when it survives.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from phase2b.conftest import SyntheticAuthority, fake_binding, fake_registry, CLAUDE  # noqa: E402
from uri_supervisor_bridge.bridge import SupervisorBridge  # noqa: E402


def main():
    cfg = json.loads(sys.argv[1])
    os.environ["URI_FAKE_SCENARIO"] = cfg.get("scenario", "honest")
    if cfg.get("counter"):
        os.environ["URI_FAKE_COUNTER"] = cfg["counter"]
    auth = SyntheticAuthority.from_private_hex(cfg["key"], cfg["generation"], cfg["binding"])
    bridge = SupervisorBridge(cfg["client_root"], registry=fake_registry("claude_code"),
                              executors={"claude_code": fake_binding("claude_code")}, timeout_s=cfg.get("timeout_s", 20),
                              inactivity_s=cfg.get("inactivity_s", 5))
    if cfg["mode"] == "restart_only":
        print(json.dumps({"startup": bridge.reconcile_restart()}))
        bridge.close()
        return
    work = auth.verify(cfg["signed"], cfg["request"], CLAUDE, now=cfg["now"])
    out = bridge.execute(work)
    print(json.dumps({"outcome": out[0], "failure": out[2], "startup": bridge.reconcile_restart()}))
    bridge.close()


if __name__ == "__main__":
    main()
