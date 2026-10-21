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
from scripts.dev_workflow.milestones.store import (GIT, EventStore, StoreError, canonical,
                                                   file_sha256, read_segment, sha256_text)

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
        self.last_autocommit = None

    # ------------------------------------------------------------------ projection

    def projection(self) -> dict:
        """Fold of the verified log. Always derived from the event segments; nothing is trusted from a cache
        (review R1-02/R1-06/R1-08: a cache that guards read could be forged or stale). 10,000 events fold in well
        under a second (criterion N3)."""
        segs = self.store.read_all()
        return self._fold_segments(segs)

    rebuild = projection

    def _fold_segments(self, segs) -> dict:
        state = M.fold(M.ordered(segs))
        errors = [e for s in segs for e in s.errors] + self.store.anchor_errors(segs)
        warnings = [f"{s.name}: {len(s.torn)} torn bytes at the end (ignored; `recover` on that host)"
                    for s in segs if s.torn]
        warnings += [f"incomplete batch {b} ({len(evs)} of {evs[0]['batch']['n']} events; ignored)"
                     for b, evs in state.get("pending_batches", {}).items()]
        state["integrity_errors"] = errors
        state["integrity_warnings"] = warnings
        return state

    # ------------------------------------------------------------------ write helper

    def _require_actor(self):
        if not self.actor or not isinstance(self.actor, str) or len(self.actor) > 200:
            raise ValidationError("NO_ACTOR", "an --actor (or URI_MM_ACTOR) identifying the agent is required for writes")
        if M.find_secret(self.actor) or M.find_secret(self.session or ""):
            raise ValidationError("SECRET", "actor/session looks like a secret")

    def _write(self, build):
        """``build(p)`` validates against the verified projection ``p`` and returns [(kind, data, base), ...].

        All events of one call are appended as one batch (single write + fsync); the fold applies a batch only when
        it is complete, so a crash never leaves half a command applied (R1-15)."""
        self._require_actor()
        with self.store.locked():
            segs = self.store.read_all()
            p = self._fold_segments(segs)
            if p["integrity_errors"]:
                raise StoreError("CHAIN_BROKEN", "ledger fails verification; run `verify` (" +
                                 "; ".join(p["integrity_errors"][:2]) + ")")
            items = build(p)
            for kind, data, _ in items:
                hit = M.find_secret(data)
                if hit:
                    raise ValidationError("SECRET", f"{kind} contains what looks like a {hit}; secrets are never "
                                                    "stored (record a reference instead)")
            written = self.store.append_many(items, actor=self.actor, session=self.session)
            for ev in written:
                M.apply(p, ev)
            if written:
                own = read_segment(self.store.segment_path)
                self.store.write_anchors([s for s in segs if s.name != own.name] + [own])
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
            m = self._milestone(p, ident)
            base = self._version_check(p, ident, expect_version)
            if "candidate_commit" in clean and m["status"] in ("ACCEPTED", "INTEGRATED", "DONE") \
                    and clean["candidate_commit"] != m.get("candidate_commit"):
                raise ValidationError("CANDIDATE_LOCKED", f"{ident} is {m['status']} on {m.get('candidate_commit')}; "
                                                          "set it back to IN_PROGRESS before naming a new candidate "
                                                          "(the new commit needs its own independent review)")
            return [("MILESTONE_UPDATED", {"id": ident, "fields": clean}, base)]
        return self._write(build)

    def _independent_accept(self, p, m) -> list[str]:
        """Qualifying independent ACCEPT reviews on the current candidate; raises unless the latest review on that
        commit is positive (a later negative review outranks an earlier ACCEPT, R1-03)."""
        ident = m["id"]
        cand = m.get("candidate_commit")
        if not cand:
            raise ValidationError("NO_CANDIDATE", f"{ident} has no candidate_commit; record the exact commit first")
        implementers = {M.norm_id(a) for a in m["implementers"]}
        on_cand = [r for r in p["reviews"].values() if r["subject"] == ident and r["commit"] == cand
                   and r["result_class"] == "COMPLETED_WITH_RESULT"]
        good = [r["id"] for r in on_cand
                if r["verdict"] in M.POSITIVE_VERDICTS and r["blocking_open"] == 0
                and r["assurance"] in M.QUALIFYING_ASSURANCE and M.norm_id(r["reviewer"]["id"]) not in implementers]
        if not good:
            raise ValidationError("NO_INDEPENDENT_ACCEPT",
                                  f"{ident} needs an independent review (reviewer not among implementers "
                                  f"{m['implementers']}) with ACCEPT / ACCEPT WITH FINDINGS, no open blocking "
                                  f"finding, result COMPLETED_WITH_RESULT and a qualifying assurance class, on "
                                  f"commit {cand}")
        latest = max(on_cand, key=lambda r: (r["recorded"]["ts"], r["recorded"]["seg"], r["recorded"]["seq"]))
        if latest["verdict"] not in M.POSITIVE_VERDICTS or latest["blocking_open"]:
            raise ValidationError("LATER_NEGATIVE_REVIEW", f"latest review {latest['id']} on {cand} is "
                                                           f"{latest['verdict']} / {latest['blocking_open']} blocking")
        return good

    def guard_status(self, p, m, status) -> dict:
        """Evidence a positive status needs. Returns the basis recorded with the status, or raises."""
        ident = m["id"]
        if status in ("ACCEPTED", "INTEGRATED", "DONE"):
            open_c = [c for c in p["conflicts"] if not c["resolved"] and (c.get("subject") == ident
                                                                           or c["entity"] == ident)]
            if open_c:
                raise ValidationError("CONFLICT_OPEN", f"{ident} has {len(open_c)} unresolved conflict(s) "
                                                       f"({open_c[0]['type']}); resolve them first")
        if status == "ACCEPTED":
            return {"reviews": self._independent_accept(p, m), "commit": m["candidate_commit"]}
        if status == "INTEGRATED":
            if m["status"] not in ("ACCEPTED", "INTEGRATED"):
                raise ValidationError("NOT_ACCEPTED", f"{ident} must be ACCEPTED before INTEGRATED")
            reviews = self._independent_accept(p, m)
            appr = [a["id"] for a in p["approvals"].values()
                    if a["subject"] == ident and a["kind"] == "INTEGRATION" and a["status"] == "APPROVED"]
            if not appr:
                raise ValidationError("NO_OWNER_INTEGRATION_APPROVAL",
                                      f"{ident} needs an APPROVED owner approval of kind INTEGRATION")
            integ = m.get("integration")
            if not integ or not integ.get("contains_candidate") \
                    or integ.get("candidate_commit") != m.get("candidate_commit"):
                raise ValidationError("NO_INTEGRATION_RECORD", f"{ident} needs an integration record for its current "
                                                               f"candidate {m.get('candidate_commit')}")
            return {"approvals": appr, "reviews": reviews, "integration": integ["target_commit"]}
        if status == "DONE":
            if m["status"] not in ("ACCEPTED", "INTEGRATED"):
                raise ValidationError("NOT_ACCEPTED", f"{ident} must be ACCEPTED or INTEGRATED before DONE")
            reviews = self._independent_accept(p, m)
            open_a = [a["id"] for a in p["approvals"].values() if a["subject"] == ident and a["status"] == "REQUESTED"]
            open_b = [b["id"] for b in p["blockers"].values() if b["subject"] == ident and b["status"] == "OPEN"]
            if open_a or open_b:
                raise ValidationError("OPEN_ITEMS", f"{ident} has open approvals {open_a} / blockers {open_b}")
            return {"reviews": reviews}
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
