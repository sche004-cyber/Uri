"""Evaluation-only, proposal-only multi-tool variant of the existing bridge."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from experimental.edge_model_tests import experimental_needle_bridge_runtime as base


class MultiToolBridge(base.ExperimentalDecodeBridge):
    def _agent(self, system, schema):
        key = self._agent_key(system, schema)
        if self._current_key != key or self._current_agent is None:
            if self._current_agent is not None:
                self._current_agent.close()
            started = time.perf_counter()
            self._current_agent = base.needle.Needle(tools=schema["tools"], system=system, generation=3)
            self._load_time_ms = (time.perf_counter() - started) * 1000
            self._current_key = key
        return self._current_agent


if __name__ == "__main__":
    base.ExperimentalDecodeBridge = MultiToolBridge
    raise SystemExit(base.main())
