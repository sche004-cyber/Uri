"""Child supervisor process for crash tests. Config is one JSON argv. Exit code 137 = injected crash.

modes: run     -> register/submit if needed, admit, run one attempt
       recover -> just construct the Supervisor (startup recovery runs), optionally with a recovery crash point
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from uri_supervisor.executors import GENERIC_NDJSON  # noqa: E402
from uri_supervisor.ledger import LedgerError  # noqa: E402
from uri_supervisor.supervisor import Supervisor  # noqa: E402

FAKE = str(Path(__file__).parent / "fake_executor.py")


def main():
    cfg = json.loads(sys.argv[1])
    sup = Supervisor(cfg["db"])
    if cfg["mode"] == "recover":
        sup.close()
        return
    try:
        sup.registry.create_pool("slot", 2)
    except LedgerError:
        pass
    if sup.ledger.q1("SELECT 1 FROM executor_registration") is None:
        sup.registry.register_executor(replace(GENERIC_NDJSON, executor_id="fake"), capabilities=["run"], claims={"slot": 1},
                                       version="test-1")
    if sup.ledger.task(cfg["task_id"]) is None:
        sup.submit_task(cfg["task_id"], "tester", {"say": "crash test"}, authorization={"scope": {}},
                        effects=cfg["effects"], postconditions=cfg["postconditions"], requirements={"capabilities": ["run"]},
                        max_attempts=cfg.get("max_attempts", 3))
    a = sup.admit_next()
    if a is None:
        sup.close()
        return
    extra = [FAKE, "--scenario", cfg["scenario"]]
    for k in ("path", "content", "sleep", "counter"):
        if k in cfg:
            extra += [f"--{k}", str(cfg[k])]
    sup.run_attempt(a, cwd=cfg["cwd"], resolved_executable=sys.executable, extra_argv=extra,
                    timeout_s=cfg.get("timeout_s", 60), terminal_grace_s=cfg.get("grace", 2))
    sup.close()


if __name__ == "__main__":
    main()
