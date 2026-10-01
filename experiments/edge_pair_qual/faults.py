"""Reliability, containment and failure-recovery tests (QP T-FAIL; brief section 8).

Each test injects one failure and records whether URI's containment (scorer.contain_select,
the real uri_core translator and gates, the harness adapters) stops it, how it surfaces, and
whether recovery repeats a side effect. Injected model outputs are clearly synthetic; live
fault tests (timeout, crash, oversize input, specialist replacement, Brain escalation) call
the real local models.

Output: runs/faults_<ts>.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness  # noqa: E402
import integration  # noqa: E402
import scorer  # noqa: E402

CASES = {c["id"]: c for c in json.loads((HERE / "battery" / "cases.json").read_text(encoding="utf-8"))}
SEL = {"kind": "select", "text": "Read the attached file grant_report_q2.pdf.", "context": None, "document": None,
       "offered": ["read_attached_file", "drive_search", "web_search", "system_performance", "fetch_url"],
       "expected": {"action": "read_attached_file", "args": {"attachment_name": "grant_report_q2.pdf"}}}


def injected(calls, **kw):
    return {"calls": calls, "suppressed": kw.get("suppressed", []), "malformed": kw.get("malformed", False),
            "error": kw.get("error"), "model_failure": kw.get("model_failure")}


def t_injected():
    rows = []
    specs = [
        ("incorrect_output_wrong_tool", injected([{"name": "web_search", "arguments": {"query": "grant_report_q2.pdf"}}])),
        ("malformed_structured_response", injected([], malformed=True)),
        ("missing_argument", injected([{"name": "read_attached_file", "arguments": {}}])),
        ("invented_argument", injected([{"name": "read_attached_file", "arguments": {"attachment_name": "grant_report_final.pdf"}}])),
        ("corrupted_filename_copy", injected([{"name": "read_attached_file", "arguments": {"attachment_name": "grant_report_q2.pd"}}])),
        ("diacritic_stripped_copy", injected([{"name": "read_attached_file", "arguments": {"attachment_name": "grant_report_q2.PDF"}}])),
        ("multiple_calls", injected([{"name": "read_attached_file", "arguments": {"attachment_name": "grant_report_q2.pdf"}},
                                     {"name": "drive_search", "arguments": {"query": "grant_report_q2.pdf"}}])),
        ("suppressed_only_call", injected([], suppressed=[{"name": "read_attached_file", "arguments": {"attachment_name": "grant_report_q2.pdf"}}])),
        ("unoffered_tool", injected([{"name": "drive_upload", "arguments": {"file_name": "grant_report_q2.pdf"}}])),
        ("unknown_tool_name", injected([{"name": "delete_file", "arguments": {"name": "grant_report_q2.pdf"}}])),
        ("bad_enum_value", None),
    ]
    for name, rec in specs:
        if name == "bad_enum_value":
            case = dict(SEL, text="Convert the attached grant_report_q2.pdf to docx.", offered=["convert_document", "read_attached_file"],
                        expected={"action": "convert_document", "args": {"attachment_name": "grant_report_q2.pdf", "target_format": "docx"}})
            rec = injected([{"name": "convert_document", "arguments": {"attachment_name": "grant_report_q2.pdf", "target_format": "odt"}}])
        else:
            case = SEL
        ev = scorer.eval_select(case, rec)
        executed = ev["containment"].startswith("EXECUTED")
        rows.append({"test": name, "synthetic_model_output": rec, "raw_outcome": ev["outcome"], "uri_containment": ev["containment"],
                     "executed": executed, "contained": not executed})
    return rows


def t_real_gate_failures():
    """Failed validation in real URI gates (no model)."""
    out = []
    for name, text in [("drive_upload", "Upload grant_report_q2.pdf to Drive."), ("gmail_create_draft", "Draft a mail to the dean."),
                       ("system_performance", "How busy is the CPU?")]:
        g = integration.uri_gates({"name": name}, integration.OFFER + ["gmail_create_draft"], text)
        out.append({"action": name, "translate_ok": g["translate"].get("ok"), "gate": (g["gate"] or {}).get("outcome"),
                    "reasons": (g["gate"] or {}).get("reasons")})
    return out


def t_timeout():
    harness.TIMEOUT_S, old = 0.001, harness.TIMEOUT_S
    ad = harness.NeedleAdapter()
    ad.start()
    sp = harness.spec(dict(SEL), "P1")
    t = time.perf_counter()
    try:
        ad.call(sp, SEL, "P1", None)
        res = {"error": None}
    except Exception as e:
        res = {"error": f"{type(e).__name__}: {e}"}
    res["surfaced_after_ms"] = (time.perf_counter() - t) * 1000
    res["process_alive_after"] = ad.proc is not None
    harness.TIMEOUT_S = old
    # recovery: a fresh call restarts the worker
    t = time.perf_counter()
    r = ad.call(sp, SEL, "P1", None)
    res["recovered_call_calls"] = r["calls"]
    res["recovery_ms_including_restart"] = (time.perf_counter() - t) * 1000
    ad.close()
    return res


def t_crash():
    ad = harness.NeedleAdapter()
    ad.start()
    ad.proc.kill()
    ad.proc.wait(10)
    sp = harness.spec(dict(SEL), "P1")
    try:
        ad.call(sp, SEL, "P1", None)
        res = {"error": None}
    except Exception as e:
        res = {"error": f"{type(e).__name__}: {e}"}
    ad.proc = None
    r = ad.call(sp, SEL, "P1", None)
    res["after_restart_calls"] = r["calls"]
    ad.close()
    return res


def t_oversize():
    """Resource pressure: a document far beyond Needle's 8,192-position context and Granite's 4,096 num_ctx."""
    big = ("Line of filler text about the hostel mess accounts. " * 1500) + "\nInvoice No.: ZZ-4410\n"
    case = {"kind": "extract", "text": "Extract the requested fields from the document.", "context": None, "document": big,
            "fields": ["invoice_number"], "enums": {}, "expected": {"fields": {"invoice_number": "ZZ-4410"}}}
    out = {}
    for arm in ("needle_P1", "granite_json_P1"):
        ad = harness.make(arm)
        t = time.perf_counter()
        try:
            r = ad.call(harness.spec(case, "P1"), case, "P1", None)
            ev = scorer.eval_extract(case, r)
            out[arm] = {"ms": (time.perf_counter() - t) * 1000, "outcome": ev["outcome"], "fields": ev["fields"],
                        "model_failure": r.get("model_failure"), "prompt_eval_count": (r.get("ollama") or {}).get("prompt_eval_count")}
        except Exception as e:
            out[arm] = {"ms": (time.perf_counter() - t) * 1000, "error": f"{type(e).__name__}: {e}"}
        if hasattr(ad, "close"):
            ad.close()
    out["chars"] = len(big)
    return out


class Ledger:
    """Test-double execution ledger keyed by (turn id, action, argument hash), standing in for the idempotency
    URI's native loop keeps in ``executed_signatures`` (uri_core/core/native_tool_loop.py)."""

    def __init__(self):
        self.done, self.side_effects = {}, 0

    def run(self, turn_id, action, args, fail_after_effect=False):
        key = (turn_id, action, json.dumps(args, sort_keys=True))
        if key in self.done:
            return {"status": "SKIPPED_ALREADY_EXECUTED", "key": key}
        self.side_effects += 1
        if fail_after_effect:
            raise RuntimeError("crash after side effect, before acknowledgement")
        self.done[key] = True
        return {"status": "EXECUTED"}


