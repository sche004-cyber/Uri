"""Live C5 assembled-loop validation against a REAL isolated server process.

Real: server process (single-instance launcher, signed identity), HTTP transport with
pinned-identity check before every credentialed call, DPAPI-protected client credentials,
client persistence with CAS journal, execution journal, approval, signed tickets, independent
read-back verification by a freshly constructed second persistence instance.
Injected (documented): executor crash after claim (fault injection), no Brain (deterministic
rules), no native harness (unqualified -> refused). Synthetic data only; port 18060+; never 8000.

Intent discovery continuation: ambiguous request -> RAR/S1 reference binding -> budgeted
clarification -> REAL server restart -> answer -> correction -> digest-bound confirmation ->
approval bound to the Confirmed Intent Contract -> verified execution -> session-first follow-up ->
ARN widening -> drifting planner rejected (in-process real app, labelled) -> executor failure
preserves intent -> uncertain intent execution never repeated after a second real restart.
Additional injected faults: client executor failure, intent executor crash, drifting planner.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uri_core.client_contracts import ReadQuery
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.client_runtime.persistence import ClientPersistence
from uri_core.client_runtime.transport import ClientTransport, TransportError
from uri_core.client_runtime.turn_runner import TurnRunner, TurnError
from uri_core.core.runtime_identity import RuntimeManifest, provision
from scripts.uri_server_launcher import launch, listener, owned_instance

NOBRAIN = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}
HARNESS = {"kind": "client_external_harness", "provider": "claude_code", "model": None}


def uid():
    return str(uuid.uuid4())


def memory_values(manifest, session):
    fresh = ClientPersistence(manifest)   # independent instance: reads from disk, not the writer's cache
    rows = fresh.snapshot(session, [ReadQuery(store="memory", method="list_all")]).reads[0].result
    return [r["fact"]["value"] for r in rows]


def main():
    root = Path(__file__).resolve().parents[1]
    base = root / "work/c1" / ("c5_live_" + uuid.uuid4().hex)
    port = next(p for p in range(18060, 18080) if listener(p) is None)
    server = RuntimeManifest(provision(root, base / "server", Path(sys.executable), port, "c2-paired-core"))
    principal = uid()
    granted = ClientManifest(provision_client(server.path, base / "granted", principal, ["remember_fact"]))
    ungranted = ClientManifest(provision_client(server.path, base / "ungranted", principal, []))
    started, steps, evidence = None, [], {}

    def step(name, ok, **detail):
        steps.append({"step": name, "ok": bool(ok), **detail})
        print(("PASS " if ok else "FAIL ") + name, detail if detail else "")
        if not ok:
            raise AssertionError(name)

    def runner_for(manifest):
        transport = ClientTransport(manifest)
        identity = transport.verify_server()          # signed identity verified against pinned key
        transport.session()
        def call(method, path, body):
            try:
                return 200, transport.request(method, path, body)
            except TransportError as exc:
                code = str(exc)
                return (int(code[5:]) if code.startswith("HTTP_") else 599), {"detail": code}
        return TurnRunner(manifest, ClientPersistence(manifest), call, manifest.data["server_public_key"],
                          identity["generation"]), transport, identity

    try:
        started = launch(server, "start")
        again = launch(server, "start")
        step("single-instance launcher: exact same server recognised", started["pid"] == again["pid"]
             and again["result"] == "ALREADY_RUNNING", pid=started["pid"], port=port)
        runner, transport, identity = runner_for(granted)
        step("pinned signed server identity verified before credentials", bool(identity["generation"]))
        session = uid()

        # 1. authorized reversible operation, verified, persisted
        seen = []
        final = runner.run("remember that the validation room is B-12", session, NOBRAIN, lambda req: seen.append(req) or True)
        step("authorized reversible write executed and settled VERIFIED", final["code"] == "SETTLED_VERIFIED",
             code=final["code"], approval_capability=seen[0]["capability_id"], reversible=seen[0]["reversible"])
        step("independent fresh-instance read-back finds the fact",
             "the validation room is B-12" in memory_values(granted, session))
        hist = ClientPersistence(granted).snapshot(session, [ReadQuery(store="history", method="get_session", args=[session])]).reads[0].result
        step("task state persisted in client-private history", len(hist) == 1 and "verified" in hist[0]["response_text"])

        # 2. follow-up uses existing session context
        follow = runner.run("what did I just ask you?", session, NOBRAIN, lambda req: False)
        step("follow-up saw prior session turn (server context from client snapshot)",
             follow.get("context", {}).get("prior_turns") == 1, reply_code=follow["code"])

        # 3. safe refusal
        refusal = runner.run("delete all my files", session, NOBRAIN, lambda req: (_ for _ in ()).throw(AssertionError("asked approval")))
        step("destructive request safely refused without approval prompt", refusal["code"].startswith("REFUSED_"), code=refusal["code"])

        # 4. declined approval changes nothing
        declined = runner.run("remember that this must not be stored", session, NOBRAIN, lambda req: False)
        step("declined approval: nothing stored", declined["code"] == "APPROVAL_DENIED"
             and "this must not be stored" not in memory_values(granted, session))

        # 5. blocked unauthorized action (client with no grant)
        r2, _, _ = runner_for(ungranted)
        blocked = r2.run("remember that unauthorized write", uid(), NOBRAIN, lambda req: (_ for _ in ()).throw(AssertionError("asked")))
        step("ungranted client blocked; nothing stored", blocked["code"] == "REFUSED_PERMISSION_DENIED"
             and memory_values(ungranted, blocked["session_id"]) == [])

        # 6. unavailable executor: unqualified harness is refused, never substituted
        unavailable = runner.run("remember that harness test", session, HARNESS, lambda req: (_ for _ in ()).throw(AssertionError("ran")))
        step("unqualified external harness refused with no fallback", unavailable["code"] == "ADAPTER_NOT_QUALIFIED"
             and "harness test" not in memory_values(granted, session))

        # 7. interrupted executor (fault injected): unsettled claim -> uncertain, never auto-redispatched
        original = TurnRunner._run_local
        def crash(self, *a, **k):
            raise KeyboardInterrupt("injected executor crash")
        TurnRunner._run_local = crash
        try:
            try:
                runner.run("remember that crash fact", session, NOBRAIN, lambda req: True)
                step("injected crash raised", False)
            except KeyboardInterrupt:
                pass
        finally:
            TurnRunner._run_local = original
        restarted, _, _ = runner_for(granted)
        states = [r["state"] for r in restarted.journal.recover()] if restarted.journal else []
        # Fresh runner has no journal until first execution; open the same durable journal explicitly.
        from uri_core.client_runtime.execution_journal import ExecutionJournal
        recovered = ExecutionJournal(granted.data["client_root"]).recover()
        step("after restart the claimed operation is execution_uncertain with dispatch=False",
             any(r["state"] == "execution_uncertain" and r["dispatch"] is False for r in recovered), records=len(recovered))
        step("no side effect from the interrupted run", "crash fact" not in memory_values(granted, session))

        # ================= Intent discovery scenarios (numbering = acceptance list) =================
        def restart_server():
            nonlocal started
            proc = listener(port)
            observed = owned_instance(server, proc)
            assert observed["pid"] == started["pid"]
            proc.terminate()
            proc.wait(15)
            started = launch(server, "start")
            return runner_for(granted)[0]

        def add_file(target, session_id, name):
            data = ("synthetic " + name).encode()
            target._commit_consented(session_id, [("files", "list_for_session", [session_id], "save", {
                "filename": name, "media_type": "application/pdf", "session_id": session_id,
                "content": {"encoding": "base64", "data": base64.b64encode(data).decode(),
                            "sha256": hashlib.sha256(data).hexdigest()}})])

        def session_state(session_id):
            return ClientPersistence(granted).snapshot(session_id, [ReadQuery(
                store="sessions", method="get_session", args=[session_id])]).reads[0].result

        # Memory is per-principal (not per-session): judge intent effects by NEW entries only.
        baseline = len(memory_values(granted, session))

        def new_memory(_session=None):
            return memory_values(granted, session)[baseline:]

        s2 = uid()
        add_file(runner, s2, "Budget report Q3.pdf")
        add_file(runner, s2, "Budget report Q4.pdf")
        q = runner.begin("remember that the budget report is due on Friday", s2, NOBRAIN)
        step("1-3 ambiguous request: missing referent detected, clarification issued, nothing executed",
             q["code"] == "INTENT_CLARIFICATION" and len(q["clarification"]["options"]) == 2
             and new_memory() == [], question=q["message"])
        runner = restart_server()
        step("15a real server process restarted while a question is pending", bool(started["pid"]), pid=started["pid"])
        a = runner.begin("the Q4 one", s2, NOBRAIN)
        step("4/15 answer after restart binds the referent; question not asked again",
             a["code"] == "INTENT_CONFIRMATION_REQUIRED" and a["intent"]["questions_asked"] == 1
             and a["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.pdf is due on Friday")
        c = runner.begin("actually it is due on Monday, not Friday", s2, NOBRAIN)
        args = c["confirmation"]["arguments"]["request_text"]
        step("12-13 correction replaces only the obsolete value",
             args == "remember that Budget report Q4.pdf is due on Monday"
             and c["intent"]["superseded"][0]["value"].endswith("Friday"), arguments=args)
        allowed = set("remember that budget report q4.pdf is due on monday friday the q4 one actually it not".split())
        step("14 no unsupported value introduced (every token from the user or the bound title)",
             set(args.lower().replace(",", "").split()) <= allowed)
        stale = runner.confirm(s2, NOBRAIN, a)
        step("false CONFIRMED prevented: superseded confirmation digest refused", stale["code"] == "INTENT_DECISION_STALE")
        approval = runner.confirm(s2, NOBRAIN, c)
        step("5-6 explicit confirmation; approval bound to the confirmed intent with identical arguments",
             approval["state"] == "approval_required"
             and approval["approval_request"]["intent_digest"] == c["confirmation"]["digest"]
             and approval["approval_request"]["arguments"]["inputs"] == c["confirmation"]["arguments"]
             and approval["approval_request"]["replanned"] is False)
        done = runner.decide("Confirm", s2, NOBRAIN, approval, True)
        step("7-8 reversible authorized operation executed and independently verified",
             done["code"] == "SETTLED_VERIFIED" and new_memory() == ["Budget report Q4.pdf is due on Monday"])
        baseline += 1
        st = session_state(s2)
        step("9 state persisted: intent completed, confirmed referent stored as a session fact",
             st["active_workflow"] is None
             and st["current_facts"]["reference.recent_subject"]["data"]["value"] == "Budget report Q4.pdf")
        f = runner.begin("remember that it was approved by Priya", s2, NOBRAIN)
        step("10/11/16 same-session follow-up: 'it' bound session-first, nothing asked",
             f["code"] == "INTENT_CONFIRMATION_REQUIRED" and f["intent"]["questions_asked"] == 0
             and f["confirmation"]["arguments"]["request_text"] == "remember that Budget report Q4.pdf was approved by Priya")
        runner.abandon(s2, NOBRAIN, f)
        s3 = uid()
        u = runner.begin("remember that the expense form is due tomorrow", s3, NOBRAIN)
        arn = session_state(s3)["active_workflow"]["arn"]
        step("17 unknown referent: ARN widened once (session -> graph), then asked; nothing invented",
             u["code"] == "INTENT_CLARIFICATION" and u["clarification"]["kind"] == "reference_free"
             and [x[0] for x in arn["checked"]] == ["session_context", "graph"] and new_memory() == [])

        # 18: conflicting downstream proposal needs an injected planner -> REAL app, in-process (labelled).
        # It gets its OWN provisioned server/client roots: two server instances must never share a
        # control root (C1 single-instance invariant).
        from fastapi.testclient import TestClient
        from uri_core.app.paired_server import create_app
        from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
        from uri_core.core.runtime_identity import RuntimeIdentity, dpapi
        side = RuntimeManifest(provision(root, base / "server18", Path(sys.executable), port + 1, "c2-paired-core"))
        side_client = ClientManifest(provision_client(side.path, base / "client18", uid(), ["remember_fact"]))
        runtime = RuntimeIdentity(side)
        app = create_app(runtime, composition={"policy": ReasoningSelectionPolicy(
            {("server_local_model", "uri-deterministic", None)})})
        with TestClient(app) as http:
            cred = json.loads(dpapi((Path(side_client.data["client_root"]) / "secure/uri-credentials.dpapi").read_bytes(), True))
            tok = http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
                            headers={"Authorization": "Bearer " + cred["principal_token"],
                                     "X-URI-Pairing": cred["pairing_token"]}).json()["token"]
            hdr = {"Authorization": "Bearer " + tok, "X-URI-Client": cred["client_id"]}

            def local_call(method, path, body):
                r = http.request(method, path, json=body, headers=hdr)
                return r.status_code, r.json()
            local = TurnRunner(side_client, ClientPersistence(side_client), local_call,
                               side_client.data["server_public_key"], runtime.generation)
            s4 = uid()
            add_file(local, s4, "Plan A.pdf")
            add_file(local, s4, "Plan B.pdf")
            local.begin("remember that the plan is approved", s4, NOBRAIN)
            conf = local.begin("Plan B", s4, NOBRAIN)
            app.state.client_service.coordinator.planner = lambda prepared, request, selection, intent: {
                "goal": "x", "mode": "single_action", "capability": "remember_fact", "clarification": None,
                "unsupported_reason": None, "requires_approval": False, "confidence": 0.9, "reason": "drift",
                "actions": [{"name": "remember", "inputs": {"request_text": "remember that Plan A.pdf is rejected"}}]}
            rep = local.confirm(s4, NOBRAIN, conf)
            req = rep["approval_request"]
            step("18 conflicting downstream proposal rejected and replanned from the confirmed intent (in-process real app)",
                 req["replanned"] is True and req["arguments"]["inputs"]["request_text"] == "remember that Plan B.pdf is approved",
                 conflicts=req["rejected_proposal"]["conflicts"])
            local.decide("Confirm", s4, NOBRAIN, rep, False)

        # 20: executor failure preserves the confirmed intent; an explicit retry executes once
        s5 = uid()
        add_file(runner, s5, "Travel memo.pdf")
        add_file(runner, s5, "Travel memo draft.pdf")
        runner.begin("remember that the travel memo is signed", s5, NOBRAIN)
        cf = runner.begin("1", s5, NOBRAIN)
        original = TurnRunner._run_local
        TurnRunner._run_local = lambda self, *a, **k: ("failed", [], "NOT_STARTED:NO_LOCAL_EXECUTOR")
        try:
            failed = runner.decide("Confirm", s5, NOBRAIN, runner.confirm(s5, NOBRAIN, cf), True)
        finally:
            TurnRunner._run_local = original
        kept = session_state(s5)["active_workflow"]
        step("20 unavailable executor: failed settle, nothing stored, confirmed intent preserved",
             failed["code"] == "SETTLED_FAILED" and kept["status"] == "CONFIRMED" and new_memory() == [])
        reminder = runner.begin("status?", s5, NOBRAIN)
        retried = runner.decide("Confirm", s5, NOBRAIN, runner.confirm(s5, NOBRAIN, reminder), True)
        step("20b explicit retry of the preserved intent executes exactly once",
             retried["code"] == "SETTLED_VERIFIED" and new_memory() == ["Travel memo.pdf is signed"])
        baseline += 1

        # 21: an uncertain intent execution is never repeated, even after a real restart
        s6 = uid()
        add_file(runner, s6, "Lease contract A.pdf")
        add_file(runner, s6, "Lease contract B.pdf")
        runner.begin("remember that the lease contract is renewed", s6, NOBRAIN)
        cu = runner.begin("2", s6, NOBRAIN)
        appr = runner.confirm(s6, NOBRAIN, cu)

        def crash2(self, *a, **k):
            raise KeyboardInterrupt("injected executor crash (intent)")
        TurnRunner._run_local = crash2
        try:
            try:
                runner.decide("Confirm", s6, NOBRAIN, appr, True)
            except KeyboardInterrupt:
                pass
        finally:
            TurnRunner._run_local = original
        runner = restart_server()
        again = runner.confirm(s6, NOBRAIN, cu)
        step("21 uncertain intent execution not repeated after restart (no new approval)",
             again["state"] == "reply" and again["code"] == "INTENT_EXECUTION_UNCERTAIN" and new_memory() == [])

        # ---- second-review additions (same real server process) ----
        # 22: a verified intent cannot be executed again by replaying older client state.
        s7 = uid()
        add_file(runner, s7, "Audit plan 2025.pdf")
        add_file(runner, s7, "Audit plan 2026.pdf")
        runner.begin("remember that the audit plan is signed", s7, NOBRAIN)
        await7 = runner.begin("the 2026 one", s7, NOBRAIN)
        before_state = session_state(s7)
        ok7 = runner.decide("Confirm", s7, NOBRAIN, runner.confirm(s7, NOBRAIN, await7), True)
        runner._commit_consented(s7, [("sessions", "get_session", [s7], "save_session", {"session_id": s7}, before_state)])
        replay7 = runner.confirm(s7, NOBRAIN, await7)
        step("22 verified intent replayed from older client state is refused (no second execution)",
             ok7["code"] == "SETTLED_VERIFIED" and replay7["state"] == "reply"
             and replay7["code"] in {"INTENT_ALREADY_EXECUTED", "INTENT_STATE_STALE"}
             and new_memory() == ["Audit plan 2026.pdf is signed"], code=replay7["code"])
        baseline += 1
        # 23: graph widening against the REAL client GraphStore: several plausible nodes -> asked, not guessed.
        s8 = uid()
        for name in ("Expense form 2025", "Expense form 2026"):
            runner._commit_consented(s8, [("graph", "list_nodes", [], "upsert_node",
                                           {"entity_type": "document", "canonical_name": name})])
        g = runner.begin("remember that the expense form is due on Friday", s8, NOBRAIN)
        labels = sorted(o["label"] for o in (g.get("clarification") or {}).get("options") or [])
        step("23 graph widening with two real graph nodes asks with both options; nothing executed",
             g["code"] == "INTENT_CLARIFICATION" and labels == ["Expense form 2025", "Expense form 2026"]
             and new_memory() == [], options=labels)
        runner.abandon(s8, NOBRAIN, g)
        # 24: a bound session file removed before confirmation makes the confirmation stale; nothing runs.
        s9 = uid()
        add_file(runner, s9, "Board memo March.pdf")
        add_file(runner, s9, "Board memo April.pdf")
        runner.begin("remember that the board memo is final", s9, NOBRAIN)
        await9 = runner.begin("the April one", s9, NOBRAIN)
        files9 = ClientPersistence(granted).snapshot(s9, [ReadQuery(store="files", method="list_for_session",
                                                                    args=[s9])]).reads[0].result
        april = next(f for f in files9 if "April" in f["filename"])
        runner._commit_consented(s9, [("files", "list_for_session", [s9], "delete", {"file_id": april["file_id"]})])
        stale9 = runner.confirm(s9, NOBRAIN, await9)
        step("24 confirmation of a referent removed after binding is stale; re-resolved, nothing executed",
             stale9["state"] == "reply" and "April" not in json.dumps(stale9.get("confirmation") or {})
             and new_memory() == [], code=stale9["code"])

        # ---- third-review additions (same real server process, third real restart) ----
        # 25: a "failed" receipt after dispatch (the write landed, the read-back "failed") is execution
        # uncertain; neither re-confirming nor a real restart obtains a second approval or execution.
        s10 = uid()
        add_file(runner, s10, "Grant report draft.pdf")
        add_file(runner, s10, "Grant report final.pdf")
        runner.begin("remember that the grant report is submitted", s10, NOBRAIN)
        await10 = runner.begin("the final one", s10, NOBRAIN)

        def wrote_then_failed(self, *a, **k):
            original(self, *a, **k)
            return "failed", [], "READBACK_MISMATCH"
        TurnRunner._run_local = wrote_then_failed
        try:
            f10 = runner.decide("Confirm", s10, NOBRAIN, runner.confirm(s10, NOBRAIN, await10), True)
        finally:
            TurnRunner._run_local = original
        landed = new_memory()
        runner = restart_server()
        again10 = runner.confirm(s10, NOBRAIN, await10)
        step("25 failed receipt after dispatch settles uncertain; not re-run after a real restart",
             f10["code"] == "SETTLED_EXECUTION_UNCERTAIN" and again10["code"] in {"INTENT_EXECUTION_UNCERTAIN",
             "INTENT_DECISION_STALE"} and landed == ["Grant report final.pdf is submitted"] and new_memory() == landed,
             code=again10["code"])
        baseline += 1
        # 26: plain text never re-offers the possibly-executed request; the session is not locked.
        aside = runner.begin("hello", s10, NOBRAIN)
        after = runner.begin("hello", s10, NOBRAIN)
        step("26 uncertain intent set aside on plain text (no re-confirmation offer); session continues",
             aside["code"] == "INTENT_EXECUTION_UNCERTAIN" and "confirmation" not in aside
             and session_state(s10)["active_workflow"] is None and after["code"] == "CONVERSATION"
             and new_memory() == [])

        evidence = {"schema_version": "uri.client.v1", "port": port, "server_pid": started["pid"],
                    "brain": "none (deterministic rules, explicit user-selected source)", "native_harness": "not exercised (unqualified, refused)",
                    "injected_faults": ["executor crash after claim", "client executor failure", "intent executor crash after claim",
                                        "drifting planner (in-process real app)", "write landed then failed read-back"],
                    "server_restarts": 3, "second_review_steps": ["22", "23", "24"], "third_review_steps": ["25", "26"], "steps": steps, "production_cutover": False}
    finally:
        if started is not None:
            proc = listener(port)
            observed = owned_instance(server, proc)
            assert observed["pid"] == started["pid"] and observed["generation"] == started["generation"]
            proc.terminate()
            proc.wait(15)
            assert listener(port) is None
    evidence["test_owned_server_cleaned"] = True
    out = base / "server/control/c5-live-evidence.json"
    out.write_text(json.dumps(evidence, indent=2))
    (root / "work/c1/c5-live-locator.json").write_text(json.dumps({"evidence": str(out)}))
    print(json.dumps({"result": "ALL_STEPS_PASSED", "evidence": str(out), "steps": len(steps)}))


if __name__ == "__main__":
    main()
