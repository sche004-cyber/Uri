"""Plain-text rendering of a `flow.StepResult` (M39 §4.2 view.py).

`VERIFIED` here always means "the acceptance items URI checked passed", never
that the change is semantically correct (plan §9 risk 2) -- every VERIFIED
render says so explicitly.
"""
from __future__ import annotations

_HARNESS_NAMES = {"CLAUDE_CODE": "Claude Code", "CODEX_CLI": "Codex CLI"}
_ORIGINAL_MODIFIED_FLAGS = {"ORIGINAL_MODIFIED_DURING_RUN", "ORIGINAL_MODIFIED_DURING_VERIFICATION"}
_VERIFIED_CAVEAT = "(VERIFIED means the acceptance items URI checked passed -- not that the change is semantically correct.)"


def render(step) -> str:
    kind = step.kind
    lines = [f"[{kind}]"]
    if kind == "UNSUPPORTED":
        lines.append(f"URI does not recognize this as a supported request ({step.reason}).")
    elif kind == "CLARIFY":
        for role, rb in step.roles.items():
            if rb.state == "CONFIRMED":
                lines.append(f"- {role}: bound.")
            elif getattr(rb, "ask", False):
                kind = "script (.py)" if role == "script" else "workbook (.xlsx/.xlsm)"
                why = "" if rb.reason == "NON_AFFIRMATIVE_CONTEXT" else f" ({rb.reason})"
                lines.append(f"- {role}: which file is the {kind}? Reply with just its file name{why}, or \"cancel\" to stop. "
                             f"(round {step.task_id}/{rb.contract_id})")
            elif rb.contract_id:
                why = f"; {rb.reason}" if rb.reason else ""
                lines.append(f"- {role}: needs clarification (round {step.task_id}/{rb.contract_id}{why}). "
                             "Reply to choose, or \"cancel\" to stop.")
            else:
                lines.append(f"- {role}: could not be resolved ({rb.reason}).")
    elif kind == "CANCELLED":
        lines.append("Task cancelled. URI wrote nothing back to your files.")
    elif kind == "CLARIFY_MEMORY":
        lines.append(f"URI needs to re-check this task before continuing ({step.reason}).")
    elif kind == "ESCALATION_PROPOSAL":
        esc = step.escalation
        lines.append("URI could not complete this locally. Route: harness escalation.")
        for u in esc.unresolved:
            lines.append(f"- unresolved: {u}")
        roles = ", ".join(sorted(i.role for i in esc.inputs))
        harness = getattr(step, "harness", None)
        if harness:
            # F3 (independent audit 736464a): escalation sends file contents
            # to an external model provider over the network (plan §4.4 rule
            # 2); the consent screen must say so and name the harness.
            name = _HARNESS_NAMES.get(harness, harness)
            lines.append(f"Harness: {name}. The contents of these files will be sent to {name}, "
                         f"which passes them over the network to its external model provider: {roles}")
        else:
            lines.append(f"No harness is configured, so approving cannot run anything. Files the escalation would send: {roles}")
        lines.append("Posture: restrictive default for the harness's own tools (no network tools, no package install, "
                     "no elevation). This does not stop the file contents above from reaching the provider.")
        for w in step.warnings:
            lines.append(f"Note: {w}")
        lines.append('Reply "yes" / "approve" to run the harness, or say why not to decline.')
    elif kind == "ESCALATION_DECLINED":
        lines.append("Harness escalation declined. The task stays open with URI's local findings.")
    elif kind == "HARNESS_UNAVAILABLE":
        lines.append("The configured harness is not installed or not reachable. Nothing was started.")
    elif kind == "HARNESS_FAILED":
        lines.append(f"The harness's claim was checked and rejected (status: {step.verification_status}).")
        flags = tuple(step.safety_flags or ())
        if flags:
            lines.append(f"Safety flags: {', '.join(flags)}.")
        # N3 (independent audit 736464a): "Nothing was written" is only true
        # when no flag says an original was touched. Without an OS sandbox the
        # harness itself can write an original; URI detects that but cannot
        # undo it, so the reply must say so plainly.
        if set(flags) & _ORIGINAL_MODIFIED_FLAGS:
            who = _HARNESS_NAMES.get(getattr(step, "harness", None) or "", "the harness")
            changed = tuple(getattr(step, "originals_changed", ()) or ())
            what = ", ".join(changed) if changed else "one or more of your original files"
            when = ("the harness run" if "ORIGINAL_MODIFIED_DURING_RUN" in flags
                    else "verification of the harness's output (its code ran and changed them)")
            lines.append(f"Warning: your original file(s) were changed during {when}, not by URI's write-back "
                         f"({who}): {what}. URI did not undo this; check the file(s) before relying on them.")
            lines.append("URI wrote nothing back. The task stays open and is not complete.")
        elif flags:
            lines.append("URI wrote nothing back to your files. The task stays open and is not complete.")
        else:
            # R5-1 (re-audit 0d690ea): no flag proves only that the originals
            # kept their hashes, not that the harness wrote nothing anywhere
            # (no OS sandbox), so URI states only what it did itself.
            lines.append("URI wrote nothing back to your files. The task stays open and is not complete.")
    elif kind == "NOTHING_TO_WRITE":
        lines.append("The run verified but changed nothing that needs writing back. Nothing to apply.")
    elif kind == "AWAITING_APPROVAL":
        lines.append(f"Verified. {_VERIFIED_CAVEAT}")
        lines.append("URI will write back exactly: " + ", ".join(step.relpaths))
        for w in step.warnings:
            lines.append(f"Note: {w}")
        lines.append('Reply "apply" / "approve" to write these files back, or "pause" to decide later.')
    elif kind == "WRITEBACK_REFUSED":
        if step.written:
            lines.append(f"Write-back refused: {step.reason}.")
            lines.append("Some files were already written to disk before the refusal -- this is not \"nothing happened\":")
            for w in step.written:
                lines.append(f"- {w['relpath']}: {w['before_sha256'][:12]} -> {w['after_sha256'][:12]}")
            if step.partial_record == "FAILED":
                lines.append("The task is recorded as FAILED in Memory, with the files above.")
            elif step.partial_record == "NOTED":
                lines.append("The partial write is noted on the task in Memory.")
            elif step.partial_record:
                lines.append(f"Memory could not record the partial write ({step.partial_record}).")
        else:
            lines.append(f"Write-back refused: {step.reason}. URI wrote nothing back to your files.")
    elif kind == "COMPLETED":
        lines.append("Written and task complete.")
        for w in step.written:
            lines.append(f"- {w['relpath']}: {w['before_sha256'][:12]} -> {w['after_sha256'][:12]}")
    elif kind == "PAUSED":
        lines.append(f"Paused. Resume later with the same task ({step.task_id}); run {step.run_id} is pending approval.")
    elif kind == "ERROR":
        lines.append(f"URI could not continue: {step.reason}.")
    else:
        lines.append(f"(no renderer for {kind})")
    return "\n".join(lines)


def render_status(rows) -> str:
    if not rows:
        return "No open or paused tasks."
    lines = []
    for r in rows:
        refs = ", ".join(x["source_id"][:12] for x in r["references"]) or "(no references yet)"
        lines.append(f"- {r['task_id']}: {r['status']} -- {refs}"
                     + (f" -- next: {r['next_step']}" if r["next_step"] else ""))
    return "\n".join(lines)
