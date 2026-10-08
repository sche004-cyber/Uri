import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uri_supervisor.clock import FakeClock  # noqa: E402
from uri_supervisor.executors import GENERIC_NDJSON  # noqa: E402
from uri_supervisor.supervisor import Supervisor  # noqa: E402

FAKE = str(Path(__file__).parent / "helpers" / "fake_executor.py")
HELPERS = Path(__file__).parent / "helpers"


class Env:
    """One ledger + supervisor + a registered generic executor."""

    def __init__(self, tmp_path, clock=None, **kw):
        self.tmp = Path(tmp_path)
        self.db = self.tmp / "ledger" / "ledger.db"
        self.clock = clock
        self.sup = Supervisor(self.db, clock=clock, **kw)
        self.L = self.sup.ledger

    def setup_pools(self, **pools):
        for name, cap in pools.items():
            self.sup.registry.create_pool(name, cap)

    def register(self, executor_id="fake", claims=None, caps=("run",), quota_pools=(), preemptible=False, spec=None):
        spec = spec or GENERIC_NDJSON
        from dataclasses import replace
        spec = replace(spec, executor_id=executor_id)
        return self.sup.registry.register_executor(spec, capabilities=caps, claims=claims or {}, quota_pools=quota_pools,
                                                   preemptible=preemptible, version="test-1")

    def task(self, task_id, *, effects=None, postconditions=None, **kw):
        effects = effects or [{"op_class": "read", "operation": "noop"}]
        postconditions = postconditions or [{"kind": "terminal_success"}]
        self.sup.submit_task(task_id, "tester", {"say": task_id}, authorization={"scope": {"x": 1}},
                             effects=effects, postconditions=postconditions, requirements={"capabilities": ["run"]}, **kw)

    def run(self, admitted, scenario, **kw):
        extra = ["--scenario", scenario]
        for k in ("path", "content", "sleep", "pidfile", "counter"):
            if k in kw:
                extra += [f"--{k}", str(kw.pop(k))]
        return self.sup.run_attempt(admitted, cwd=str(self.tmp), resolved_executable=sys.executable,
                                    extra_argv=[FAKE] + extra, **kw)

    def state(self, task_id):
        return self.L.task(task_id)["state"]

    def close(self):
        self.sup.close()


@pytest.fixture
def env(tmp_path):
    e = Env(tmp_path)
    e.setup_pools(slot=2)
    e.register(claims={"slot": 1})
    yield e
    e.close()
