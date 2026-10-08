"""Provider-neutral resource pools, executor registrations, atomic admission, aging, circuit breakers.

Nothing here names a provider. Pools are rows (name, capacity, kind); an executor registration
declares which pools an attempt claims and which pools suffer a breaker when it reports quota
exhaustion. Admission of all required claims for one attempt happens in ONE `BEGIN IMMEDIATE`
transaction; a capacity trigger (schema.py) guarantees SUM(held)<=capacity even against a buggy caller.

Clock discipline (brief section 9): lease deadlines are `time.monotonic` values valid ONLY inside the
scheduler epoch that wrote them. After a restart nothing is expired or trusted by deadline: old
claims stay `held` (so capacity stays consumed, preventing double admission) until recovery proves
the attempt dead and releases them. Starvation aging counts admission ROUNDS, not wall time, so a
wall-clock step cannot reorder the queue.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .executors import ExecutorSpec
from .ledger import Ledger, LedgerRefused, jdump

BACKOFF_BASE_S, BACKOFF_CAP_S = 30, 900


@dataclass
class Admitted:
    task_id: str
    attempt_id: int          # == fencing token
    registration_id: int
    executor_id: str
    claims: dict
    epoch: int
    round: int


class Registry:
    def __init__(self, ledger: Ledger):
        self.l = ledger

    def create_pool(self, name, capacity, kind="generic"):
        with self.l.tx() as db:
            db.execute("INSERT INTO resource_pool(name,capacity,kind,updated_at_us) VALUES (?,?,?,?)",
                       (name, capacity, kind, self.l.now_us()))
            self.l.emit("pool.create", payload={"name": name, "capacity": capacity})

    def set_capacity(self, name, capacity):
        with self.l.tx() as db:
            db.execute("UPDATE resource_pool SET capacity=?, updated_at_us=? WHERE name=?", (capacity, self.l.now_us(), name))
            self.l.emit("pool.capacity", payload={"name": name, "capacity": capacity})

    def register_executor(self, spec: ExecutorSpec, *, capabilities=(), claims=None, preemptible=False, safe_points=(),
                          quota_pools=(), version=None, valid_from_us=None, valid_until_us=None):
        """Versioned registration. The previous current registration is superseded, never edited."""
        claims = dict(claims or {})
        now = self.l.now_us()
        with self.l.tx() as db:
            for pool in list(claims) + list(quota_pools):
                if db.execute("SELECT 1 FROM resource_pool WHERE name=?", (pool,)).fetchone() is None:
                    raise LedgerRefused("UNKNOWN_POOL", pool)
            db.execute("UPDATE executor_registration SET superseded_at_us=?, valid_until_us=COALESCE(valid_until_us,?) "
                       "WHERE executor_id=? AND superseded_at_us IS NULL", (now, now, spec.executor_id))
            cur = db.execute(
                "INSERT INTO executor_registration(executor_id,version,spec_json,capabilities_json,claims_json,preemptible,"
                "safe_points_json,quota_pools_json,valid_from_us,valid_until_us,recorded_at_us) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (spec.executor_id, version, jdump(spec.to_json()), jdump(sorted(capabilities)), jdump(claims),
                 int(preemptible), jdump(list(safe_points)), jdump(list(quota_pools)),
                 valid_from_us if valid_from_us is not None else now, valid_until_us, now))
            self.l.emit("executor.register", payload={"executor_id": spec.executor_id, "registration_id": cur.lastrowid,
                                                     "version": version}, ref=("executor_registration", cur.lastrowid))
        return cur.lastrowid

    def current_registrations(self, at_us=None):
        at = self.l.now_us() if at_us is None else at_us
        return self.l.q("SELECT * FROM executor_registration r WHERE superseded_at_us IS NULL AND valid_from_us<=? "
                        "AND (valid_until_us IS NULL OR ?<valid_until_us) ORDER BY executor_id", (at, at))

    def registration_as_believed(self, executor_id, believed_at_us):
        """What URI believed the registration was at a past instant (bitemporal read)."""
        return self.l.q1("SELECT * FROM executor_registration WHERE executor_id=? AND recorded_at_us<=? "
                         "AND (superseded_at_us IS NULL OR ?<superseded_at_us) ORDER BY registration_id DESC LIMIT 1",
                         (executor_id, believed_at_us, believed_at_us))


class Admitter:
    def __init__(self, ledger: Ledger, epoch: int, lease_s: float = 60.0):
        self.l, self.epoch, self.lease_s = ledger, epoch, lease_s

    # ---- breakers --------------------------------------------------------------------------
    def _refresh_breaker(self, db, pool):
        """Lazily move open -> half_open when the (trusted) reopen condition has passed."""
        if pool["breaker_state"] != "open":
            return pool
        wall, mono = self.l.authority_now_us(), self.l.clock.mono_ns()
        reopen = False
        if pool["breaker_until_wall_us"] is not None:
            reopen = wall >= pool["breaker_until_wall_us"]
        elif pool["breaker_until_mono_ns"] is not None:
            # Monotonic deadline is only meaningful in the epoch that wrote it; after a restart be conservative: probe.
            reopen = pool["breaker_epoch"] != self.epoch or mono >= pool["breaker_until_mono_ns"]
        else:
            reopen = True
        if reopen:
            db.execute("UPDATE resource_pool SET breaker_state='half_open', probe_attempt_id=NULL, updated_at_us=? WHERE name=?",
                       (self.l.now_us(), pool["name"]))
            self.l.emit("breaker.half_open", payload={"pool": pool["name"]})
            return db.execute("SELECT * FROM resource_pool WHERE name=?", (pool["name"],)).fetchone()
        return pool

    def breaker_quota_hit(self, pools, provider_reset_wall_us=None, reason="quota"):
        with self.l.tx() as db:
            for name in pools:
                row = db.execute("SELECT * FROM resource_pool WHERE name=?", (name,)).fetchone()
                if row is None:
                    continue
                n = row["breaker_failures"] + 1
                if provider_reset_wall_us is not None:
                    until_wall, until_mono = provider_reset_wall_us, None   # trustworthy provider-stated reset
                else:
                    until_wall = None
                    until_mono = self.l.clock.mono_ns() + int(min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (n - 1)) * 1e9)
                db.execute("UPDATE resource_pool SET breaker_state='open', breaker_failures=?, breaker_until_wall_us=?, "
                           "breaker_until_mono_ns=?, breaker_epoch=?, probe_attempt_id=NULL, breaker_reason=?, updated_at_us=? "
                           "WHERE name=?", (n, until_wall, until_mono, self.epoch, reason, self.l.now_us(), name))
                self.l.emit("breaker.open", payload={"pool": name, "failures": n, "provider_reset": provider_reset_wall_us is not None})

    def breaker_success(self, pools):
        with self.l.tx() as db:
            for name in pools:
                db.execute("UPDATE resource_pool SET breaker_state='closed', breaker_failures=0, breaker_until_wall_us=NULL, "
                           "breaker_until_mono_ns=NULL, probe_attempt_id=NULL, breaker_reason=NULL, updated_at_us=? "
                           "WHERE name=? AND breaker_state<>'closed'", (self.l.now_us(), name))

    def probe_done(self, attempt_id, provider_answered):
        """A half-open probe attempt ended. If the provider answered (any terminal event, not quota) close the
        breaker; if it was merely interrupted, stay half-open and allow another probe."""
        with self.l.tx() as db:
            rows = db.execute("SELECT name FROM resource_pool WHERE probe_attempt_id=?", (attempt_id,)).fetchall()
            for r in rows:
                if provider_answered:
                    db.execute("UPDATE resource_pool SET breaker_state='closed', breaker_failures=0, breaker_until_wall_us=NULL, "
                               "breaker_until_mono_ns=NULL, probe_attempt_id=NULL, breaker_reason=NULL, updated_at_us=? WHERE name=?",
                               (self.l.now_us(), r["name"]))
                    self.l.emit("breaker.closed", payload={"pool": r["name"]})
                else:
                    db.execute("UPDATE resource_pool SET probe_attempt_id=NULL, updated_at_us=? WHERE name=?",
                               (self.l.now_us(), r["name"]))

    # ---- admission -------------------------------------------------------------------------
    def _assert_epoch(self):
        if self.l.current_epoch() != self.epoch:
            raise LedgerRefused("SUPERSEDED_SUPERVISOR", f"epoch {self.epoch} is not current")

    def _authorization(self, db, task_id, now):
        return db.execute(
            "SELECT * FROM authorization WHERE task_id=? AND superseded_at_us IS NULL AND valid_from_us<=? "
            "AND (valid_until_us IS NULL OR ?<valid_until_us) ORDER BY auth_id DESC LIMIT 1", (task_id, now, now)).fetchone()

    def _free(self, db, pool):
        held = db.execute("SELECT COALESCE(SUM(amount),0) FROM claim WHERE pool=? AND state='held'", (pool,)).fetchone()[0]
        cap = db.execute("SELECT capacity FROM resource_pool WHERE name=?", (pool,)).fetchone()[0]
        return cap - held

    def effective_priority(self, task, rnd):
        interval = max(1, int(self.l.meta("aging_interval", "5")))
        return task["base_priority"] + max(0, rnd - task["enqueue_round"]) // interval

    def admit_next(self, only_task_id=None) -> Admitted | None:
        """One scheduling pass. Returns the admitted attempt or None. Atomic.

        `only_task_id` restricts the pass to one task (Phase 2B bridge: a caller holding one ticket may only
        ever admit the task bound to that ticket, never a higher-ranked foreign task left in the queue)."""
        with self.l.tx() as db:
            self._assert_epoch()
            rnd = int(self.l.meta("admission_round", "0")) + 1
            db.execute("UPDATE meta SET value=? WHERE key='admission_round'", (str(rnd),))
            now = self.l.authority_now_us()
            if only_task_id is None:
                tasks = db.execute("SELECT * FROM task WHERE state IN ('QUEUED','RETRY_SAFE')").fetchall()
            else:
                tasks = db.execute("SELECT * FROM task WHERE state IN ('QUEUED','RETRY_SAFE') AND task_id=?",
                                   (only_task_id,)).fetchall()
            ranked = sorted(tasks, key=lambda t: (-self.effective_priority(t, rnd), t["enqueue_round"], t["task_seq"]))
            regs = self.current_registrations_in(db, now)
            reserved: set[str] = set()
            for t in ranked:
                auth = self._authorization(db, t["task_id"], now)
                if auth is None:
                    continue
                req = json.loads(t["requirements_json"])
                scope = json.loads(auth["scope_json"])
                allowed_cls = scope.get("allowed_op_classes")
                if allowed_cls is not None and any(e["op_class"] not in allowed_cls for e in req.get("effects", [])):
                    continue        # a (possibly narrowed) authorization no longer covers the declared effects
                caps_needed = set(req.get("capabilities", []))
                prefer = list(req.get("executors", []))
                allowed_exec = scope.get("allowed_executors")
                cands = [r for r in regs if caps_needed <= set(json.loads(r["capabilities_json"]))
                         and (not prefer or r["executor_id"] in prefer)
                         and (allowed_exec is None or r["executor_id"] in allowed_exec)]
                if prefer:
                    cands.sort(key=lambda r: prefer.index(r["executor_id"]))
                capacity_blocked_pools: set[str] = set()
                chosen = None
                for r in cands:
                    claims = json.loads(r["claims_json"])
                    pools = {n: self._refresh_breaker(db, db.execute("SELECT * FROM resource_pool WHERE name=?", (n,)).fetchone())
                             for n in claims}
                    if any(p["breaker_state"] == "open" or (p["breaker_state"] == "half_open" and p["probe_attempt_id"] is not None)
                           for p in pools.values()):
                        continue
                    if set(claims) & reserved:
                        capacity_blocked_pools |= set(claims) & reserved
                        continue
                    if all(self._free(db, n) >= amt for n, amt in claims.items()):
                        chosen = (r, claims, pools)
                        break
                    capacity_blocked_pools |= set(claims)
                if chosen is None:
                    reserved |= capacity_blocked_pools      # a waiting higher-ranked task reserves its pools
                    continue
                return self._commit_admission(db, t, auth, *chosen, rnd)
            return None

    def current_registrations_in(self, db, now):
        return db.execute("SELECT * FROM executor_registration WHERE superseded_at_us IS NULL AND valid_from_us<=? "
                          "AND (valid_until_us IS NULL OR ?<valid_until_us) ORDER BY executor_id", (now, now)).fetchall()

    def _commit_admission(self, db, t, auth, reg, claims, pools, rnd) -> Admitted:
        now, mono = self.l.now_us(), self.l.clock.mono_ns()
        n = t["attempt_count"] + 1
        cur = db.execute(
            "INSERT INTO attempt(task_id,attempt_no,executor_id,registration_id,executor_version,status,epoch,admitted_at_us) "
            "VALUES (?,?,?,?,?,'ADMITTED',?,?)", (t["task_id"], n, reg["executor_id"], reg["registration_id"], reg["version"],
                                                  self.epoch, now))
        attempt_id = cur.lastrowid
        db.execute("INSERT INTO admission(task_id,attempt_id,auth_id,epoch,registration_id,round,claims_json,admitted_at_us) "
                   "VALUES (?,?,?,?,?,?,?,?)", (t["task_id"], attempt_id, auth["auth_id"], self.epoch, reg["registration_id"],
                                                rnd, jdump(claims), now))
        lease_ns = int(self.lease_s * 1e9)
        for pool, amount in sorted(claims.items()):
            db.execute("INSERT INTO claim(task_id,attempt_id,pool,amount,epoch,state,lease_ns,lease_deadline_mono_ns,acquired_at_us) "
                       "VALUES (?,?,?,?,?,'held',?,?,?)", (t["task_id"], attempt_id, pool, amount, self.epoch, lease_ns,
                                                           mono + lease_ns, now))
            if pools[pool]["breaker_state"] == "half_open":
                db.execute("UPDATE resource_pool SET probe_attempt_id=? WHERE name=?", (attempt_id, pool))
        self.l.transition(t["task_id"], "RUNNING", "ADMITTED", f"attempt {n} executor {reg['executor_id']}",
                          attempt_id=attempt_id, set_fence=attempt_id, extra={"attempt_count": n})
        self.l.emit("admission", t["task_id"], attempt_id, ("attempt", attempt_id),
                    {"executor": reg["executor_id"], "claims": claims, "epoch": self.epoch, "round": rnd})
        return Admitted(t["task_id"], attempt_id, reg["registration_id"], reg["executor_id"], claims, self.epoch, rnd)

    # ---- leases / claims -------------------------------------------------------------------
    def renew(self, attempt_id):
        """Heartbeat. Only claims written in THIS epoch can be renewed; others need recovery."""
        with self.l.tx() as db:
            self._assert_epoch()
            db.execute("UPDATE claim SET lease_deadline_mono_ns=? + lease_ns WHERE attempt_id=? AND state='held' AND epoch=?",
                       (self.l.clock.mono_ns(), attempt_id, self.epoch))

    def expired_leases(self):
        """Same-epoch held claims past their monotonic deadline. Never includes foreign-epoch claims."""
        return self.l.q("SELECT * FROM claim WHERE state='held' AND epoch=? AND lease_deadline_mono_ns<?",
                        (self.epoch, self.l.clock.mono_ns()))

    def foreign_epoch_claims(self):
        return self.l.q("SELECT * FROM claim WHERE state='held' AND epoch<>?", (self.epoch,))

    def release(self, attempt_id, reason, state="released"):
        with self.l.tx() as db:
            db.execute("UPDATE claim SET state=?, ended_at_us=?, end_reason=? WHERE attempt_id=? AND state='held'",
                       (state, self.l.now_us(), reason, attempt_id))
            self.l.emit("claims.release", attempt_id=attempt_id, payload={"reason": reason, "state": state})

    def held_by_pool(self):
        return {r["pool"]: r["s"] for r in self.l.q(
            "SELECT pool, SUM(amount) s FROM claim WHERE state='held' GROUP BY pool")}
