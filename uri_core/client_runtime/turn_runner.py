"""C5 client-side turn runner: the client half of the paired canonical loop.

The server only proposes/gates/signs. This runner (the client's trusted code) owns private
state, user approval, local execution, INDEPENDENT verification and persistence.
Nothing here trusts a harness's or server's claim of success.

Execution order (never reordered): journal.intent -> online claim -> journal.acknowledge ->
execute -> independent verify -> journal.settle -> online settle -> persist history.
"""
from __future__ import annotations

import hashlib
import uuid

from uri_core.client_contracts import Binding, ReadQuery, canonical, digest
from uri_core.client_runtime.execution_journal import ExecutionJournal
from uri_core.core.client_execution_control import verify_ticket
from uri_core.core.client_state_ports import ClientStatePorts

# Pre-launch refusal: nothing that could have an effect was started. Any other failure after dispatch is
# settled by the server as execution_uncertain (a write may have landed; a harness may have acted).
NOT_STARTED = "NOT_STARTED:"


class TurnError(RuntimeError):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


def uid():
    return str(uuid.uuid4())


class TurnRunner:
    def __init__(self, manifest, persistence, call, server_public_key, generation, journal=None, clock=None, harness=None):
        """`call(method, path, body|None) -> (status, json)` is the only network seam."""
        self.m = manifest.data
        self.persistence, self.call, self.server_public_key = persistence, call, server_public_key
        self.journal = journal
        self.harness = harness   # HarnessRegistry; None = no external harness available
        # Server generation must come from a verified signed identity proof, never from a ticket.
        self.generation = generation
        import time
        self.clock = clock or time.time

    # ---- helpers ---------------------------------------------------------------------------
    def _binding(self, session):
        return {k: self.m[k] for k in ("server_id", "client_id", "principal_id")} | {"session_id": session}

    def _post(self, path, body):
        status, data = self.call("POST", path, body)
        if status != 200:
            raise TurnError("SERVER_REFUSED:" + str(data.get("detail") if isinstance(data, dict) else status), data)
        return data

    def _control(self, session, record, **extra):
        return {**self._binding(session), "expected_version": record["version"], "idempotency_key": uid(), **extra}

    def _mutations(self, session, changes):
        """changes: [(store, read_method, read_args, write_method, write_kwargs[, replacement])] as in C3."""
        queries = [ReadQuery(store=c[0], method=c[1], args=c[2]) for c in changes]
        snapshot = self.persistence.snapshot(session, queries)
        ports = ClientStatePorts(snapshot, Binding(**self._binding(session)).model_dump())
        for store, _, _, method, kwargs, *replacement in changes:
            reads = sorted([r.model_dump() for r in snapshot.reads if r.query.store == store], key=lambda r: digest(r["query"]))
            ports.propose(store, method, kwargs=kwargs, base_version=reads[0]["store_version"], previous_digest=digest(reads),
                          replacement=replacement[0] if replacement else None)
        return ports.mutation_set(uid(), uid())

    def _commit_consented(self, session, changes):
        mutation_set = self._mutations(session, changes)
        self.persistence.consent(mutation_set)   # trusted local consent; the user approved above
        return self.persistence.commit(mutation_set)

    BASE_READS = (("sessions", "get_session"), ("history", "get_session"), ("files", "list_for_session"))

    def _snapshot(self, session, extra=()):
        # Session-first context the server may use: session state, transcript and this session's files.
        return self.persistence.snapshot(session, [ReadQuery(store=s, method=m, args=[session]) for s, m in self.BASE_READS]
                                         + list(extra))

    # ---- the loop ----------------------------------------------------------------------------
    def begin(self, text, session, reasoning, intent_decision=None):
        """Start a turn. If the result is approval_required the caller must decide().

        intent_decision: the user's explicit structured confirm/abandon/select for a pending intent."""
        body = {**self._binding(session), "request_id": uid(), "idempotency_key": uid(), "text": text,
                "snapshot": self._snapshot(session).model_dump(), "reasoning": reasoning}
        if intent_decision is not None:
            body["intent_decision"] = intent_decision
        turn = self._post("/client/v1/turns", body)
        extra = []
        for _ in range(3):   # server-requested context (e.g. ARN cold-start retrieval); bounded
            if turn["state"] != "needs_context":
                break
            extra += [ReadQuery.model_validate(r) for r in turn.get("reads") or []]
            turn = self._post(f"/client/v1/turns/{turn['turn_id']}/continue", {
                **self._binding(session), "expected_version": turn["version"], "idempotency_key": uid(),
                "snapshot": self._snapshot(session, extra).model_dump()})
        if turn["state"] == "approval_required":
            return turn
        return self._finish(session, text, turn, turn.get("message"))

    def confirm(self, session, reasoning, turn):
        """Explicitly confirm the intent shown in `turn` (digest-bound). Returns the next turn envelope."""
        c = turn["confirmation"]
        return self.begin("Confirm", session, reasoning, {"intent_id": c["intent_id"], "revision": c["revision"],
                                                         "decision": "confirm", "digest": c["digest"]})

    def select(self, session, reasoning, turn, candidate_id):
        c = turn["clarification"]
        return self.begin("Selected option", session, reasoning, {"intent_id": c["intent_id"], "revision": c["revision"],
                                                                  "decision": "select", "candidate_id": candidate_id})

    def abandon(self, session, reasoning, turn):
        c = turn.get("confirmation") or turn.get("clarification")
        return self.begin("Cancel that request", session, reasoning,
                          {"intent_id": c["intent_id"], "revision": c["revision"], "decision": "abandon"})

    def decide(self, text, session, reasoning, turn, approved):
        """Apply the user's explicit decision to an approval_required turn."""
        request = turn["approval_request"]
        pending_session, intent = turn.get("session_update"), turn.get("intent")
        turn = self._post(f"/client/v1/turns/{turn['turn_id']}/approval", self._control(
            session, turn, decision="approve" if approved else "deny", approval_digest=request["approval_digest"]))
        if pending_session is not None:
            turn.setdefault("session_update", pending_session)
        if not approved:
            return self._finish(session, text, turn, "You declined; nothing was changed.", approval=request, intent=intent)
        return self._execute(session, text, turn, request, reasoning, intent)

    def run(self, text, session, reasoning, approve):
        """approve(approval_request) -> bool is the user's explicit decision. Returns final envelope."""
        turn = self.begin(text, session, reasoning)
        if turn["state"] != "approval_required":
            return turn
        return self.decide(text, session, reasoning, turn, bool(approve(turn["approval_request"])))

    def _execute(self, session, text, turn, request, reasoning, intent=None):
        signed = turn["ticket"]
        ticket = signed["ticket"]
        self._ctx = (session, request)    # per-turn validation context (journal outlives a single turn)
        if self.journal is None:
            self.journal = ExecutionJournal(self.m["client_root"], validate_ticket=self._validate_ticket)
        self.journal.intent(signed)                       # durable intent BEFORE the online claim
        claimed = self._post(f"/client/v1/turns/{turn['turn_id']}/claim", self._control(
            session, turn, ticket=signed, execution_version=0))
        if claimed["claim"]["dispatch"] is not True:
            raise TurnError("CLAIM_DID_NOT_AUTHORIZE_DISPATCH")
        self.journal.acknowledge(signed, claimed["claim"])
        outcome, evidence, failure = self._run_local(session, request, reasoning)
        if outcome == "quota":
            return self._quota_wait(session, text, turn, claimed, signed, ticket, request, reasoning, intent)
        receipt = self._receipt(session, turn, ticket, outcome, evidence, failure)
        self.journal.settle(receipt)
        final = self._post(f"/client/v1/turns/{turn['turn_id']}/settle", self._control(
            session, claimed, ticket=signed, receipt=receipt))
        if turn.get("session_update") is not None:
            final.setdefault("session_update", turn["session_update"])
        return self._finish(session, text, final, final.get("message"), approval=request, intent=intent)

    def _receipt(self, session, turn, ticket, outcome, evidence, failure):
        return {**self._binding(session), "turn_id": turn["turn_id"], "operation_id": ticket["operation_id"],
                "ticket_digest": digest(ticket), "run_id": uid(), "outcome": outcome,
                "verifier_id": ticket["verifier_id"], "implementation_digest": ticket["implementation_digest"],
                "state_version": 1, "evidence": evidence, "failure_category": failure, "schema_version": "uri.client.v1"}

    def _quota_wait(self, session, text, turn, claimed, signed, ticket, request, reasoning, intent=None):
        """Provider quota: preserve the task, close the ticket without any verified effect, never switch."""
        from pathlib import Path
        import json
        checkpoint = {"text": text, "session": session, "turn_id": turn["turn_id"], "tried": reasoning,
                      "argument_digest": request["argument_digest"]}
        cp_digest = digest(checkpoint)
        folder = Path(self.m["client_root"]) / "control/checkpoints"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (turn["turn_id"] + ".json")).write_text(json.dumps({**checkpoint, "digest": cp_digest}))
        waiting = self._post(f"/client/v1/turns/{turn['turn_id']}/wait", self._control(
            session, claimed, checkpoint_digest=cp_digest))
        receipt = self._receipt(session, turn, ticket, "cancelled", [], "QUOTA_EXHAUSTED")
        self.journal.settle(receipt)
        final = self._post(f"/client/v1/turns/{turn['turn_id']}/settle", self._control(
            session, waiting, ticket=signed, receipt=receipt))
        if turn.get("session_update") is not None:
            final.setdefault("session_update", turn["session_update"])
        return self._finish(session, text, final, final.get("message"), approval=request, intent=intent)

    def continue_waiting(self, session, turn_id, new_reasoning, approve):
        """User explicitly picks another provider for a quota-paused task. Fresh turn, fresh approval."""
        from pathlib import Path
        import json
        path = Path(self.m["client_root"]) / "control/checkpoints" / (turn_id + ".json")
        cp = json.loads(path.read_text())
        if cp["session"] != session or digest({k: cp[k] for k in ("text", "session", "turn_id", "tried", "argument_digest")}) != cp["digest"]:
            raise TurnError("CHECKPOINT_INVALID")
        if cp.get("consumed"):
            # Fifth review: a checkpoint is ONE explicit continuation. Once an attempt was dispatched from it,
            # the task's state is that attempt's outcome (verified, failed, uncertain, or its own new
            # checkpoint); re-running the same task from the old checkpoint would bypass the uncertainty of
            # the later attempt. The user may still make a new explicit request.
            raise TurnError("CHECKPOINT_CONSUMED")
        if new_reasoning == cp["tried"]:
            raise TurnError("SAME_PROVIDER_REQUIRES_NEW_CHOICE")
        path.write_text(json.dumps({**cp, "consumed": True}))   # before dispatch: a crash mid-run must not revive it
        return self.run(cp["text"], session, new_reasoning, approve)

    def _validate_ticket(self, value):
        session, request = self._ctx
        return bool(verify_ticket(value, self.server_public_key, self._binding(session), generation=self.generation,
                                  now=self.clock(), argument_digest=request["argument_digest"],
                                  workspace_handle=value["ticket"]["workspace_handle"], workspace_version=0))

    def _run_harness(self, session, request, reasoning):
        from pathlib import Path
        import shutil
        from uri_core.client_runtime import harness as h
        if self.harness is None:
            return "failed", [], NOT_STARTED + "NO_HARNESS_REGISTRY"
        provider = reasoning["provider"]
        inputs = request["arguments"]["inputs"]
        expected = inputs["expected_file"]
        if Path(expected).name != expected:
            return "failed", [], NOT_STARTED + "EXPECTED_FILE_INVALID"
        run_id = uid()
        work = Path(self.m["client_root"]) / "workspace" / run_id
        work.mkdir(parents=True)
        try:
            capsule = h.Capsule(run_id=run_id, workspace=str(work.resolve()), timeout_s=120, inactivity_s=60,
                instructions=(inputs["instruction"] + "\nWrite the result to a file named " + expected
                              + " in the working directory.").encode())
            argv, env, prompt = self.harness.invoke(provider, capsule)
        except h.HarnessError as exc:
            return "failed", [], NOT_STARTED + "HARNESS_" + str(exc)
        proc = h.supervise(argv, cwd=work, env=env, stdin_bytes=prompt, timeout_s=capsule.timeout_s,
                           inactivity_s=capsule.inactivity_s, log_path=work.parent / (run_id + ".log"))
        claim = self.harness.parse(provider, proc)
        if not proc.contained:
            return "execution_uncertain", [], "CONTAINMENT_UNCONFIRMED"
        if claim["claimed_outcome"] == "quota_exhausted":
            # A quota pause may close the attempt "without effect" only when the harness requested no tool
            # action before the limit hit. After any tool_use the workspace, or anything the harness could
            # reach, may already have changed; containment beyond the workspace is not qualified, so the
            # attempt is uncertain (never a clean pause that re-runs the same task on another provider).
            if claim["usage"].get("tool_calls") == 0:
                return "quota", [], "QUOTA"
            return "execution_uncertain", [], "QUOTA_AFTER_TOOL_ACTIVITY"
        if claim["claimed_outcome"] != "completed_claimed":
            return ("execution_uncertain" if claim["claimed_outcome"] == "outcome_unknown" else "failed"), [], claim["error_family"]
        # Independent verification: URI inspects the workspace itself; the harness claim is only a claim.
        out = work / expected
        if not out.is_file() or out.is_symlink() or out.stat().st_size == 0:
            return "failed", [], "OUTPUT_MISSING_FALSE_CLAIM"
        data = out.read_bytes()
        dest = Path(self.m["client_root"]) / "workspace/results" / run_id
        dest.mkdir(parents=True)
        shutil.copyfile(out, dest / expected)   # copy-out only after verification
        return "verified", [{"check": "harness_output_check", "argument_digest": request["argument_digest"],
                             "verifier_id": "uri.client.harness_output_check.v1", "matched": True,
                             "output_sha256": hashlib.sha256(data).hexdigest(), "output_bytes": len(data),
                             "harness": provider}], None

    def _run_local(self, session, request, reasoning=None):
        """Local reversible execution + independent read-back. Returns (outcome, evidence, failure)."""
        if request["capability_id"] == "external_harness_task":
            return self._run_harness(session, request, reasoning)
        if request["capability_id"] != "remember_fact":
            return "failed", [], NOT_STARTED + "NO_LOCAL_EXECUTOR"
        content = self._fact(request["arguments"]["inputs"]["request_text"])
        try:
            self._commit_consented(session, [("memory", "list_all", [], "add",
                                              {"category": "explicit_statement", "content": content})])
        except Exception as exc:   # rollback is automatic in the C3 journal
            return "failed", [], (type(exc).__name__ + ":" + str(exc))[:120]
        # Independent verification: fresh snapshot read, not the write result.
        snap = self.persistence.snapshot(session, [ReadQuery(store="memory", method="list_all")])
        stored = snap.reads[0].result
        matched = any(isinstance(item, dict) and isinstance(item.get("fact"), dict)
                      and item["fact"].get("value") == content and item.get("consent") == "user_provided" for item in stored)
        if not matched:
            return "failed", [], "READBACK_MISMATCH"
        return "verified", [{"check": "memory_readback", "argument_digest": request["argument_digest"],
                             "verifier_id": "uri.client.memory_readback.v1", "matched": True,
                             "content_sha256": hashlib.sha256(content.encode()).hexdigest()}], None

    @staticmethod
    def _fact(text):
        from uri_core.tools.remember_fact import RememberFactTool
        return RememberFactTool._extract_content(text)

    PROVENANCE = "uri.turn.provenance.v1"
    PROVENANCE_LIMIT = 4096   # bytes of canonical JSON; the history query itself is limited to 16 KiB

    @classmethod
    def _provenance(cls, turn, approval, intent):
        """Client-private, durable record of what URI believed the intent was (slot values and whether each came
        from the user's words, an interpreter or a correction), which referent it bound, what it showed for
        confirmation, what the user approved (exact arguments and digests) and how execution settled. Kept with
        the transcript turn so a later wrong outcome can be traced to the user's words, the Brain, the binding,
        the approval or the executor (fifth review: the signed intent record is cleared once the request
        completes, so without this nothing durable carried the interpretation lineage)."""
        intent = intent or turn.get("intent")
        record = {"kind": cls.PROVENANCE, "code": turn.get("code"), "state": turn.get("state")}
        if intent:
            record["intent"] = {k: v for k, v in intent.items() if k != "request"}   # request = that turn's user_text
        for key in ("clarification", "confirmation"):
            if turn.get(key) is not None:
                # Copy: truncation below pops keys, and turn[key] is the envelope returned to the caller/UI
                # (final review: popping in place removed the confirmation arguments the user must see).
                record[key] = dict(turn[key])
        if approval:
            record["approval"] = {k: approval.get(k) for k in ("capability_id", "argument_digest", "approval_digest",
                                                                "arguments", "intent_digest", "replanned", "rejected_proposal")}
        if turn.get("execution") is not None:
            record["execution"] = turn["execution"]
        if len(record) <= 3:
            return None
        if len(canonical(record)) > cls.PROVENANCE_LIMIT:
            # Bounded: the transcript turn already carries the user's words and the rendered confirmation; the
            # digests still bind the (dropped) long values, so the lineage stays verifiable without doubling them.
            full_digest = digest(record)
            for key in ("values", "corrections", "superseded"):
                record.get("intent", {}).pop(key, None)
            record.get("confirmation", {}).pop("arguments", None)
            record.get("clarification", {}).pop("options", None)
            record["truncated"] = True
            if len(canonical(record)) > cls.PROVENANCE_LIMIT:
                # Final review: long titles in the question/referent or long approved arguments could still
                # exceed the bound. Keep only the fixed-size lineage (ids, sources, digests, states).
                def pick(src, keys):
                    return {k: src[k] for k in keys if isinstance(src, dict) and k in src}
                record = {"kind": cls.PROVENANCE, "code": record.get("code"), "state": record.get("state"),
                          "truncated": "digest_only", "record_digest": full_digest,
                          "intent": pick(record.get("intent"), ("intent_id", "revision", "status", "capability",
                                                                "sources", "questions_asked", "digest")),
                          "confirmation": pick(record.get("confirmation"), ("intent_id", "revision", "digest")),
                          "approval": pick(record.get("approval"), ("capability_id", "argument_digest",
                                                                    "approval_digest", "intent_digest", "replanned")),
                          "execution": record.get("execution")}
                record = {k: v for k, v in record.items() if v not in ({}, None)}
                if len(canonical(record)) > cls.PROVENANCE_LIMIT:
                    record = {"kind": cls.PROVENANCE, "truncated": "digest_only", "record_digest": full_digest}
        return record

    def _finish(self, session, text, turn, message, approval=None, intent=None):
        """Persist the turn transcript (with its provenance record) and, if the server proposed one, the updated
        session state (pending/confirmed intent, confirmed facts) in ONE consented client commit."""
        message = message or "No further action."
        provenance = self._provenance(turn, approval, intent)
        changes = [("history", "get_session", [session], "append_turn", {
            "session_id": session, "turn_id": turn["turn_id"], "user_text": text, "response_text": message,
            "status": turn["state"], "capability": (approval or {}).get("capability_id"),
            "attachments": [provenance] if provenance else []})]
        update = turn.get("session_update")
        if update is not None:
            changes.append(("sessions", "get_session", [session], "save_session", {"session_id": session}, update))
        try:
            self._commit_consented(session, changes)
        except Exception as exc:
            raise TurnError("HISTORY_PERSIST_FAILED", type(exc).__name__) from None
        return {**{k: v for k, v in turn.items() if k != "session_update"}, "message": message}
