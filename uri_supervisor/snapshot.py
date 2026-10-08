"""Deterministic, bounded manager snapshot derived ONLY from the durable ledger plus fresh observations.

* `stable` (definitions, vocabulary, schema) comes first and never contains volatile data, so an LLM
  prompt prefix built from it stays cache-identical across snapshots.
* `volatile` carries the ledger watermark (monotonic version), counters, conditions, bounded lists
  with disclosed omitted counts, and ledger event ids that justify each item.
* Conditions are True / False / Unknown. An observation older than its TTL, or never made, is
  Unknown. Nothing is ever assumed healthy. The observation board is in-memory by design: after a
  supervisor restart every observation is Unknown until re-observed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from .ledger import Ledger, jdump
from .schema import STATES

SCHEMA = "uri.manager_snapshot/1"
STABLE = {
    "schema": SCHEMA,
    "states": list(STATES),
    "condition_values": ["True", "False", "Unknown"],
    "definitions": {
        "RUNNING": "an admitted attempt is executing under supervision",
        "RECOVERING": "an attempt ended or was interrupted; URI is reconciling evidence",
        "COMPLETE": "every required postcondition was verified by URI itself",
        "RETRY_SAFE": "URI proved a retry cannot duplicate an effect",
        "UNCERTAIN": "URI cannot prove whether an effect happened; waiting for new evidence",
        "NEEDS_USER": "only a human decision can resolve the uncertainty",
        "FAILED": "terminal failure",
        "QUEUED": "admitted to the queue, no attempt yet",
    },
    "rules": ["No event, no claim.", "Executor reports are claims, not facts.", "Unknown is never reported as healthy."],
}
STABLE_JSON = jdump(STABLE)
STABLE_SHA256 = hashlib.sha256(STABLE_JSON.encode()).hexdigest()


class ObservationBoard:
    """Fresh observations with TTLs. Uses the monotonic clock: valid only inside this process/epoch."""

    def __init__(self, clock):
        self.clock = clock
        self._obs: dict[str, tuple] = {}
        self._required: dict[str, float] = {}

    def require(self, name, ttl_s):
        self._required[name] = ttl_s

    def observe(self, name, value: bool, ttl_s=None, detail=""):
        ttl = ttl_s if ttl_s is not None else self._required.get(name, 30.0)
        self._obs[name] = (bool(value), self.clock.mono_ns(), ttl, detail)

    def conditions(self):
        out, now = [], self.clock.mono_ns()
        for name in sorted(set(self._required) | set(self._obs)):
            o = self._obs.get(name)
            ttl = o[2] if o else self._required.get(name, 30.0)
            if o is None:
                out.append({"type": name, "status": "Unknown", "reason": "NEVER_OBSERVED", "age_s": None, "ttl_s": ttl})
                continue
            age = (now - o[1]) / 1e9
            if age < 0 or age > o[2]:
                out.append({"type": name, "status": "Unknown", "reason": "STALE_OBSERVATION", "age_s": round(max(age, 0), 3),
                            "ttl_s": o[2]})
            else:
                out.append({"type": name, "status": "True" if o[0] else "False", "reason": o[3] or "OBSERVED",
                            "age_s": round(age, 3), "ttl_s": o[2]})
        return out


def build_snapshot(ledger: Ledger, board: ObservationBoard, *, max_items=10):
    L = ledger
    with L.read_tx():   # one consistent WAL snapshot: watermark + rows from the same point
        wm = L.watermark()
        counts = {r["state"]: r["n"] for r in L.q("SELECT state, COUNT(*) n FROM task GROUP BY state")}
        needs = L.q("SELECT task_id,state,reason_code,state_changed_at_us FROM task WHERE state IN ('NEEDS_USER','UNCERTAIN','RECOVERING','FAILED') "
                    "ORDER BY CASE state WHEN 'NEEDS_USER' THEN 0 WHEN 'UNCERTAIN' THEN 1 WHEN 'RECOVERING' THEN 2 ELSE 3 END, task_seq")
        running = L.q("SELECT t.task_id,t.reason_code,a.executor_id,a.attempt_id FROM task t JOIN attempt a ON a.attempt_id=t.current_fence "
                      "WHERE t.state='RUNNING' ORDER BY t.task_seq")
        pools = L.q("SELECT p.name,p.capacity,p.breaker_state,COALESCE((SELECT SUM(amount) FROM claim c WHERE c.pool=p.name AND c.state='held'),0) held "
                    "FROM resource_pool p ORDER BY p.name")

        def last_event(task_id):
            r = L.q1("SELECT MAX(seq) FROM event WHERE task_id=? AND kind='task.state'", (task_id,))
            return r[0]
        attention = [{"task_id": r["task_id"], "state": r["state"], "reason": r["reason_code"], "event_ids": [last_event(r["task_id"])]}
                     for r in needs[:max_items]]
        run_items = [{"task_id": r["task_id"], "executor": r["executor_id"], "attempt": r["attempt_id"],
                      "event_ids": [last_event(r["task_id"])]} for r in running[:max_items]]
        derived = [{"type": f"breaker_open:{p['name']}", "status": "True" if p["breaker_state"] != "closed" else "False",
                    "reason": f"breaker_state={p['breaker_state']}", "source": "ledger"} for p in pools]
        derived.append({"type": "pool_capacity_respected", "source": "ledger",
                        "status": "True" if all(p["held"] <= p["capacity"] for p in pools) else "False", "reason": "SUM(held)<=capacity"})
        now = dt.datetime.fromtimestamp(L.clock.wall_us() / 1e6, dt.timezone.utc).isoformat().replace("+00:00", "Z")
        vol = {"version": wm, "generated_at": now, "epoch": L.current_epoch(),
               "counts": {"running": counts.get("RUNNING", 0), "queued": counts.get("QUEUED", 0) + counts.get("RETRY_SAFE", 0),
                          "uncertain": counts.get("UNCERTAIN", 0), "needs_user": counts.get("NEEDS_USER", 0),
                          "recovering": counts.get("RECOVERING", 0)},
               "conditions": board.conditions() + derived,
               "attention": attention, "running": run_items,
               "omitted": {"attention": max(0, len(needs) - max_items), "running": max(0, len(running) - max_items)},
               "pools": [{"name": p["name"], "held": p["held"], "capacity": p["capacity"], "breaker": p["breaker_state"]} for p in pools[:max_items]],
               "pools_omitted": max(0, len(pools) - max_items)}
    return {"stable_sha256": STABLE_SHA256, "stable": STABLE, "volatile": vol}


def render_prompt(snapshot) -> str:
    """Stable prefix first, byte-identical across snapshots; volatile data strictly after it."""
    return STABLE_JSON + "\n--- VOLATILE ---\n" + jdump(snapshot["volatile"])
