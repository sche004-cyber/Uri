"""LIVE qualification of text intelligence on Runtime v1 (TI-AC10, TI-AC11 in-process part).

Runs the draft desk through the real `IntegratedTurns` bridge (the same code the integrated worker runs, minus the
paired Core, which drafting never uses) against the RUNNING Runtime v1 server. It never starts or stops a model:
start Runtime v1 first with the host from the materialized runtime, and only when no other GPU workload runs.

    <venv>\\python.exe scripts\\ti_live_matrix.py [--url http://127.0.0.1:18470] [--tier fast|normal]
                                                  [--only M1,M2] [--baseline] [--repeat N]

Writes docs/text_intelligence/evidence/ti_live_matrix_<ts>.json: every step's input (typed or SIMULATED transcript),
route, draft text, changed blocks, flags, metrics and automatic checks. Automatic checks are deliberately narrow
(fact presence/absence, locality, version state); the drafts themselves are reviewed by reading them.

--baseline also runs the creation prompts through the accepted answer channel (68cac3d behaviour for a language
request) and the warden revisions as plain follow-up turns, for comparison. The baseline path has no versions, so
"undo" is recorded as unsupported.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_operational_intelligence import answer as A                      # noqa: E402
from uri_operational_intelligence import brain_client as BC               # noqa: E402
from uri_operational_intelligence import text_input as TI                 # noqa: E402
from uri_operational_intelligence import triage as T                      # noqa: E402
from uri_operational_intelligence.orchestrator import Orchestrator        # noqa: E402
from uri_operational_intelligence.reasoning_policy import FAST, NORMAL    # noqa: E402
from uri_operational_intelligence.runtime_v1 import Readiness             # noqa: E402
from uri_operational_intelligence.task_ledger import TaskLedger           # noqa: E402
from uri_operational_intelligence.worker_bridge import IntegratedTurns    # noqa: E402

EVIDENCE = ROOT / "docs/text_intelligence/evidence"


def sim(raw, uncertain=None, language="en-IN"):
    t = {"raw": raw, "engine": "simulated", "simulated": True, "language": language}
    if uncertain:
        t["uncertain"] = uncertain
    return {"schema": TI.SCHEMA, "source": "transcript", "transcript": t}


def has(text, *words):
    low = text.lower()
    return all(re.search(r"(?<![\w])" + re.escape(w.lower()) + r"(?![\w])", low) for w in words)


def lacks(text, *words):
    low = text.lower()
    return not any(re.search(r"(?<![\w])" + re.escape(w.lower()) + r"(?![\w])", low) for w in words)


# A step: (text, input envelope or None, checks: list of (name, fn(step_result, history) -> bool))
WARDEN = ("URI draft a letter to the warden regarding five students, sorry seven students, who left the hostel on "
          "Monday without permission. Make it formal.")
CASES = {
    "M1_owner_demo": [
        (WARDEN, None, [("seven_not_five", lambda r, h: has(r["text"], "seven") or has(r["text"], "7")),
                        ("five_absent", lambda r, h: lacks(r["text"], "five", "5")),
                        ("monday", lambda r, h: has(r["text"], "monday")),
                        ("version_1", lambda r, h: r["version"] == 1)]),
        ("Actually, don't say without permission. Say they left without recording their departure in the hostel "
         "register.", None,
         [("phrase_gone", lambda r, h: lacks(r["text"], "without permission")),
          ("register_wording", lambda r, h: has(r["text"], "hostel register")),
          ("seven_kept", lambda r, h: has(r["text"], "seven") or has(r["text"], "7")),
          ("unrelated_blocks_identical", lambda r, h: r["unchanged_blocks_identical"]),
          ("version_2", lambda r, h: r["version"] == 2)]),
        ("Make it more diplomatic and shorten the second paragraph.", None,
         [("register_kept", lambda r, h: has(r["text"], "register")),
          ("seven_kept", lambda r, h: has(r["text"], "seven") or has(r["text"], "7")),
          ("permission_not_back", lambda r, h: lacks(r["text"], "without permission")),
          ("second_para_shorter", lambda r, h: r["body_len"](1, h[-1]) < r["body_len"](1, h[-2]) if len(h) > 1 else False),
          ("version_3", lambda r, h: r["version"] == 3)]),
        ("Undo the last change.", None,
         [("restored_v2_text", lambda r, h: r["text"] == h[-3]["text"]),      # h[-1] is this step, h[-2] is v3
          ("no_model_call", lambda r, h: not r["metrics"].get("model_used")),
          ("position_2_of_3", lambda r, h: r["position"] == 2 and r["count"] == 3)]),
    ],
    "M2_spoken_date_correction": [
        ("URI write a letter to the warden about the students leaving hostel yesterday, no wait, on the 6th, and make "
         "it formal.", "SIM",
         [("sixth", lambda r, h: has(r["text"], "6th") or has(r["text"], "sixth")),
          ("yesterday_gone", lambda r, h: lacks(r["text"], "yesterday")),
          ("labelled_simulated", lambda r, h: r["source"].get("simulated") is True)]),
    ],
    "M3_multiple_corrections_one_statement": [
        ("Draft an email to the accounts office saying the fee of 4500, sorry, 5400 rupees was paid on Tuesday, no, "
         "Wednesday, by Anil, I mean Sunil Verma.", "SIM",
         [("5400", lambda r, h: has(r["text"], "5400") or has(r["text"], "5,400")),
          ("4500_gone", lambda r, h: lacks(r["text"], "4500", "4,500")),
          ("wednesday", lambda r, h: has(r["text"], "wednesday")), ("tuesday_gone", lambda r, h: lacks(r["text"], "tuesday")),
          ("sunil", lambda r, h: has(r["text"], "sunil")), ("anil_gone", lambda r, h: lacks(r["text"], "anil"))]),
    ],
    "M4_number_correction_after_draft": [
        ("Write a notice that the hostel mess will be closed for two days from Sunday for repairs.", None,
         [("two", lambda r, h: has(r["text"], "two") or has(r["text"], "2"))]),
        ("Sorry, not two days, three.", "SIM",
         [("three", lambda r, h: has(r["text"], "three") or has(r["text"], "3")),
          ("two_gone", lambda r, h: lacks(r["text"], "two days", "2 days")),
          ("sunday_kept", lambda r, h: has(r["text"], "sunday"))]),
    ],
    "M5_i_meant_tuesday": [
        ("Draft a short email to Professor Mehta asking to reschedule our meeting to Monday at 3 pm.", None,
         [("monday", lambda r, h: has(r["text"], "monday"))]),
        ("No, I meant Tuesday.", "SIM",
         [("tuesday", lambda r, h: has(r["text"], "tuesday")), ("monday_gone", lambda r, h: lacks(r["text"], "monday")),
          ("time_kept", lambda r, h: has(r["text"], "3 pm") or has(r["text"], "3:00") or has(r["text"], "3 p.m."))]),
    ],
    "M6_misheard_name": [
        ("write an email to Priya near about the budget meeting on Friday", "SIM_UNCERTAIN:Priya near",
         [("flagged", lambda r, h: "POSSIBLE_MISHEARING" in r["flag_codes"]),
          ("not_silently_changed", lambda r, h: lacks(r["text"], "nair") or "POSSIBLE_MISHEARING" in r["flag_codes"]),
          ("friday", lambda r, h: has(r["text"], "friday"))]),
    ],
    "M7_hinglish": [
        ("principal ko ek leave application likho, kal se teen din ki chutti chahiye, beti ki shaadi hai", "SIM_HI",
         [("english", lambda r, h: has(r["text"], "leave")),
          ("three_days", lambda r, h: has(r["text"], "three") or has(r["text"], "3")),
          ("daughter_wedding", lambda r, h: has(r["text"], "daughter") and (has(r["text"], "wedding") or has(r["text"], "marriage"))),
          ("no_invented_date", lambda r, h: "NEW_DETAIL" not in r["flag_codes"] or "[" in r["text"])]),
        ("isko thoda chhota karo", "SIM_HI", [("shorter", lambda r, h: len(r["text"]) < len(h[-2]["text"]))]),
    ],
    "M8_indian_english_numbers": [
        ("pls write one letter to bank manager for changing my mobile number in account, old number is 9876543210 new "
         "is 9123456780, do the needful", None,
         [("old_kept", lambda r, h: "9876543210" in r["text"]), ("new_kept", lambda r, h: "9123456780" in r["text"]),
          ("order_kept", lambda r, h: r["text"].find("9876543210") < r["text"].find("9123456780"))]),
    ],
    "M9_long_dictation": [
        ("Write a short report summary from this: um so the hostel inspection was done on the 3rd of October by the "
         "committee, uh, we checked all forty two rooms, and we found that eleven rooms had broken fans, six rooms had "
         "leaking taps, and two rooms, sorry, three rooms had damaged windows. The mess kitchen was clean but the "
         "storage area needs pest control. Total estimated repair cost is around eighty five thousand rupees and the "
         "committee recommends finishing the work before the exams start in November.", "SIM",
         [("42", lambda r, h: has(r["text"], "42") or has(r["text"], "forty-two") or has(r["text"], "forty two")),
          ("11", lambda r, h: has(r["text"], "11") or has(r["text"], "eleven")),
          ("6", lambda r, h: has(r["text"], "6") or has(r["text"], "six")),
          ("three_windows", lambda r, h: has(r["text"], "three") or has(r["text"], "3")),
          ("two_windows_gone", lambda r, h: not re.search(r"(?<!forty-)(?<!forty )\b(?:two|2) rooms", r["text"], re.I)),
          ("85000", lambda r, h: any(x in r["text"].lower().replace(",", "") for x in ("85000", "eighty-five thousand",
                                                                                        "eighty five thousand", "85 thousand"))),
          ("november", lambda r, h: has(r["text"], "november")), ("3rd_oct", lambda r, h: has(r["text"], "october"))]),
    ],
    "M10_contradiction": [
        ("Draft a notice that the library will be closed on Saturday and also that it will be open on Saturday as usual.",
         None, [("clarified", lambda r, h: r["status"] == "needs_user")]),
    ],
    "M11_revise_first_paragraph_only": [
        ("Draft a letter to the hostel warden requesting permission for a cultural event in the common room on Friday "
         "evening from 6 pm to 9 pm. Mention that about forty students will attend, that we will clean the room "
         "afterwards, and that the event coordinator is Kavya.", None,
         [("forty", lambda r, h: has(r["text"], "forty") or has(r["text"], "40")), ("kavya", lambda r, h: has(r["text"], "kavya"))]),
        ("Make the first paragraph more formal. Keep everything else the same.", None,
         [("only_first_body_changed", lambda r, h: r["changed_roles_ok"](["body:0"])),
          ("kavya_kept", lambda r, h: has(r["text"], "kavya"))]),
    ],
    "M12_grammar_only": [
        ("Correct this: me and my friend goes to college daily but yesterday we was late because bus not came, our "
         "principal Mr. Iyer give us warning.", None,
         [("no_meaning_flag", lambda r, h: "MEANING_CHANGED" not in r["flag_codes"]),
          ("iyer", lambda r, h: has(r["text"], "iyer")), ("yesterday", lambda r, h: has(r["text"], "yesterday")),
          ("not_formalised", lambda r, h: len(r["text"]) < 1.5 * len(h[-1]["first_text"]) + 40),
          ("original_kept_v1", lambda r, h: r["count"] == 2)]),
    ],
    "M13_exclusion": [
        ("Write a short note to the class teacher that the student Rahul Sharma was absent on Monday due to fever.", None,
         [("rahul", lambda r, h: has(r["text"], "rahul"))]),
        ("Don't mention the student's name.", None,
         [("rahul_gone", lambda r, h: lacks(r["text"], "rahul", "sharma")),
          ("monday_kept", lambda r, h: has(r["text"], "monday")), ("fever_kept", lambda r, h: has(r["text"], "fever"))]),
    ],
    "M14_ambiguous_correction": [
        ("Write a notice that the hostel fee must be paid by the 5th, and the late fee applies from the 15th.", None,
         [("both_dates", lambda r, h: has(r["text"], "5th") and has(r["text"], "15th"))]),
        ("Change the date to the 10th.", None,
         [("clarified_or_flagged", lambda r, h: r["status"] == "needs_user")]),
    ],
    "M15_remove_previous_sentence": [
        ("Draft an email to the librarian asking to extend the due date of the book Clean Code by one week.", None, []),
        ("Add a sentence saying I will return it in good condition.", None,
         [("added", lambda r, h: has(r["text"], "good condition"))]),
        ("Remove the previous sentence.", None,
         [("removed", lambda r, h: lacks(r["text"], "good condition")),
          ("book_kept", lambda r, h: has(r["text"], "clean code"))]),
    ],
    "M16_rewrite_politely": [
        ("Rewrite politely: send me the attendance report by today evening otherwise I will escalate.", None,
         [("today_evening", lambda r, h: has(r["text"], "evening") and (has(r["text"], "today") or has(r["text"], "this evening"))),
          ("no_new_detail", lambda r, h: "NEW_DETAIL" not in r["flag_codes"])]),
    ],
    "M17_expand_notes": [
        ("Expand these notes into a circular: water supply off tue 10am-2pm, block A and B, maintenance, store water "
         "in advance", None,
         [("times", lambda r, h: (has(r["text"], "10") and has(r["text"], "2"))),
          ("blocks", lambda r, h: has(r["text"], "block a") or has(r["text"], "blocks a")),
          ("tuesday", lambda r, h: has(r["text"], "tuesday") or has(r["text"], "tue"))]),
    ],
    "M18_greeting_fast_path": [
        ("hello", None, [("not_desk", lambda r, h: r["route"] == "answer")]),
    ],
    # L-9: live runs of the verifier scenarios that Codex TI rounds 12-15 repaired (unit-tested only until now).
    # Rule checked: every value the user gave is either in the draft or named by a visible flag (TI-AC4: a change is
    # never hidden); and a draft that keeps every value carries no error flag (precision).
    "L9a_grammar_clock_currency": [
        ("Correct the grammar only: the bus departure are at 18:00 from the east gate and the fee are Rs5400 per "
         "student.", None,
         [("clock_kept_or_flagged", lambda r, h: kept_or_flagged(r, "18:00")),
          ("amount_kept_or_flagged", lambda r, h: kept_or_flagged(r, "rs5400", "rs 5400", "rs. 5400", "5400", "5,400")),
          ("no_error_if_kept", lambda r, h: not (has(r["text"], "18:00") and "5400" in r["text"].replace(",", ""))
           or not error_flags(r)),
          ("grammar_route", lambda r, h: r["route"] == "draft")]),
    ],
    "L9b_comma_replacement": [
        ("Write a short notice that the visitors' gate is in the west wing and opens at 9 am.", None,
         [("west_wing", lambda r, h: has(r["text"], "west wing"))]),
        ("Don't say west wing; say east wing, sector C.", None,
         [("replacement_whole_or_flagged", lambda r, h: (has(r["text"], "east wing") and has(r["text"], "sector c"))
           or flag_names(r, "sector c", "east wing")),
          ("old_gone_or_flagged", lambda r, h: lacks(r["text"], "west wing") or flag_names(r, "west wing")),
          ("time_kept_or_flagged", lambda r, h: kept_or_flagged(r, "9 am", "9:00", "9 a.m.", "09:00", "9am",
                                                                "nine"))]),
    ],
    "L9c_title_replacement": [
        ("Write a two-line note that the advisor will attend the parents' meeting on Friday.", None,
         [("advisor", lambda r, h: has(r["text"], "advisor"))]),
        ("Replace advisor with Dr. Mehta.", None,
         [("dr_mehta_or_flagged", lambda r, h: has(r["text"], "mehta") or flag_names(r, "mehta")),
          ("no_bare_dr", lambda r, h: not re.search(r"\bDr\.?\s+(will|is|has)\b", r["text"])
           or flag_names(r, "mehta", "dr.")),
          ("friday_kept_or_flagged", lambda r, h: kept_or_flagged(r, "friday"))]),
    ],
    "L9d_hinglish_kal": [
        ("Principal ko leave application likho: kal se teen din ki chutti chahiye, ghar mein function hai.", "SIM_HI",
         [("not_yesterday_or_flagged", lambda r, h: lacks(r["text"], "yesterday")
           or flag_names(r, "yesterday", "kal", "tomorrow")),
          ("three_days", lambda r, h: kept_or_flagged(r, "three", "3")),
          ("drafted", lambda r, h: r["route"] == "draft" and r["version"] == 1)]),
    ],
    "L9e_tone_change_keeps_facts": [
        ("Draft an email to the accounts office: the fee of 5400 rupees was paid on Wednesday by Sunil Verma, receipt "
         "number 2231.", None,
         [("facts", lambda r, h: has(r["text"], "wednesday") and has(r["text"], "sunil") and "2231" in r["text"])]),
        ("Make it warmer and a bit shorter.", None,
         [("amount_kept_or_flagged", lambda r, h: kept_or_flagged(r, "5400", "5,400")),
          ("receipt_kept_or_flagged", lambda r, h: kept_or_flagged(r, "2231")),
          ("name_kept_or_flagged", lambda r, h: kept_or_flagged(r, "sunil")),
          ("no_error_if_kept", lambda r, h: not ("2231" in r["text"] and has(r["text"], "sunil"))
           or not error_flags(r))]),
    ],
}


def flag_names(r, *values):
    """A visible flag names one of the values (an unrelated flag does not count; Codex TIWS r1 L9-1)."""
    details = " ".join(str(f.get("detail", "")) for f in r["flags"]).lower()
    return any(v.lower() in details for v in values)


def kept_or_flagged(r, *values):
    """The value is in the draft as a whole token, or a visible flag names it (nothing is changed silently).
    Presence is not meaning: the drafts themselves are read in the review (Codex TIWS r1 L9-2)."""
    return any(has(r["text"], v) for v in values) or flag_names(r, *values)


def error_flags(r):
    return [f for f in r["flags"] if f.get("severity") == "error"]


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, ev):
        self.events.append(ev)


def run_step(b, rec, sid, text, env, timeout=240):
    n0 = len(rec.events)
    t0 = time.monotonic()
    cmd = {"command": "oi_turn", "session_id": sid, "text": text, "depth": "auto"}
    if env is not None:
        cmd["input"] = env
    r = b.handle("oi_turn", cmd)
    b.wait(timeout)
    wall = round(time.monotonic() - t0, 3)
    evs = [e for e in rec.events[n0:] if e["turn_id"] == r["turn_id"]]
    get = lambda t: [e["data"] for e in evs if e["type"] == t]
    routed = (get("turn.routed") or [{}])[-1]
    fin = (get("turn.finished") or [{}])[-1]
    done = (get("answer.done") or [{}])[-1]
    upd = (get("draft.updated") or [None])[-1]
    draft = (upd or {}).get("draft") if upd else b.desk.snapshot(sid)
    cur = (draft or {}).get("current") or {}
    return {"text_in": text, "input": env, "route": routed.get("route"), "text_kind": (routed.get("triage") or {}).get("text_kind"),
            "status": fin.get("status"), "wall_s": wall, "metrics": done.get("metrics") or {},
            "answer": "".join(d.get("text", "") for d in get("answer.delta")),
            "question": (get("draft.clarify") or [{}])[-1].get("question"),
            "errors": get("error"), "op": (upd or {}).get("op"),
            "version": cur.get("n"), "position": (draft or {}).get("position"), "count": (draft or {}).get("count"),
            "text": cur.get("text", ""), "blocks": cur.get("blocks", []), "changed": cur.get("changed", []),
            "flags": cur.get("flags", []), "flag_codes": [f["code"] for f in cur.get("flags", [])],
            "missing": cur.get("missing", []), "source": (draft or {}).get("source") or {},
            "first_text": ((draft or {}).get("first") or {}).get("text", "")}


def envelope(kind, text):
    if kind is None:
        return None
    if kind == "SIM":
        return sim(text)
    if kind == "SIM_HI":
        return sim(text, language="hi-IN")
    if kind.startswith("SIM_UNCERTAIN:"):
        return sim(text, uncertain=[kind.split(":", 1)[1]])
    raise ValueError(kind)


def body_len_fn(i, step):
    bodies = [b["text"] for b in step["blocks"] if b["role"] == "body"]
    return len(bodies[i]) if i < len(bodies) else 10 ** 9


def run_case(b, rec, name, steps):
    sid = str(uuid.uuid4())
    hist = []
    for text, kind, checks in steps:
        r = run_step(b, rec, sid, text, envelope(kind, text))
        prev = hist[-1] if hist else None
        if prev and prev["blocks"] and r["blocks"]:
            pb = {x["id"]: x for x in prev["blocks"]}
            r["unchanged_blocks_identical"] = all(pb[x["id"]]["text"] == x["text"] for x in r["blocks"]
                                                  if x["id"] in pb and x["id"] not in r["changed"])
            prev_body = [x["id"] for x in prev["blocks"] if x["role"] == "body"]
            r["_prev_body"] = prev_body
        else:
            r["unchanged_blocks_identical"] = None
        hist.append(r)
        ctx = dict(r, body_len=body_len_fn,
                   changed_roles_ok=lambda allowed, r=r: set(r["changed"]) <= {
                       r.get("_prev_body", [None])[int(a.split(":")[1])] for a in allowed if a.startswith("body:")})
        r["checks"] = {}
        for cname, fn in checks:
            try:
                r["checks"][cname] = bool(fn(ctx, hist))
            except Exception as exc:       # a check that cannot be evaluated is a failure, not a pass
                r["checks"][cname] = False
                r.setdefault("check_errors", {})[cname] = repr(exc)
        r.pop("_prev_body", None)
        print("  %-40s %-6s %-9s v%-3s %6.2fs %s" % (name if len(hist) == 1 else "", r["route"], r["status"], r["version"],
                                                    r["wall_s"], " ".join(("+" if v else "-") + k for k, v in r["checks"].items())))
    return hist


def run_baseline(client, name, steps):
    """Accepted 68cac3d behaviour for these requests: triage class + the answer channel with history (no desk)."""
    history, out = [], []
    for text, kind, _ in steps:
        tri = T.triage(text).kind
        t0 = time.monotonic()
        res = A.answer(client, text, tier=FAST, history=history, deadlines=BC.Deadlines(total_s=240))
        r = {"text_in": text, "baseline_triage": tri, "status": res.status, "wall_s": round(time.monotonic() - t0, 3),
             "text": res.text, "metrics": res.metrics,
             "note": "68cac3d routes ACTION-class requests to Core first; Core has no drafting capability in the WS "
                     "composition, so a CONVERSATION reply then falls back to this answer channel" if tri == T.ACTION else None}
        history += [{"role": "user", "content": text}, {"role": "assistant", "content": res.text}]
        out.append(r)
        print("  [baseline] %-28s %-10s %-9s %6.2fs" % (name if len(out) == 1 else "", tri, res.status, r["wall_s"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18470")
    ap.add_argument("--tier", choices=["fast", "normal"], default="fast")
    ap.add_argument("--only", default="")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args(argv)
    client = BC.BrainClient(a.url)
    import httpx
    health = httpx.get(a.url + "/health", timeout=5).json()
    props = httpx.get(a.url + "/props", timeout=5).json()
    model = Path(str(props.get("model_path") or "")).name
    status = lambda: Readiness("READY", a.url, model_id=model)
    tmp = Path(tempfile.mkdtemp(prefix="ti_live_"))
    o = Orchestrator(client=client, core=None, brain_selection={}, ledger=TaskLedger(tmp), capability_ids=set(),
                     readiness=status, harness_statuses=lambda: [])
    rec = Recorder()
    b = IntegratedTurns(orchestrator=o, cfg={"model": {"id": model}, "runtime": {}}, status=status, write_event=rec)
    b.desk.tier = NORMAL if a.tier == "normal" else FAST
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    report = {"schema": "uri.ti.live_matrix.v1", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "url": a.url,
              "health": health, "model": model, "tier": a.tier, "input_note": "Transcript inputs are SIMULATED "
              "(typed text in the uri.text_input.v1 envelope, engine 'simulated'); no microphone or recogniser was used.",
              "cases": {}, "baseline": {}}
    for rep in range(a.repeat):
        for name, steps in CASES.items():
            if only and name.split("_")[0] not in only:
                continue
            key = name if a.repeat == 1 else "%s#%d" % (name, rep + 1)
            report["cases"][key] = run_case(b, rec, key, steps)
    # Cancellation and Brain-unavailable on the real path.
    if not only or "M19" in only:
        sid = str(uuid.uuid4())
        r = b.handle("oi_turn", {"command": "oi_turn", "session_id": sid, "text": WARDEN, "depth": "auto"})
        time.sleep(1.0)
        cancelled = b.handle("oi_cancel", {"command": "oi_cancel", "turn_id": r["turn_id"]})["cancelled"]
        b.wait(60)
        errs = [e["data"]["code"] for e in rec.events if e["turn_id"] == r["turn_id"] and e["type"] == "error"]
        report["cases"]["M19_cancel_during_generation"] = [{"cancel_accepted": cancelled, "error_codes": errs,
                                                            "draft_after": b.desk.snapshot(sid),
                                                            "checks": {"cancelled": "CANCELLED" in errs,
                                                                       "no_draft": b.desk.snapshot(sid) is None}}]
        print("  M19_cancel_during_generation", report["cases"]["M19_cancel_during_generation"][0]["checks"])
    if not only or "M20" in only:
        sid = str(uuid.uuid4())
        run_step(b, rec, sid, "Write a two line note to the mess manager thanking him for the Diwali dinner.", None)
        b.o.readiness = lambda: Readiness("STOPPED", a.url, model_id=model)    # simulated outage; runtime untouched
        r1 = run_step(b, rec, sid, "Make it more formal.", None)
        r2 = run_step(b, rec, sid, "Show me the original", None)
        b.o.readiness = status
        report["cases"]["M20_brain_unavailable_simulated"] = [r1, r2]
        r1["checks"] = {"brain_unavailable": any(e.get("code") == "BRAIN_UNAVAILABLE" for e in r1["errors"]),
                        "draft_unchanged": r1["version"] in (None, 1)}
        r2["checks"] = {"original_works_without_brain": r2["status"] == "ok"}
        print("  M20_brain_unavailable_simulated", r1["checks"], r2["checks"])
    if a.baseline:
        for name in ("M1_owner_demo", "M2_spoken_date_correction", "M3_multiple_corrections_one_statement",
                     "M7_hinglish", "M8_indian_english_numbers", "M9_long_dictation", "M12_grammar_only"):
            if only and name.split("_")[0] not in only:
                continue
            report["baseline"][name] = run_baseline(client, name, CASES[name])
    total = sum(len(s.get("checks", {})) for c in report["cases"].values() for s in c)
    passed = sum(sum(1 for v in s.get("checks", {}).values() if v) for c in report["cases"].values() for s in c)
    report["summary"] = {"checks": total, "passed": passed}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / ("ti_live_matrix_%s_%s.json" % (a.tier, time.strftime("%Y%m%dT%H%M%S")))
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8", newline="\n")
    print("checks passed %d/%d -> %s" % (passed, total, out))
    return 0 if passed == total else 1        # a failed check is never an exit-0 run (Codex TIWS r1 L9-3)


if __name__ == "__main__":
    raise SystemExit(main())
