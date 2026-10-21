"""Milestone Manager service: one method per command.

Every mutating method runs ``_write``: take the ledger lock, load the projection (cache + new events), validate the
request against it, append the event(s) with fsync, update the cache, optionally git-commit. Validation inside the
lock means two agents cannot both pass a check and then both write (no check-then-use race).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

from scripts.dev_workflow.milestones import model as M
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones.store import (GIT, EventStore, StoreError, atomic_write_bytes, canonical,
                                                   file_sha256, read_segment, sha256_text)

CACHE_SCHEMA = "uri-mm-projection/1"
LEASE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime(LEASE_FORMAT)


class Manager:
    def __init__(self, home, actor: str | None = None, session: str | None = None, clock=None, task_source=None):
        self.store = EventStore(home)
        self.home = Path(home)
        self.actor = actor
        self.session = session
        self.clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self.task_source = task_source
        self.cache_path = self.home / "cache" / "projection.json"
        self.last_autocommit = None

    # ------------------------------------------------------------------ projection

    def _load_cache(self):
        try:
            c = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if c.get("schema") != CACHE_SCHEMA or not isinstance(c.get("segments"), dict):
            return None
        return c

    def projection(self, use_cache: bool = True) -> dict:
        """Current projection. Incremental from the cache when every new event sorts after the cached ones."""
        cache = self._load_cache() if use_cache else None
        paths = self.store.segment_paths()
        if cache is not None:
            new_events, segs, ok = [], {}, True
            for path in paths:
                info = cache["segments"].get(path.stem, {"offset": 0, "head": "0" * 64, "count": 0})
                size = path.stat().st_size
                if size < info["offset"]:
                    ok = False
                    break
                seg = read_segment(path, info["offset"], info["head"], info["count"])
                if seg.errors:
                    ok = False
                    break
                new_events.extend(seg.events)
                segs[path.stem] = {"offset": seg.good_bytes, "head": seg.head, "count": info["count"] + len(seg.events)}
            if ok and set(cache["segments"]) <= set(segs):
                new_events.sort(key=M.event_key)
                last = cache["state"].get("last_key")
                if not new_events or last is None or M.event_key(new_events[0]) > last:
                    state = M.fold(new_events, cache["state"]) if new_events else cache["state"]
                    if new_events:
                        self._save_cache(segs, state)
                    return state
        return self.rebuild()

    def rebuild(self) -> dict:
        segs = self.store.read_all()
        bad = [e for s in segs for e in s.errors]
        state = M.fold(M.ordered(segs))
        if not bad:
            self._save_cache({s.name: {"offset": s.good_bytes, "head": s.head, "count": len(s.events)} for s in segs},
                             state)
        state["integrity_errors"] = bad
        return state

    def _save_cache(self, segs: dict, state: dict) -> None:
        state = {k: v for k, v in state.items() if k != "integrity_errors"}
        data = json.dumps({"schema": CACHE_SCHEMA, "segments": segs, "state": state}, sort_keys=True)
        atomic_write_bytes(self.cache_path, data.encode("utf-8"))

    # ------------------------------------------------------------------ write helper

    def _require_actor(self):
        if not self.actor or not isinstance(self.actor, str) or len(self.actor) > 200:
            raise ValidationError("NO_ACTOR", "an --actor (or URI_MM_ACTOR) identifying the agent is required for writes")
        if M.find_secret(self.actor) or M.find_secret(self.session or ""):
            raise ValidationError("SECRET", "actor/session looks like a secret")

    def _write(self, build):
        """``build(p)`` validates against projection ``p`` and returns [(kind, data, base), ...] to append."""
        self._require_actor()
        with self.store.locked():
            p = self.projection()
            if p.get("integrity_errors"):
                raise StoreError("CHAIN_BROKEN", "ledger fails verification; run `verify` (" +
                                 "; ".join(p["integrity_errors"][:2]) + ")")
            items = build(p)
            for kind, data, _ in items:
                hit = M.find_secret(data)
                if hit:
                    raise ValidationError("SECRET", f"{kind} contains what looks like a {hit}; secrets are never "
                                                    "stored (record a reference instead)")
            written = []
            for kind, data, base in items:
                ev = self.store.append(kind, data, actor=self.actor, session=self.session, base=base)
                M.apply(p, ev)
                written.append(ev)
            if written:
                segs = {}
                for path in self.store.segment_paths():
                    s = read_segment(path)
                    segs[s.name] = {"offset": s.good_bytes, "head": s.head, "count": len(s.events)}
                p.pop("integrity_errors", None)
                self._save_cache(segs, p)
                self.last_autocommit = self.store.autocommit(f"{written[-1]['kind']} by {self.actor}")
            return written

    @staticmethod
    def _version_check(p, entity, expect_version):
        cur = p["versions"].get(entity, 0)
        if expect_version is not None and int(expect_version) != cur:
            raise ValidationError("CONFLICT", f"{entity} is at version {cur}, not {expect_version}; re-read and retry")
        return {entity: cur}

    @staticmethod
    def _milestone(p, ident):
        m = p["milestones"].get(ident)
        if not m:
            raise ValidationError("NOT_FOUND", f"milestone {ident} does not exist")
        return m

    @staticmethod
    def _subject(p, subject):
        if subject != "PROJECT" and subject not in p["milestones"]:
            raise ValidationError("NOT_FOUND", f"subject {subject} is neither PROJECT nor a milestone id")
        return subject

    @staticmethod
    def _next_id(p, prefix, width=0):
        n = p["counters"].get(prefix, 0) + 1
        return f"{prefix}-{n:0{width}d}" if width else f"{prefix}-{n}"

    # ------------------------------------------------------------------ milestones

    def create_milestone(self, ident, title, objective=None, priority=None, phase="RESEARCH", depends_on=(),
                         acceptance_ref=None, worktree=None, branch=None, base_commit=None, next_action=None,
                         status="PLANNED", origin=None):
        M.check_id("milestone id", ident)
        def build(p):
            if ident in p["milestones"]:
                raise ValidationError("EXISTS", f"milestone {ident} already exists")
            for dep in depends_on:
                self._milestone(p, dep)
            data = {"id": ident, "title": M.check_text("title", title, True, 200),
                    "objective": M.check_text("objective", objective),
                    "priority": M.check_text("priority", priority, False, 16),
                    "phase": M.check_enum("phase", phase, M.PHASES),
                    "status": M.check_enum("status", status, ("PLANNED", "IN_PROGRESS", "PAUSED")),
                    "depends_on": list(depends_on), "acceptance_ref": M.check_text("acceptance_ref", acceptance_ref),
                    "worktree": M.check_text("worktree", worktree), "branch": M.check_text("branch", branch),
                    "base_commit": M.check_sha("base_commit", base_commit),
                    "next_action": M.check_text("next_action", next_action), "origin": origin}
            return [("MILESTONE_CREATED", data, {ident: 0})]
        return self._write(build)

    def update_milestone(self, ident, expect_version=None, **fields):
        unknown = set(fields) - set(M.MILESTONE_FIELDS)
        if unknown:
            raise ValidationError("BAD_FIELD", f"cannot update {sorted(unknown)} (status, dependencies and assignment "
                                               "have their own commands)")
        clean = {}
        for k, v in fields.items():
            if k == "phase":
                clean[k] = M.check_enum("phase", v, M.PHASES)
            elif k in ("base_commit", "candidate_commit"):
                clean[k] = M.check_sha(k, v)
            elif k == "title":
                clean[k] = M.check_text(k, v, True, 200)
            elif k == "priority":
                clean[k] = M.check_text(k, v, False, 16)
            else:
                clean[k] = M.check_text(k, v)
        if not clean:
            raise ValidationError("MISSING", "nothing to update")
        def build(p):
            self._milestone(p, ident)
            base = self._version_check(p, ident, expect_version)
            return [("MILESTONE_UPDATED", {"id": ident, "fields": clean}, base)]
        return self._write(build)

    def guard_status(self, p, m, status) -> dict:
        """Evidence a positive status needs. Returns the basis recorded with the status, or raises."""
        ident = m["id"]
        if status == "ACCEPTED":
            cand = m.get("candidate_commit")
            if not cand:
                raise ValidationError("NO_CANDIDATE", f"{ident} has no candidate_commit; record the exact commit first")
            good = []
            for r in p["reviews"].values():
                if r["subject"] != ident or r["commit"] != cand:
                    continue
                if (r["verdict"] in M.POSITIVE_VERDICTS and r["blocking_open"] == 0
                        and r["result_class"] == "COMPLETED_WITH_RESULT"
                        and r["assurance"] in M.QUALIFYING_ASSURANCE
                        and r["reviewer"]["id"] not in m["implementers"]):
                    good.append(r["id"])
            if not good:
                raise ValidationError("NO_INDEPENDENT_ACCEPT",
                                      f"{ident} needs an independent review (reviewer not among implementers "
                                      f"{m['implementers']}) with ACCEPT / ACCEPT WITH FINDINGS, no open blocking "
                                      f"finding, result COMPLETED_WITH_RESULT and a qualifying assurance class, on "
                                      f"commit {cand}")
            # A later negative review on the same commit outranks an earlier ACCEPT.
            latest = max((r for r in p["reviews"].values() if r["subject"] == ident and r["commit"] == cand
                          and r["result_class"] == "COMPLETED_WITH_RESULT"),
                         key=lambda r: M.event_key({"ts": r["recorded"]["ts"], "seg": r["recorded"]["seg"],
                                                    "seq": r["recorded"]["seq"]}))
            if latest["verdict"] not in M.POSITIVE_VERDICTS or latest["blocking_open"]:
                raise ValidationError("LATER_NEGATIVE_REVIEW", f"latest review {latest['id']} on {cand} is "
                                                               f"{latest['verdict']} / {latest['blocking_open']} blocking")
            return {"reviews": good, "commit": cand}
        if status == "INTEGRATED":
            appr = [a["id"] for a in p["approvals"].values()
                    if a["subject"] == ident and a["kind"] == "INTEGRATION" and a["status"] == "APPROVED"]
            if not appr:
                raise ValidationError("NO_OWNER_INTEGRATION_APPROVAL",
                                      f"{ident} needs an APPROVED owner approval of kind INTEGRATION")
            integ = m.get("integration")
            if not integ or not integ.get("contains_candidate"):
                raise ValidationError("NO_INTEGRATION_RECORD", f"{ident} needs an integration record whose target "
                                                               "commit contains the candidate commit")
            if m["status"] not in ("ACCEPTED", "INTEGRATED"):
                raise ValidationError("NOT_ACCEPTED", f"{ident} must be ACCEPTED before INTEGRATED")
            return {"approvals": appr, "integration": integ["target_commit"]}
        if status == "DONE":
            if m["status"] not in ("ACCEPTED", "INTEGRATED"):
                raise ValidationError("NOT_ACCEPTED", f"{ident} must be ACCEPTED or INTEGRATED before DONE")
            open_a = [a["id"] for a in p["approvals"].values() if a["subject"] == ident and a["status"] == "REQUESTED"]
            open_b = [b["id"] for b in p["blockers"].values() if b["subject"] == ident and b["status"] == "OPEN"]
            if open_a or open_b:
                raise ValidationError("OPEN_ITEMS", f"{ident} has open approvals {open_a} / blockers {open_b}")
            return {}
        return {}

    def set_status(self, ident, status, reason, expect_version=None):
        M.check_enum("status", status, M.STATUSES)
        M.check_text("reason", reason, True)
        def build(p):
            m = self._milestone(p, ident)
            base = self._version_check(p, ident, expect_version)
            if m["status"] == status:
                raise ValidationError("NO_CHANGE", f"{ident} is already {status}")
            basis = self.guard_status(p, m, status)
            return [("MILESTONE_STATUS_SET", {"id": ident, "status": status, "reason": reason, "basis": basis}, base)]
        return self._write(build)

    def add_dependency(self, ident, on):
        def build(p):
            m = self._milestone(p, ident)
            self._milestone(p, on)
            if on == ident or M.would_cycle(p["milestones"], ident, on):
                raise ValidationError("CYCLE", f"{ident} -> {on} would create a dependency cycle")
            if on in m["depends_on"]:
                raise ValidationError("NO_CHANGE", f"{ident} already depends on {on}")
            return [("DEPENDENCY_ADDED", {"id": ident, "on": on}, {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    def remove_dependency(self, ident, on, reason):
        M.check_text("reason", reason, True)
        def build(p):
            m = self._milestone(p, ident)
            if on not in m["depends_on"]:
                raise ValidationError("NO_CHANGE", f"{ident} does not depend on {on}")
            return [("DEPENDENCY_REMOVED", {"id": ident, "on": on, "reason": reason},
                     {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    def assign(self, ident, hours: float = 4.0, worktree=None, takeover=False):
        if not (0 < float(hours) <= 72):
            raise ValidationError("BAD_VALUE", "lease hours must be in (0, 72]")
        def build(p):
            m = self._milestone(p, ident)
            now = _iso(self.clock())
            cur = m.get("assignment")
            takeover_of = None
            if cur and cur["agent"] != self.actor:
                if cur["expires_at"] > now:
                    raise ValidationError("ASSIGNED", f"{ident} is assigned to {cur['agent']} until "
                                                      f"{cur['expires_at']}")
                if not takeover:
                    raise ValidationError("EXPIRED_ASSIGNMENT", f"{ident} has an expired assignment by "
                                                                f"{cur['agent']}; pass takeover to take it over")
                takeover_of = cur["agent"]
            expires = _iso(self.clock() + datetime.timedelta(hours=float(hours)))
            data = {"id": ident, "agent": self.actor, "session": self.session,
                    "worktree": M.check_text("worktree", worktree), "expires_at": expires, "takeover_of": takeover_of}
            return [("MILESTONE_ASSIGNED", data, {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    def release(self, ident, reason):
        M.check_text("reason", reason, True)
        def build(p):
            m = self._milestone(p, ident)
            cur = m.get("assignment")
            if not cur:
                raise ValidationError("NO_CHANGE", f"{ident} is not assigned")
            if cur["agent"] != self.actor and cur["expires_at"] > _iso(self.clock()):
                raise ValidationError("ASSIGNED", f"only {cur['agent']} can release {ident} before "
                                                  f"{cur['expires_at']}")
            return [("MILESTONE_RELEASED", {"id": ident, "reason": reason}, {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    def record_implementer(self, ident, agent):
        M.check_text("agent", agent, True, 200)
        def build(p):
            m = self._milestone(p, ident)
            if agent in m["implementers"]:
                raise ValidationError("NO_CHANGE", f"{agent} already recorded")
            return [("IMPLEMENTER_RECORDED", {"id": ident, "agent": agent}, {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    # ------------------------------------------------------------------ blockers

    def add_blocker(self, subject, kind, reason, needs):
        M.check_enum("kind", kind, M.BLOCKER_KINDS)
        M.check_text("reason", reason, True)
        M.check_text("needs", needs, True)
        def build(p):
            self._subject(p, subject)
            bid = self._next_id(p, "BLK")
            return [("BLOCKER_ADDED", {"id": bid, "subject": subject, "kind": kind, "reason": reason,
                                       "needs": needs}, {bid: 0})]
        return self._write(build)

    def resolve_blocker(self, bid, resolution):
        M.check_text("resolution", resolution, True)
        def build(p):
            b = p["blockers"].get(bid)
            if not b:
                raise ValidationError("NOT_FOUND", f"blocker {bid} does not exist")
            if b["status"] != "OPEN":
                raise ValidationError("NO_CHANGE", f"{bid} is already resolved")
            return [("BLOCKER_RESOLVED", {"id": bid, "resolution": resolution}, {bid: p["versions"].get(bid, 0)})]
        return self._write(build)

    # ------------------------------------------------------------------ evidence and reviews

    def add_evidence(self, subject, kind, ref, result_class, summary, commit=None, file=None, sha256=None):
        M.check_enum("kind", kind, M.EVIDENCE_KINDS)
        M.check_enum("result_class", result_class, M.RESULT_CLASSES)
        M.check_text("ref", ref, True, 1000)
        M.check_text("summary", summary, True, 1000)
        M.check_sha("commit", commit)
        if file:
            sha256 = file_sha256(Path(file))
        M.check_sha("sha256", sha256, rx=M.SHA256_RE)
        content = {"subject": subject, "kind": kind, "ref": ref, "sha256": sha256, "commit": commit,
                   "result_class": result_class}
        eid = "EV-" + sha256_text(canonical(content))[:16]
        def build(p):
            self._subject(p, subject)
            if eid in p["evidence"]:
                return []  # identical evidence already recorded: deduplicated
            return [("EVIDENCE_ADDED", {"id": eid, **content, "summary": summary}, {eid: 0})]
        self._write(build)
        return eid

    def record_review(self, subject, commit, reviewer_kind, reviewer_id, assurance, verdict, blocking_open,
                      findings_total, result_class, summary, evidence=()):
        M.check_sha("commit", commit, required=True)
        M.check_enum("reviewer_kind", reviewer_kind, M.REVIEWER_KINDS)
        M.check_text("reviewer_id", reviewer_id, True, 200)
        M.check_enum("assurance", assurance, M.ASSURANCE)
        M.check_enum("verdict", verdict, M.VERDICTS)
        M.check_enum("result_class", result_class, M.RESULT_CLASSES)
        M.check_text("summary", summary, True, 2000)
        if int(blocking_open) < 0 or int(findings_total) < int(blocking_open):
            raise ValidationError("BAD_VALUE", "need 0 <= blocking_open <= findings_total")
        if verdict in M.POSITIVE_VERDICTS and int(blocking_open):
            raise ValidationError("INCONSISTENT", "a positive verdict cannot have open blocking findings")
        def build(p):
            self._subject(p, subject)
            for e in evidence:
                if e not in p["evidence"]:
                    raise ValidationError("NOT_FOUND", f"evidence {e} does not exist")
            rid = self._next_id(p, "RV")
            return [("REVIEW_RECORDED", {"id": rid, "subject": subject, "commit": commit,
                                         "reviewer": {"kind": reviewer_kind, "id": reviewer_id},
                                         "assurance": assurance, "verdict": verdict,
                                         "blocking_open": int(blocking_open), "findings_total": int(findings_total),
                                         "result_class": result_class, "summary": summary,
                                         "evidence": list(evidence)}, {rid: 0})]
        return self._write(build)

    # ------------------------------------------------------------------ approvals

    def request_approval(self, subject, kind, question, alias=None, origin=None):
        M.check_enum("kind", kind, M.APPROVAL_KINDS)
        M.check_text("question", question, True)
        def build(p):
            self._subject(p, subject)
            if alias and any(a.get("alias") == alias for a in p["approvals"].values()):
                return []
            aid = self._next_id(p, "AP")
            return [("APPROVAL_REQUESTED", {"id": aid, "subject": subject, "kind": kind, "question": question,
                                            "alias": alias, "origin": origin}, {aid: 0})]
        return self._write(build)

    def resolve_approval(self, aid, outcome, owner_words=None, source=None, reason=None):
        """Record the owner's answer as relayed by the acting agent (assurance OWNER_RELAYED).

        APPROVED and DENIED need the owner's own words and where they were given. The tool cannot prove the owner
        said them; it records who relayed them, so a false relay is attributable."""
        M.check_enum("outcome", outcome, M.APPROVAL_OUTCOMES)
        if outcome in ("APPROVED", "DENIED"):
            M.check_text("owner_words", owner_words, True)
            M.check_text("source", source, True, 500)
        else:
            M.check_text("reason", reason, True)
        def build(p):
            a = p["approvals"].get(aid)
            if not a:
                raise ValidationError("NOT_FOUND", f"approval {aid} does not exist")
            if a["status"] != "REQUESTED":
                raise ValidationError("NO_CHANGE", f"{aid} is already {a['status']}")
            data = {"id": aid, "outcome": outcome, "owner_words": owner_words, "source": source, "reason": reason,
                    "assurance": "OWNER_RELAYED" if outcome != "WITHDRAWN" else "AGENT"}
            return [("APPROVAL_RESOLVED", data, {aid: p["versions"].get(aid, 0)})]
        return self._write(build)

    # ------------------------------------------------------------------ decisions

    def record_decision(self, title, decision, date, evidence_class, source, ident=None, proposal=None,
                        reasoning=None, alternatives_rejected=None, related=(), consequences=None,
                        approval_ref=None, supersedes=None, partial=False, note=None):
        M.check_text("title", title, True, 300)
        M.check_text("decision", decision, True)
        M.check_text("date", date, True, 40)
        M.check_enum("evidence_class", evidence_class, M.EVIDENCE_CLASSES)
        M.check_text("source", source, True, 1000)
        for name in ("proposal", "reasoning", "alternatives_rejected", "consequences"):
            M.check_text(name, locals()[name])
        if ident:
            M.check_id("decision id", ident, M.DEC_RE)
        def build(p):
            did = ident or self._next_id(p, "DEC", 3)
            if did in p["decisions"]:
                raise ValidationError("EXISTS", f"decision {did} already exists; decisions are never overwritten "
                                                "(use supersede or correct)")
            if approval_ref and approval_ref not in p["approvals"]:
                raise ValidationError("NOT_FOUND", f"approval {approval_ref} does not exist")
            if supersedes and supersedes not in p["decisions"]:
                raise ValidationError("NOT_FOUND", f"decision {supersedes} does not exist")
            data = {"id": did, "title": title, "decision": decision, "date": date, "evidence_class": evidence_class,
                    "source": {"text": source}, "proposal": proposal, "reasoning": reasoning,
                    "alternatives_rejected": alternatives_rejected, "related": list(related),
                    "consequences": consequences, "approval_ref": approval_ref, "imported": False}
            items = [("DECISION_RECORDED", data, {did: 0})]
            if supersedes:
                items.append(("DECISION_SUPERSEDED", {"id": supersedes, "by": did, "partial": bool(partial),
                                                      "note": note}, {supersedes: p["versions"].get(supersedes, 0)}))
            return items
        return self._write(build)

    def supersede_decision(self, ident, by, partial=False, note=None):
        M.check_text("note", note)
        def build(p):
            for d in (ident, by):
                if d not in p["decisions"]:
                    raise ValidationError("NOT_FOUND", f"decision {d} does not exist")
            if ident == by:
                raise ValidationError("BAD_VALUE", "a decision cannot supersede itself")
            if any(s["by"] == by for s in p["decisions"][ident]["superseded_by"]):
                raise ValidationError("NO_CHANGE", f"{ident} is already superseded by {by}")
            return [("DECISION_SUPERSEDED", {"id": ident, "by": by, "partial": bool(partial), "note": note},
                     {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    def correct_decision(self, ident, correction, evidence_class, source):
        M.check_text("correction", correction, True)
        M.check_enum("evidence_class", evidence_class, M.EVIDENCE_CLASSES)
        M.check_text("source", source, True, 1000)
        def build(p):
            if ident not in p["decisions"]:
                raise ValidationError("NOT_FOUND", f"decision {ident} does not exist")
            return [("DECISION_CORRECTED", {"id": ident, "correction": correction, "evidence_class": evidence_class,
                                            "source": source}, {ident: p["versions"].get(ident, 0)})]
        return self._write(build)

    # ------------------------------------------------------------------ handoff, lifecycle, integration, conflicts

    def record_handoff(self, subject, summary, done=None, next_action=None, files=(), commit=None):
        M.check_text("summary", summary, True, 2000)
        M.check_text("done", done)
        M.check_text("next", next_action)
        M.check_sha("commit", commit)
        files = [M.check_text("file", f, True, 500) for f in files][: M.MAX_LIST]
        def build(p):
            self._subject(p, subject)
            hid = self._next_id(p, "HO")
            return [("HANDOFF_RECORDED", {"id": hid, "subject": subject, "summary": summary, "done": done,
                                          "next": next_action, "files": files, "commit": commit}, {hid: 0})]
        return self._write(build)

    def link_lifecycle(self, subject, state_dir, config_path=None):
        state_dir = str(Path(state_dir))
        def build(p):
            m = self._milestone(p, subject)
            if any(x["state_dir"] == state_dir for x in m["lifecycle"]):
                return []
            return [("LIFECYCLE_LINKED", {"subject": subject, "state_dir": state_dir, "config_path": config_path},
                     {subject: p["versions"].get(subject, 0)})]
        return self._write(build)

    def sync_lifecycle(self, subject, state_dir):
        from scripts.dev_workflow.milestones.importers import read_lifecycle_snapshot
        state_dir = str(Path(state_dir))
        snap = read_lifecycle_snapshot(state_dir)
        def build(p):
            m = self._milestone(p, subject)
            if not any(x["state_dir"] == state_dir for x in m["lifecycle"]):
                raise ValidationError("NOT_LINKED", f"{state_dir} is not linked to {subject}; run link-lifecycle")
            return [("LIFECYCLE_SYNCED", {"subject": subject, "state_dir": state_dir, "snapshot": snap},
                     {subject: p["versions"].get(subject, 0)})]
        self._write(build)
        return snap

    def record_integration(self, subject, target_ref, target_commit, repo=None):
        M.check_text("target_ref", target_ref, True, 300)
        M.check_sha("target_commit", target_commit, required=True)
        def build(p):
            m = self._milestone(p, subject)
            cand = m.get("candidate_commit")
            if not cand:
                raise ValidationError("NO_CANDIDATE", f"{subject} has no candidate_commit")
            if repo:
                r = subprocess.run([*GIT, "-C", str(repo), "merge-base", "--is-ancestor", cand, target_commit],
                                   capture_output=True, text=True)
                if r.returncode not in (0, 1):
                    raise ValidationError("GIT", f"cannot check ancestry in {repo}: {r.stderr.strip()[:200]}")
                contains, how = r.returncode == 0, f"git merge-base --is-ancestor in {repo}"
            else:
                contains, how = cand == target_commit, "candidate equals target (no repository given)"
            if not contains:
                raise ValidationError("NOT_CONTAINED", f"{target_commit} does not contain candidate {cand}")
            return [("INTEGRATION_RECORDED", {"subject": subject, "target_ref": target_ref,
                                              "target_commit": target_commit, "candidate_commit": cand,
                                              "contains_candidate": True, "verified_by": how},
                     {subject: p["versions"].get(subject, 0)})]
        return self._write(build)

    def resolve_conflict(self, entity, note):
        M.check_text("note", note, True)
        def build(p):
            if not any(c["entity"] == entity and not c["resolved"] for c in p["conflicts"]):
                raise ValidationError("NOT_FOUND", f"no open conflict on {entity}")
            return [("CONFLICT_RESOLVED", {"entity": entity, "note": note}, {})]
        return self._write(build)

    # ------------------------------------------------------------------ evidence checking and tasks

    def check_evidence(self) -> list[dict]:
        """Re-hash every evidence file that is a local path; report missing or changed files (read-only)."""
        out = []
        for e in self.projection()["evidence"].values():
            path = Path(e["ref"])
            if not e.get("sha256") or not path.is_absolute():
                continue
            if not path.is_file():
                out.append({"id": e["id"], "ref": e["ref"], "problem": "MISSING"})
            elif file_sha256(path) != e["sha256"]:
                out.append({"id": e["id"], "ref": e["ref"], "problem": "CHANGED"})
        return out

    def task_summaries(self, milestone_ref) -> dict:
        """Lifecycle V3.1 task summaries for a milestone (read-only, contract uri-dev/task-ledger-contract/1)."""
        if self.task_source is not None:
            return self.task_source(milestone_ref)
        repo_root = Path(__file__).resolve().parents[3]
        if not (repo_root / "scripts" / "dev_workflow" / "task_ledger.py").is_file():
            return {"available": False, "reason": "Lifecycle V3.1 task ledger is not installed in this checkout"}
        try:
            r = subprocess.run([os.environ.get("PYTHON", "python"), "-m", "scripts.dev_workflow.task_ledger",
                                "summary", "--milestone", milestone_ref, "--json"], cwd=repo_root,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"available": False, "reason": f"task ledger did not run: {e.__class__.__name__}"}
        # Contract (agreed with the V3.1 session 2026-10-21): exit 0 = verified data; 4 = LEDGER_INTEGRITY_FAILED;
        # 3 = refused; 2 = error.
        if r.returncode:
            return {"available": False, "reason": f"task ledger exit {r.returncode}: {r.stderr.strip()[:200]}",
                    "integrity_failure": r.returncode == 4}
        try:
            tasks = json.loads(r.stdout)
        except ValueError:
            return {"available": False, "reason": "task ledger output is not JSON", "integrity_failure": True}
        if not isinstance(tasks, list):
            return {"available": False, "reason": "task ledger output is not a list", "integrity_failure": True}
        return {"available": True, "tasks": tasks}