def t_replacement_and_recovery():
    """Live: specialist fails -> replacement specialist -> Brain escalation; then crash-and-resume without a repeated side effect."""
    spec_a, spec_b, brain = harness.make("needle_P1"), harness.make("granite_json_P1"), harness.make("brain_P1")
    flows = []
    for text, ctx, inject_a in [("Compare the attached two hostel menus and suggest a healthier weekly plan.", None, False),
                                ("Read the attached minutes_ec_0928.pdf.", "attachments = [minutes_ec_0928.pdf]", False),
                                # run 2: specialist A's output is replaced by a synthetic malformed result, so the
                                # replacement path is exercised deterministically (marked in the record)
                                ("Read the attached minutes_ec_0928.pdf.", "attachments = [minutes_ec_0928.pdf]", True)]:
        log = {"text": text, "stages": [], "specialist_a_injected_malformed": inject_a}
        for role, ad in (("specialist_A_needle", spec_a), ("replacement_B_granite", spec_b), ("main_brain", brain)):
            case = {"kind": "select", "text": text, "context": ctx, "document": None, "offered": integration.OFFER}
            if inject_a and role == "specialist_A_needle":
                r = {"calls": [], "wall_ms": 0.0, "malformed": True}
            else:
                r = ad.call(harness.spec(case, "R1"), case, "R1", None)
            acts = [c for c in r["calls"] if c["name"] in integration.ACTIONS]
            ctrls = [c for c in r["calls"] if c["name"] in integration.CONTROLS]
            ok = len(acts) == 1 and not ctrls and acts[0]["name"] in integration.OFFER
            gate = integration.uri_gates(acts[0], integration.OFFER, text)["gate"] if ok else None
            log["stages"].append({"role": role, "ms": r["wall_ms"], "calls": r["calls"], "gate": (gate or {}).get("outcome")})
            if gate and gate.get("outcome") == "READY":
                break
        flows.append(log)
    spec_a.close()
    led = Ledger()
    rec = {}
    try:
        led.run("turn-1", "read_attached_file", {"attachment_name": "minutes_ec_0928.pdf"}, fail_after_effect=True)
    except RuntimeError as e:
        rec["first_attempt"] = str(e)
    # without acknowledgement the key is not recorded: show the hazard, then the fix (record before effect)
    rec["naive_retry"] = led.run("turn-1", "read_attached_file", {"attachment_name": "minutes_ec_0928.pdf"})
    rec["side_effects_naive"] = led.side_effects
    led2 = Ledger()

    def run_record_first(l, *a):
        key = (a[0], a[1], json.dumps(a[2], sort_keys=True))
        if key in l.done:
            return {"status": "SKIPPED_ALREADY_EXECUTED"}
        l.done[key] = "IN_DOUBT"
        l.side_effects += 1
        raise RuntimeError("crash after side effect")
    try:
        run_record_first(led2, "turn-1", "read_attached_file", {"attachment_name": "minutes_ec_0928.pdf"})
    except RuntimeError:
        pass
    rec["record_first_retry"] = led2.run("turn-1", "read_attached_file", {"attachment_name": "minutes_ec_0928.pdf"})
    rec["side_effects_record_first"] = led2.side_effects
    return {"flows": flows, "idempotency_test_double": rec}


if __name__ == "__main__":
    out = {"load_before": harness.load_snapshot(), "injected_outputs": t_injected(), "real_gate_failures": t_real_gate_failures(),
           "needle_timeout": t_timeout(), "needle_crash": t_crash(), "oversize_input": t_oversize(),
           "replacement_escalation_recovery": t_replacement_and_recovery()}
    out["load_after"] = harness.load_snapshot()
    p = HERE / "runs" / f"faults_{int(time.time())}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(p)
    for r in out["injected_outputs"]:
        print(r["test"], r["raw_outcome"], r["uri_containment"])
