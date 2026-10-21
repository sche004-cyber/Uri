"""Command line for the Milestone Manager.

    python -m scripts.dev_workflow.milestones <command> [options]

Ledger home: --home or URI_MM_HOME. Writer identity: --actor or URI_MM_ACTOR (required for writes), session:
--session or URI_MM_SESSION / CLAUDE_CODE_SESSION_ID. Exit codes: 0 ok, 1 refused (validation), 2 usage or store
error, 3 verify found problems.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from scripts.dev_workflow.milestones import importers, views
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore, StoreError


def _p(parser, *names, **kw):
    parser.add_argument(*names, **kw)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m scripts.dev_workflow.milestones",
                                 description="URI Milestone Manager (development project registry)")
    ap.add_argument("--home", default=os.environ.get("URI_MM_HOME"))
    ap.add_argument("--actor", default=os.environ.get("URI_MM_ACTOR"))
    ap.add_argument("--session", default=os.environ.get("URI_MM_SESSION") or os.environ.get("CLAUDE_CODE_SESSION_ID"))
    ap.add_argument("--no-emoji", action="store_true", help="plain text indicators only")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init-host", help="register this machine on a cloned ledger with a new host id")
    _p(s, "--host-id", required=True)
    s = sub.add_parser("reanchor", help="explicitly re-base this machine's anchors (recorded)")
    _p(s, "--reason", required=True)
    _p(s, "--acknowledge-loss", action="store_true", help="record a detected loss of events explicitly")
    s = sub.add_parser("init", help="create a ledger home")
    _p(s, "--host-id")
    _p(s, "--autocommit", action="store_true", help="git-commit every append when the home is a git work tree")

    s = sub.add_parser("milestone-add")
    _p(s, "id"); _p(s, "--title", required=True); _p(s, "--objective"); _p(s, "--priority")
    _p(s, "--phase", default="RESEARCH"); _p(s, "--depends-on", nargs="*", default=[])
    _p(s, "--acceptance-ref"); _p(s, "--worktree"); _p(s, "--branch"); _p(s, "--base-commit")
    _p(s, "--next-action"); _p(s, "--status", default="PLANNED")

    s = sub.add_parser("milestone-update")
    _p(s, "id"); _p(s, "--expect-version", type=int)
    for f in ("title", "objective", "priority", "phase", "next-action", "worktree", "branch", "base-commit",
              "candidate-commit", "acceptance-ref"):
        _p(s, "--" + f)

    s = sub.add_parser("status-set", help="set milestone status (positive states are evidence-guarded)")
    _p(s, "id"); _p(s, "status"); _p(s, "--reason", required=True); _p(s, "--expect-version", type=int)

    s = sub.add_parser("dep-add"); _p(s, "id"); _p(s, "on")
    s = sub.add_parser("dep-remove"); _p(s, "id"); _p(s, "on"); _p(s, "--reason", required=True)
    s = sub.add_parser("assign"); _p(s, "id"); _p(s, "--hours", type=float, default=4.0); _p(s, "--worktree")
    _p(s, "--takeover", action="store_true")
    s = sub.add_parser("release"); _p(s, "id"); _p(s, "--reason", required=True)
    s = sub.add_parser("implementer-add"); _p(s, "id"); _p(s, "agent")

    s = sub.add_parser("blocker-add"); _p(s, "subject"); _p(s, "--kind", required=True)
    _p(s, "--reason", required=True); _p(s, "--needs", required=True)
    s = sub.add_parser("blocker-resolve"); _p(s, "id"); _p(s, "--resolution", required=True)

    s = sub.add_parser("evidence-add"); _p(s, "subject"); _p(s, "--kind", required=True); _p(s, "--ref", required=True)
    _p(s, "--result", required=True, help="result class, e.g. COMPLETED_WITH_RESULT")
    _p(s, "--summary", required=True); _p(s, "--commit"); _p(s, "--file", help="hash this file (default: --ref)")
    _p(s, "--sha256"); _p(s, "--no-hash", action="store_true")

    s = sub.add_parser("review-add"); _p(s, "subject"); _p(s, "--commit", required=True)
    _p(s, "--reviewer-kind", required=True); _p(s, "--reviewer-id", required=True)
    _p(s, "--assurance", required=True); _p(s, "--verdict", required=True)
    _p(s, "--blocking-open", type=int, required=True); _p(s, "--findings-total", type=int, required=True)
    _p(s, "--result", required=True); _p(s, "--summary", required=True); _p(s, "--evidence", nargs="*", default=[])

    s = sub.add_parser("approval-request"); _p(s, "subject"); _p(s, "--kind", required=True)
    _p(s, "--question", required=True); _p(s, "--commit", help="commit the approval is for (INTEGRATION: candidate)")
    s = sub.add_parser("approval-resolve"); _p(s, "id"); _p(s, "outcome")
    _p(s, "--owner-words", help="the owner's own words, verbatim"); _p(s, "--source", help="where the owner said it")
    _p(s, "--reason")

    s = sub.add_parser("decision-add"); _p(s, "--id"); _p(s, "--title", required=True)
    _p(s, "--decision", required=True); _p(s, "--date", required=True); _p(s, "--evidence-class", required=True)
    _p(s, "--source", required=True); _p(s, "--proposal"); _p(s, "--reasoning"); _p(s, "--alternatives-rejected")
    _p(s, "--related", nargs="*", default=[]); _p(s, "--consequences"); _p(s, "--approval-ref")
    _p(s, "--supersedes"); _p(s, "--partial", action="store_true"); _p(s, "--note")
    s = sub.add_parser("decision-supersede"); _p(s, "id"); _p(s, "--by", required=True)
    _p(s, "--partial", action="store_true"); _p(s, "--note")
    s = sub.add_parser("decision-correct"); _p(s, "id"); _p(s, "--correction", required=True)
    _p(s, "--evidence-class", required=True); _p(s, "--source", required=True)

    s = sub.add_parser("handoff"); _p(s, "subject"); _p(s, "--summary", required=True); _p(s, "--done")
    _p(s, "--next"); _p(s, "--files", nargs="*", default=[]); _p(s, "--commit")

    s = sub.add_parser("link-lifecycle"); _p(s, "subject"); _p(s, "state_dir"); _p(s, "--config")
    s = sub.add_parser("sync-lifecycle"); _p(s, "subject"); _p(s, "state_dir")
    s = sub.add_parser("integration-record"); _p(s, "subject"); _p(s, "--target-ref", required=True)
    _p(s, "--target-commit", required=True); _p(s, "--repo")
    s = sub.add_parser("resolve-conflict"); _p(s, "entity"); _p(s, "--note", required=True)

    s = sub.add_parser("import-decisions"); _p(s, "path"); _p(s, "--commit")
    s = sub.add_parser("import-register"); _p(s, "path"); _p(s, "--commit")

    s = sub.add_parser("status"); _p(s, "--milestone"); _p(s, "--json", action="store_true")
    _p(s, "--a2ui", action="store_true", help="emit an A2UI surface description (JSON)")
    _p(s, "--no-tasks", action="store_true", help="do not query the Lifecycle V3.1 task ledger")
    s = sub.add_parser("show"); _p(s, "id")
    s = sub.add_parser("resume"); _p(s, "id"); _p(s, "--max-chars", type=int, default=6000)
    _p(s, "--no-tasks", action="store_true")
    s = sub.add_parser("ready")
    s = sub.add_parser("log"); _p(s, "--entity"); _p(s, "--limit", type=int, default=30)
    sub.add_parser("verify")
    sub.add_parser("verify-evidence")
    s = sub.add_parser("recover"); _p(s, "--reason", default="torn tail / incomplete batch after a crash")
    sub.add_parser("rebuild")
    return ap


def _show(p, ident):
    for key in ("milestones", "decisions", "approvals", "evidence", "reviews", "blockers", "handoffs", "records"):
        if ident in p[key]:
            return {"type": key[:-1], "version": p["versions"].get(ident, 0), **p[key][ident]}
    raise ValidationError("NOT_FOUND", f"{ident} not found")


def a2ui_surface(status: dict) -> dict:
    """A2UI-shaped description (Card/Badge tones from uri_a2ui/catalog.py); built as plain data, no import."""
    children = []
    for m in status["milestones"]:
        ind = m["indicator"]
        children.append({"type": "Card", "tone": {"success": "neutral"}.get(ind["tone"], ind["tone"]),
                         "children": [{"type": "Badge", "tone": ind["tone"], "text": ind["word"]},
                                      {"type": "Text", "text": f"{m['id']} - {m['title']}"},
                                      {"type": "Text", "text": f"phase {m['phase']}; "
                                                               f"{ind['issue'] or 'no open issue'}"},
                                      {"type": "Text", "text": f"next: {ind['next_action'] or '-'}"}]})
    return {"surface_id": "dev.milestones", "schema": status["schema"], "root": {"type": "Column",
                                                                                  "children": children}}


def run(argv=None, out=None) -> int:
    out = out or sys.stdout
    args = build_parser().parse_args(argv)
    emoji = not args.no_emoji

    def emit(obj):
        if isinstance(obj, str):
            out.write(obj + "\n")
        else:
            out.write(json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False, default=str) + "\n")

    try:
        if not args.home:
            raise StoreError("NO_HOME", "pass --home or set URI_MM_HOME")
        if args.cmd == "init-host":
            st = EventStore.init_host(args.home, args.host_id)
            emit({"registered": st.host, "home": str(st.home)})
            return 0
        if args.cmd == "reanchor":
            if not args.actor:
                raise ValidationError("NO_ACTOR", "--actor is required")
            emit(EventStore(args.home).reanchor(args.actor, args.reason, args.session, args.acknowledge_loss))
            return 0
        if args.cmd == "init":
            st = EventStore.init(args.home, args.host_id, args.autocommit)
            emit({"initialised": str(st.home), "host_id": st.host, "autocommit": st.config["autocommit"]})
            return 0
        mgr = Manager(args.home, args.actor, args.session)
        integrity_rc = lambda p: 3 if p.get("integrity_errors") else 0  # noqa: E731
        tasks = (lambda ref: mgr.task_summaries(ref)) if not getattr(args, "no_tasks", False) else None
        c = args.cmd
        if c == "milestone-add":
            r = mgr.create_milestone(args.id, args.title, args.objective, args.priority, args.phase, args.depends_on,
                                     args.acceptance_ref, args.worktree, args.branch, args.base_commit,
                                     args.next_action, args.status)
        elif c == "milestone-update":
            fields = {k.replace("-", "_"): getattr(args, k.replace("-", "_")) for k in (
                "title", "objective", "priority", "phase", "next-action", "worktree", "branch", "base-commit",
                "candidate-commit", "acceptance-ref") if getattr(args, k.replace("-", "_")) is not None}
            r = mgr.update_milestone(args.id, args.expect_version, **fields)
        elif c == "status-set":
            r = mgr.set_status(args.id, args.status, args.reason, args.expect_version)
        elif c == "dep-add":
            r = mgr.add_dependency(args.id, args.on)
        elif c == "dep-remove":
            r = mgr.remove_dependency(args.id, args.on, args.reason)
        elif c == "assign":
            r = mgr.assign(args.id, args.hours, args.worktree, args.takeover)
        elif c == "release":
            r = mgr.release(args.id, args.reason)
        elif c == "implementer-add":
            r = mgr.record_implementer(args.id, args.agent)
        elif c == "blocker-add":
            r = mgr.add_blocker(args.subject, args.kind, args.reason, args.needs)
        elif c == "blocker-resolve":
            r = mgr.resolve_blocker(args.id, args.resolution)
        elif c == "evidence-add":
            f = None if args.no_hash or args.sha256 else (args.file or (args.ref if os.path.isfile(args.ref) else None))
            r = {"id": mgr.add_evidence(args.subject, args.kind, args.ref, args.result, args.summary, args.commit,
                                        f, args.sha256)}
        elif c == "review-add":
            r = mgr.record_review(args.subject, args.commit, args.reviewer_kind, args.reviewer_id, args.assurance,
                                  args.verdict, args.blocking_open, args.findings_total, args.result, args.summary,
                                  args.evidence)
        elif c == "approval-request":
            r = mgr.request_approval(args.subject, args.kind, args.question, commit=args.commit)
        elif c == "approval-resolve":
            r = mgr.resolve_approval(args.id, args.outcome, args.owner_words, args.source, args.reason)
        elif c == "decision-add":
            r = mgr.record_decision(args.title, args.decision, args.date, args.evidence_class, args.source, args.id,
                                    args.proposal, args.reasoning, args.alternatives_rejected, args.related,
                                    args.consequences, args.approval_ref, args.supersedes, args.partial, args.note)
        elif c == "decision-supersede":
            r = mgr.supersede_decision(args.id, args.by, args.partial, args.note)
        elif c == "decision-correct":
            r = mgr.correct_decision(args.id, args.correction, args.evidence_class, args.source)
        elif c == "handoff":
            r = mgr.record_handoff(args.subject, args.summary, args.done, args.next, args.files, args.commit)
        elif c == "link-lifecycle":
            r = mgr.link_lifecycle(args.subject, args.state_dir, args.config)
        elif c == "sync-lifecycle":
            r = mgr.sync_lifecycle(args.subject, args.state_dir)
        elif c == "integration-record":
            r = mgr.record_integration(args.subject, args.target_ref, args.target_commit, args.repo)
        elif c == "resolve-conflict":
            r = mgr.resolve_conflict(args.entity, args.note)
        elif c == "import-decisions":
            r = importers.import_decisions(mgr, args.path, args.commit)
            if r["collisions"]:
                emit({**r, "refused": "ID_COLLISION", "message": "rows whose id is already used by an unrelated "
                                                                  "decision were not imported"})
                return 1
        elif c == "import-register":
            r = importers.import_register(mgr, args.path, args.commit)
        elif c == "status":
            p = mgr.projection()
            if args.json or args.a2ui:
                st = views.status_json(p, tasks)
                emit(a2ui_surface(st) if args.a2ui else st)
            else:
                emit("\n".join(views.status_lines(p, emoji, tasks, args.milestone)) or "(no milestones)")
            return integrity_rc(p)
        elif c == "show":
            p = mgr.projection()
            emit({**_show(p, args.id), **({"ledger_integrity_errors": p["integrity_errors"]}
                                          if p.get("integrity_errors") else {})})
            return integrity_rc(p)
        elif c == "resume":
            p = mgr.projection()
            emit(views.resume_brief(p, args.id, tasks(args.id) if tasks else None, args.max_chars, emoji))
            return integrity_rc(p)
        elif c == "ready":
            p = mgr.projection()
            emit(views.ready(p, args.actor) if not p.get("integrity_errors") else
                 {"error": "INTEGRITY", "message": "ledger fails verification; no milestone is ready",
                  "integrity_errors": p["integrity_errors"]})
            return integrity_rc(p)
        elif c == "log":
            evs = [e for s in mgr.store.read_all() for e in s.valid_events]
            evs.sort(key=lambda e: (e["ts"], e["seg"], e["seq"]))
            if args.entity:
                evs = [e for e in evs if args.entity in json.dumps(e["data"]) or args.entity in e.get("base", {})]
            out_rows = [{k: e[k] for k in ("seg", "seq", "ts", "actor", "kind", "data")} for e in evs[-args.limit:]]
            p = mgr.projection()
            emit({"events": out_rows, "integrity_errors": p["integrity_errors"]} if p.get("integrity_errors")
                 else out_rows)
            return integrity_rc(p)
        elif c == "verify":
            rep = mgr.store.verify()
            p = mgr.projection()
            rep["conflicts_open"] = len(views.open_conflicts(p))
            rep["warnings"] = p.get("integrity_warnings", [])
            emit(rep)
            return 0 if rep["ok"] else 3
        elif c == "verify-evidence":
            probs = mgr.check_evidence()
            emit({"ok": not probs, "problems": probs})
            return 0 if not probs else 3
        elif c == "recover":
            if not args.actor:
                raise ValidationError("NO_ACTOR", "--actor is required")
            res = mgr.store.recover(args.actor, args.session)
            ab = mgr.abandon_batches(args.reason)
            res["abandoned_batches"] = [b for e in ab for b in e["data"]["batches"]]
            emit(res)
            return 0
        elif c == "rebuild":
            p = mgr.projection()
            emit({"events": p["events"], "integrity_errors": p.get("integrity_errors", [])})
            return integrity_rc(p)
        else:  # pragma: no cover - argparse restricts choices
            raise ValidationError("USAGE", c)
        if isinstance(r, list):
            r = {"written": [{"kind": e["kind"], "seq": e["seq"], "hash": e["hash"],
                              "id": e["data"].get("id") or e["data"].get("subject")} for e in r]}
            if mgr.last_autocommit and mgr.last_autocommit.get("error"):
                r["autocommit_error"] = mgr.last_autocommit["error"]
            if mgr.last_warnings:
                r["warnings"] = mgr.last_warnings
        emit(r)
        return 0
    except ValidationError as e:
        emit({"refused": e.code, "message": str(e)})
        return 1
    except StoreError as e:
        emit({"error": e.code, "message": str(e)})
        return 2
    except OSError as e:  # missing or unreadable file named on the command line (R1-12)
        emit({"error": "IO", "message": f"{e.__class__.__name__}: {e}"})
        return 2
    except (ValueError, KeyError, TypeError, AttributeError) as e:  # malformed input file
        emit({"error": "INPUT", "message": f"{e.__class__.__name__}: {e}"})
        return 2


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(run())


if __name__ == "__main__":
    main()
