"""CLI: `python -m uri_v1.office --root <folder> [--attach <file>]...` (M39 §4.2).

An isolated demonstrator REPL, never wired into `/ask`, the UI, S6 or M31.
Commands are sentences; `status`, `pause`, `resume <task>` are recognized
verbatim. No model call anywhere in this module.
"""
from __future__ import annotations

import argparse
import sys
import uuid

from .bootstrap import build_session
from .flow import OfficeSession, StepResult
from .request import parse
from .view import render, render_status


def _turn():
    return uuid.uuid4().hex, uuid.uuid4().hex


def run_repl(session: OfficeSession, user_id: str, *, in_stream=sys.stdin, out=sys.stdout) -> None:
    session_id = uuid.uuid4().hex
    active_task = None
    pending_writeback: dict = {}  # task_id -> relpaths URI offered for approval (M39-7)
    pending_round = None          # (task_id, round_id) of the question URI last asked (repair round 3, R2-1)
    out.write("URI Office demonstrator. Type a request, or 'status' / 'pause' / 'resume <task>'.\n")
    for line in in_stream:
        raw = line.strip()
        if not raw:
            continue
        if raw == "status":
            out.write(render_status(session.status()) + "\n")
            continue
        if raw.startswith("resume "):
            task_id = raw.split(None, 1)[1].strip()
            turn_id, trace_id = _turn()
            step = session.resume(task_id, raw, session_id=session_id, turn_id=turn_id, trace_id=trace_id)
            active_task = step.task_id
            if step.kind == "AWAITING_APPROVAL":
                pending_writeback[step.task_id] = step.relpaths
            elif step.task_id is not None:
                pending_writeback.pop(step.task_id, None)
            out.write(render(step) + "\n")
            continue
        if raw == "pause" and active_task:
            run_id = session._run.get(active_task)
            if run_id is None:
                out.write("[ERROR]\nNo pending run to pause.\n")
                continue
            turn_id, trace_id = _turn()
            step = session.pause(active_task, raw, run_id=run_id, session_id=session_id, turn_id=turn_id, trace_id=trace_id)
            out.write(render(step) + "\n")
            continue
        turn_id, trace_id = _turn()
        if pending_round and not parse(raw).ok:
            # Repair round 3 (R2-1): a clarifying question (a per-file
            # question, or a Memory round) is answered by the next line,
            # unless that line is itself a new supported request.
            step = session.answer(pending_round[0], raw, session_id=session_id, turn_id=turn_id,
                                  trace_id=trace_id, round_id=pending_round[1])
        elif active_task and session._escalation.get(active_task) is not None:
            step = session.confirm_escalation(active_task, raw, session_id=session_id, turn_id=turn_id, trace_id=trace_id)
        elif active_task and active_task in session._run:
            # M39-7: approve_writeback needs the exact relpaths URI itself
            # offered (`_offer_writeback`'s AWAITING_APPROVAL result) -- it no
            # longer guesses "all modified files" on the caller's behalf, so
            # the REPL must remember and pass them, or every approval used to
            # refuse with WRITEBACK_TARGETS_REQUIRED.
            relpaths = pending_writeback.get(active_task, ())
            step = session.approve_writeback(active_task, raw, relpaths=relpaths,
                                             session_id=session_id, turn_id=turn_id, trace_id=trace_id)
        else:
            parsed = parse(raw)
            if not parsed.ok:
                out.write(render(StepResult("UNSUPPORTED", reason=parsed.reason)) + "\n")
                continue
            step = session.start(raw, session_id=session_id, turn_id=turn_id, trace_id=trace_id, parsed=parsed)
            active_task = step.task_id
        if step.kind == "AWAITING_APPROVAL":
            pending_writeback[step.task_id] = step.relpaths
        elif step.task_id is not None:
            pending_writeback.pop(step.task_id, None)
        pending_round = None
        if step.kind == "CLARIFY":
            nxt = next((rb for rb in step.roles.values() if rb.state != "CONFIRMED" and rb.contract_id), None)
            if nxt is not None:
                pending_round = (step.task_id, nxt.contract_id)
        out.write(render(step) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m uri_v1.office")
    ap.add_argument("--root", required=True, help="the one folder this run is authorized to read/write in")
    ap.add_argument("--data-dir", default=None, help="private application data directory (default: <root>/.uri-office)")
    ap.add_argument("--user-id", default=None)
    args = ap.parse_args(argv)
    user_id = args.user_id or str(uuid.uuid4())
    data_dir = args.data_dir or (args.root.rstrip("/\\") + "/.uri-office")
    session = build_session(user_id, data_dir, authorized_root=args.root)
    run_repl(session, user_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
