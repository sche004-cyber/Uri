"""Writing Intelligence engine (plan 16, WI-1..WI-6): deterministic rules, Windows spelling, apply/undo, Brain
proofread / tone / completion with a fake Brain, privacy refusals."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from uri_assist import writing as W
from uri_operational_intelligence import brain_client as BC

CORPUS = json.loads((Path(__file__).parent / "data" / "writing_corpus.json").read_text(encoding="utf-8"))["items"]
WINDOWS = os.name == "nt"


class NoSpell:
    """A spell worker that is not available: the rules must still run."""
    def check(self, text, lang, wait=True):
        raise W.WritingError("SPELL_UNAVAILABLE")


class FakeSpell:
    def __init__(self, errors, lang="en-IN"):
        self.errors, self.lang, self.calls = errors, lang, 0

    def check(self, text, lang, wait=True):
        self.calls += 1
        return {"ok": True, "lang": self.lang, "errors": self.errors}


class FakeBrain:
    def __init__(self, answer, status=BC.COMPLETE, base_url="http://127.0.0.1:18080"):
        self.answer, self.status, self.bodies = answer, status, []
        self.base_url = base_url

    def stream_chat(self, body, cancel=None, deadlines=None):
        self.bodies.append(body)
        return BC.CallResult(status=self.status, text=json.dumps(self.answer) if self.answer is not None else "",
                             total_s=0.1)


def rules(text):
    return W.check(text, spell=NoSpell())


def fixes(res):
    return [(s["original"], s["replacements"][0] if s["replacements"] else "") for s in res["suggestions"]]


# ------------------------------------------------------------------------------------------- rules (WI-1)
def test_rules_find_spacing_punctuation_capitals_repeats_and_articles():
    t = "i saw the the file  today , it was ok!! the next step is a urgent review. An hotel and a hour."
    got = fixes(rules(t))
    assert ("i", "I") in got
    assert (" the", "") in got
    assert ("  ", " ") in got
    assert (" ", "") in got                     # space before the comma
    assert ("!!", "!") in got
    assert ("t", "T") in got                    # "the next step" after "!!"
    assert ("a", "an") in got                   # a urgent, a hour
    assert ("An", "A") in got                   # An hotel


def test_rules_leave_abbreviations_initials_references_and_links_alone():
    for t in ["Dy. Secy. said so.", "Shri R. K. Sharma came.", "w.e.f. 01.11.2026 the order applies.",
              "Mail admin.section@example.gov.in now.", "See e.g. the annexure.", "Rs. 4,50,000 sanctioned.",
              "Annexure A is attached.", "See item (a) of para 4.", "Wait... then go.", "No. 12/3/2026-Admin dated."]:
        assert rules(t)["suggestions"] == [], t


def test_spell_unavailable_reports_why_and_rules_still_run():
    r = W.check("i went", spell=NoSpell())
    assert r["status"]["spelling"] == "SPELL_UNAVAILABLE"
    assert ("i", "I") in fixes(r)


def test_spell_results_map_utf16_offsets_and_skip_proper_nouns():
    text = "Emoji \U0001F600 thier note to Iyer about tuesday"
    # UTF-16 offsets as Windows reports them: the emoji is two code units
    errs = [{"start": 9, "length": 5, "word": "thier", "action": 2, "replacement": "their", "suggestions": []},
            {"start": 23, "length": 4, "word": "Iyer", "action": 1, "replacement": "", "suggestions": ["Ayer"]},
            {"start": 34, "length": 7, "word": "tuesday", "action": 1, "replacement": "", "suggestions": ["Tuesday"]}]
    r = W.check(text, spell=FakeSpell(errs))
    got = fixes(r)
    assert ("thier", "their") in got and ("tuesday", "Tuesday") in got
    assert not any(o == "Iyer" for o, _ in got)
    s = next(x for x in r["suggestions"] if x["original"] == "thier")
    assert text[s["start"]:s["end"]] == "thier"


def test_dismissed_words_and_ids_are_not_offered_again():
    r = rules("i agree")
    sid = r["suggestions"][0]["id"]
    assert W.check("i agree", spell=NoSpell(), ignore=[sid])["suggestions"] == []


def test_too_long_text_is_refused_by_name():
    with pytest.raises(W.WritingError) as e:
        W.check("x" * (W.MAX_CHECK_CHARS + 1), spell=NoSpell())
    assert e.value.code == "TEXT_TOO_LONG"


# ------------------------------------------------------------------------------------------- apply / undo (WI-2)
def _acc(res, text):
    return [{"start": s["start"], "end": s["end"], "original": s["original"], "replacement": s["replacements"][0]}
            for s in res["suggestions"]]


def test_apply_all_and_undo_restores_exact_text():
    t = "i saw the the file  today , ok!!"
    r = rules(t)
    out = W.apply(t, _acc(r, t))
    assert out["text"] == "I saw the file today, ok!"
    back = W.apply(out["text"], out["undo"])
    assert back["text"] == t


def test_apply_refuses_stale_and_overlapping_items():
    t = "i agree"
    item = {"start": 0, "end": 1, "original": "i", "replacement": "I"}
    with pytest.raises(W.WritingError) as e:
        W.apply("I agree", [item])
    assert e.value.code == "STALE_SUGGESTION"
    with pytest.raises(W.WritingError) as e:
        W.apply(t, [item, {"start": 0, "end": 3, "original": "i a", "replacement": "x"}])
    assert e.value.code == "OVERLAPPING_SUGGESTIONS"
    with pytest.raises(W.WritingError) as e:
        W.apply(t, [{"start": 2, "end": 2, "original": "", "replacement": "x"},
                    {"start": 2, "end": 2, "original": "", "replacement": "y"}])
    assert e.value.code == "OVERLAPPING_SUGGESTIONS"


# ------------------------------------------------------------------------------------------- Brain (WI-4)
def test_proofread_turns_brain_text_into_corrections_and_meaning_changes_into_rewrites():
    t = "He dont attend the meeting on 12 October with Shri Rao."
    b = FakeBrain({"status": "ok", "message": "", "text":
                   "He does not attend the meeting on 14 October with Shri Rao."})
    r = W.proofread(t, client=b)
    by = {s["original"]: s for s in r["suggestions"]}
    assert by["12"]["class"] == "rewrite"                       # a number changed
    assert any(s["class"] == "correction" for s in r["suggestions"]) or any(
        s["class"] == "rewrite" for s in r["suggestions"])
    assert any(f["code"] == "MEANING_CHANGED" for f in r["flags"])
    body = b.bodies[0]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "UNTRUSTED DATA" in body["messages"][1]["content"]


def test_proofread_pure_grammar_fix_is_a_correction():
    t = "The files was sent yesterday."
    r = W.proofread(t, client=FakeBrain({"status": "ok", "message": "", "text": "The files were sent yesterday."}))
    assert [(s["original"], s["replacements"][0], s["class"]) for s in r["suggestions"]] == [("was", "were", "correction")]
    out = W.apply(t, [{**{k: r["suggestions"][0][k] for k in ("start", "end", "original")},
                       "replacement": "were"}])
    assert out["text"] == "The files were sent yesterday."


@pytest.mark.parametrize(("original", "edited", "protected"), [
    ("Ref. 12/3/2026 applies. They was informed.",
     "Ref. 12-3-2026 applies. They were informed.", "12/3/2026"),
    ("Clause (a) applies. They was informed.",
     "Clause a applies. They were informed.", "(a)"),
])
def test_proofread_reference_punctuation_requires_individual_accept(original, edited, protected):
    result = W.proofread(original, client=FakeBrain({"status": "ok", "message": "", "text": edited}))
    changes = result["suggestions"]
    assert changes
    reference_changes = [s for s in changes if s["original"] in {"/", "(", ")"}]
    assert len(reference_changes) == 2
    assert all(s["class"] == "rewrite" for s in reference_changes)
    accepted = [s for s in changes if s["class"] == "correction"]
    applied = W.apply(original, _acc({"suggestions": accepted}, original))["text"]
    assert protected in applied
    assert "They were informed." in applied


@pytest.mark.parametrize(("reference", "changed"), [
    ("12.3", "12:3"),
    ("12:3", "12.3"),
])
def test_proofread_accept_all_corrections_preserves_reference_separator(reference, changed):
    original = f"Ref. {reference} applies. They was informed."
    edited = f"Ref. {changed} applies. They were informed."
    result = W.proofread(original, client=FakeBrain({"status": "ok", "message": "", "text": edited}))
    changes = result["suggestions"]
    separator = [s for s in changes if s["original"] in {".", ":"}]
    assert len(separator) == 1
    assert separator[0]["class"] == "rewrite"
    accepted = [s for s in changes if s["class"] == "correction"]
    assert [(s["original"], s["replacements"][0]) for s in accepted] == [("was", "were")]
    applied = W.apply(original, _acc({"suggestions": accepted}, original))["text"]
    assert applied == f"Ref. {reference} applies. They were informed."


@pytest.mark.parametrize(("original", "edited", "protected", "reference_edits"), [
    ("Ref. 12/3 is pending. Annexure A is attached. They was informed.",
     "Ref: 12/3 is pending. Annexure An is attached. They were informed.",
     ("Ref.", "Annexure A"), {(".", ":"), ("A", "An")}),
    ("No. 12/3 is pending. Clause B is attached. They was informed.",
     "No: 12/3 is pending. Clause An is attached. They were informed.",
     ("No.", "Clause B"), {(".", ":"), ("B", "An")}),
    ("Annexure a is attached. They was informed.",
     "Annexure A is attached. They were informed.",
     ("Annexure a",), {("a", "A")}),
])
def test_proofread_accept_all_preserves_reference_labels_and_single_letter_ids(
        original, edited, protected, reference_edits):
    result = W.proofread(original, client=FakeBrain({"status": "ok", "message": "", "text": edited}))
    changes = result["suggestions"]
    assert {(s["original"], s["replacements"][0]) for s in changes if s["class"] == "rewrite"} == reference_edits
    accepted = [s for s in changes if s["class"] == "correction"]
    assert [(s["original"], s["replacements"][0]) for s in accepted] == [("was", "were")]
    applied = W.apply(original, _acc({"suggestions": accepted}, original))["text"]
    assert all(value in applied for value in protected)
    assert applied == original.replace("They was informed.", "They were informed.")


def test_proofread_ordinary_article_swap_remains_accept_all_correction():
    original = "A apple arrived."
    result = W.proofread(original, client=FakeBrain({"status": "ok", "message": "", "text": "An apple arrived."}))
    assert [(s["original"], s["replacements"][0], s["class"]) for s in result["suggestions"]] == [
        ("A", "An", "correction")]
    assert W.apply(original, _acc(result, original))["text"] == "An apple arrived."


def test_negation_change_is_never_a_correction():
    t = "The proposal is approved."
    r = W.proofread(t, client=FakeBrain({"status": "ok", "message": "", "text": "The proposal is not approved."}))
    assert r["suggestions"] and all(s["class"] == "rewrite" for s in r["suggestions"])


def test_rewrite_is_one_rewrite_suggestion_with_flags():
    t = "pls send the file to Rao by 5 pm"
    r = W.rewrite(t, "formal", client=FakeBrain({"status": "ok", "message": "", "text":
                                                  "Kindly send the file to Shri Rao by 5 p.m."}))
    assert len(r["suggestions"]) == 1 and r["suggestions"][0]["class"] == "rewrite"
    assert r["suggestions"][0]["start"] == 0 and r["suggestions"][0]["end"] == len(t)
    with pytest.raises(W.WritingError) as e:
        W.rewrite(t, "angry", client=FakeBrain(None))
    assert e.value.code == "BAD_TONE"


def test_complete_adds_at_the_end_and_flags_new_details():
    t = "Kindly forward the proposal"
    r = W.complete(t, client=FakeBrain({"status": "ok", "message": "", "text": "to the Finance Division by 30 October."}))
    s = r["suggestions"][0]
    assert s["start"] == s["end"] == len(t) and s["class"] == "rewrite"
    assert s["replacements"][0].startswith(" to the Finance")
    assert any(f["code"] == "NEW_DETAIL" for f in r["flags"])


def test_brain_cannot_unreachable_and_bad_output_are_named():
    assert W.proofread("abc def.", client=FakeBrain({"status": "cannot", "message": "Not text.", "text": ""}))["suggestions"] == []
    with pytest.raises(W.WritingError) as e:
        W.proofread("abc def.", client=FakeBrain(None, status=BC.UNREACHABLE))
    assert e.value.code == "BRAIN_UNAVAILABLE"
    with pytest.raises(W.WritingError) as e:
        W.proofread("abc def.", client=FakeBrain({"oops": 1}))
    assert e.value.code == "BRAIN_OUTPUT_INVALID"


# ------------------------------------------------------------------------------------------- privacy (WI-5)
def test_sensitive_fields_and_secret_text_never_reach_the_brain():
    b = FakeBrain({"status": "ok", "message": "", "text": "x"})
    with pytest.raises(W.WritingError) as e:
        W.proofread("my text", client=b, field={"type": "password", "name": "pw"})
    assert e.value.code == "SENSITIVE_FIELD"
    with pytest.raises(W.WritingError) as e:
        W.rewrite("card 4111 1111 1111 1111 please", "formal", client=b)
    assert e.value.code == "SENSITIVE_TEXT"
    with pytest.raises(W.WritingError) as e:
        W.complete("key sk-abcdefghijklmnopqrstuvwxyz0123456789 is", client=b)
    assert e.value.code == "SENSITIVE_TEXT"
    assert b.bodies == []
    # the deterministic layer still works locally on such text
    assert W.check("i paid with card 4111 1111 1111 1111", spell=NoSpell())["suggestions"]


# ------------------------------------------------------------------------------------------- real Windows spelling
@pytest.mark.skipif(not WINDOWS, reason="Windows Spell Checking API")
def test_windows_corpus_finds_expected_fixes_and_never_touches_protected_text():
    misses, touched = [], []
    for item in CORPUS:
        t = item["text"]
        r = W.check(t)
        assert r["status"]["spelling"] == "ok", r["status"]
        got = fixes(r)
        for o, rep in item["fix"]:
            if not any(g == (o, rep) or (g[0].lower().startswith(o.lower()) and g[1].lower().startswith(rep.lower()))
                       for g in got):
                misses.append((t, o, rep, got))
        for k in item["keep"]:
            a = t.index(k)
            for s in r["suggestions"]:
                if s["start"] < a + len(k) and s["end"] > a and s["start"] != s["end"]:
                    touched.append((t, k, s["original"], s["replacements"]))
    assert not touched, touched
    assert not misses, misses


@pytest.mark.skipif(not WINDOWS, reason="Windows Spell Checking API")
def test_windows_latency_warm_check_is_fast():
    W.check("warm up")
    text = ("This is an ordinary sentence about the office work with some words. " * 15)[:1000]
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        W.check(text)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    assert times[18] < 50, times


# ------------------------------------------------------------------------------------------- worker bridge commands
class SlowBrain(FakeBrain):
    """Waits until cancelled or released, then answers."""
    def __init__(self, answer):
        super().__init__(answer)
        import threading
        self.release = threading.Event()

    def stream_chat(self, body, cancel=None, deadlines=None):
        self.bodies.append(body)
        while not self.release.wait(0.01):
            if cancel is not None and cancel.cancelled:
                return BC.CallResult(status=BC.CANCELLED)
        return BC.CallResult(status=BC.COMPLETE, text=json.dumps(self.answer), total_s=0.1)


def _bridge(client, idle=True, events=None):
    from uri_assist import bridge as B
    br = B.AssistCommands(brain_client=client, brain_idle=lambda: idle,
                          write_event=(events.append if events is not None else None))
    return B, br


def test_bridge_check_and_apply_need_no_grant_and_keep_exact_keys(monkeypatch):
    monkeypatch.setattr(W, "default_spell", lambda: NoSpell())
    B, br = _bridge(None)
    r = br.handle("assist_write_check", {"command": "assist_write_check", "text": "i agree"})
    assert ("i", "I") in fixes(r)
    s = r["suggestions"][0]
    out = br.handle("assist_write_apply", {"command": "assist_write_apply", "text": "i agree",
                                           "accepted": [{**{k: s[k] for k in ("start", "end", "original")},
                                                         "replacement": "I"}]})
    assert out["text"] == "I agree"
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_check", {"command": "assist_write_check", "text": "x", "extra": 1})
    assert e.value.code == "COMMAND_SCHEMA"
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x", "op": "proofread"})
    assert e.value.code == "BRAIN_UNAVAILABLE"


def test_bridge_brain_job_reports_by_status_and_event_and_a_user_turn_cancels_it():
    events = []
    brain = SlowBrain({"status": "ok", "message": "", "text": "The files were sent."})
    B, br = _bridge(brain, events=events)
    wid = br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "The files was sent.",
                                           "op": "proofread"})["write_id"]
    assert br.handle("assist_write_status", {"command": "assist_write_status", "write_id": wid})["state"] == "RUNNING"
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x", "op": "proofread"})
    assert e.value.code == "WRITING_BUSY"
    brain.release.set()
    br._wjob[1].join(5)
    st = br.handle("assist_write_status", {"command": "assist_write_status", "write_id": wid})
    assert st["state"] == "FINISHED" and st["status"] == "COMPLETE"
    assert [(x["original"], x["replacements"][0]) for x in st["suggestions"]] == [("was", "were")]
    assert events and events[-1]["type"] == "assist.writing" and events[-1]["turn_id"] == wid
    # a second job, stopped by the start of a user turn
    brain2 = SlowBrain({"status": "ok", "message": "", "text": "y"})
    B, br = _bridge(brain2)
    wid = br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x y", "op": "rewrite",
                                           "tone": "formal"})["write_id"]
    br.cancel_brain_work("user_turn")
    br._wjob[1].join(5)
    st = br.handle("assist_write_status", {"command": "assist_write_status", "write_id": wid})
    assert st["status"] == "CANCELLED"


def test_bridge_brain_refuses_while_a_user_turn_holds_the_brain():
    B, br = _bridge(FakeBrain({"status": "ok", "message": "", "text": "x"}), idle=False)
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x", "op": "complete"})
    assert e.value.code == "BRAIN_BUSY"
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x", "op": "rewrite", "tone": "loud"})
    assert e.value.code == "COMMAND_SCHEMA"


# ------------------------------------------------------------------------------------------- review FB1 regressions
def test_r2_01_meaning_changes_are_never_plain_corrections():
    t = "I can't approve the leave of Shri Sharma. We received nothing. Send three copies by 5 january."
    r = W.proofread(t, client=FakeBrain({"status": "ok", "message": "", "text":
                    "I can approve the leave of Shri Sharma. We received something. Send two copies by 5 june."}))
    assert r["suggestions"] and all(s["class"] == "rewrite" for s in r["suggestions"]), r["suggestions"]
    for orig, rep in [("unable", "able"), ("before", "after"), ("can't", "can"), ("nothing", "something"),
                      ("three", "two"), ("january", "june"), ("tuesday", "monday"), ("approve", "reject"),
                      ("disagree", "agree"), ("never", "always"), ("5", "6")]:
        assert W._touches_meaning(orig, rep), (orig, rep)
    # review FB2 R3-01: a spelling fix is a correction only with Windows' agreement (the spelling map)
    spelling = {"recieve": {"receive"}, "committe": {"committee"}}
    for orig, rep in [("recieve", "receive"), ("committe", "committee"), ("was", "were"), ("a", "an"),
                      ("tuesday", "Tuesday"), (" ,", ","), ("the the", "the")]:
        assert not W._touches_meaning(orig, rep, spelling=spelling), (orig, rep)
    assert W._touches_meaning("recieve", "receive", spelling=None)
    # a contraction is one token: removing "n't" is not a lone "'t" edit
    d = W._diff("I can't go.", "I can go.")
    assert [(s["original"], s["class"]) for s in d] == [("can't", "rewrite")]


def test_r2_01_a_clean_grammar_answer_still_offers_corrections():
    r = W.proofread("The files was sent to the the office.",
                    client=FakeBrain({"status": "ok", "message": "", "text": "The files were sent to the office."}))
    assert r["flags"] == [] and r["suggestions"] and all(s["class"] == "correction" for s in r["suggestions"])


def test_r2_02_enumerations_and_dotted_abbreviations_are_not_sentence_ends():
    for t in ["As per clause (i) and (ii) of the order.", "Issued vide O.M. dated 3.10.2026.",
              "Please refer to D.O. letter of the Secretary.", "All B.Tech. students may apply.",
              "He is a M.Sc. graduate.", "See sub-para i) above."]:
        got = [(s["original"], s["replacements"][0]) for s in rules(t)["suggestions"]]
        assert not any(o in ("i", "d", "l", "s", "g") for o, _ in got), (t, got)


def test_r2_03_spelling_guesses_are_marked_and_sure_fixes_are_not():
    errs = [{"start": 0, "length": 12, "word": "mukhyamantri", "action": 1, "replacement": "", "suggestions": ["mahamari"]},
            {"start": 13, "length": 7, "word": "recieve", "action": 2, "replacement": "receive", "suggestions": []},
            {"start": 21, "length": 7, "word": "tuesday", "action": 1, "replacement": "", "suggestions": ["Tuesday"]}]
    r = W.check("mukhyamantri recieve tuesday", spell=FakeSpell(errs))
    conf = {s["original"]: s["confidence"] for s in r["suggestions"]}
    assert conf == {"mukhyamantri": "guess", "recieve": "sure", "tuesday": "sure"}


def test_r2_04_check_on_a_command_loop_never_waits_for_a_worker_start_and_is_linear():
    started = []

    class Cold(W.SpellWorker):
        def prewarm(self, lang=W.DEFAULT_LANG):
            started.append(lang)

    sp = Cold()
    sp.unavailable = None
    t0 = time.perf_counter()
    r = W.check("i went", spell=sp, wait=False)
    assert (time.perf_counter() - t0) < 0.5 and r["status"]["spelling"] == "SPELL_STARTING" and started
    assert ("i", "I") in fixes(r)
    big = "word. " * 3300                      # about 20,000 characters of lower-case sentences
    t0 = time.perf_counter()
    rules(big[:W.MAX_CHECK_CHARS])
    assert (time.perf_counter() - t0) < 0.5


def test_r2_06_dismissed_words_stay_dismissed_after_earlier_edits():
    assert W.check("Yes, i agree.", spell=NoSpell(), ignore=["i"])["suggestions"] == []
    assert W.check("Yes, i agree.", spell=NoSpell())["suggestions"]


def test_r2_07_brain_must_be_loopback_and_one_assist_brain_job_at_a_time():
    with pytest.raises(W.WritingError) as e:
        W.proofread("abc def.", client=FakeBrain({"status": "ok", "message": "", "text": "x"},
                                                  base_url="https://api.example.com"))
    assert e.value.code == "BRAIN_ENDPOINT_NOT_LOOPBACK"
    B, br = _bridge(FakeBrain({"status": "ok", "message": "", "text": "x"}, base_url="http://10.0.0.5:8080"))
    with pytest.raises(B.Refused) as e:
        br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x y", "op": "proofread"})
    assert e.value.code == "BRAIN_ENDPOINT_NOT_LOOPBACK"
    brain = SlowBrain({"status": "ok", "message": "", "text": "y"})
    brain.base_url = "http://127.0.0.1:18080"
    B, br = _bridge(brain)
    br.handle("assist_write_brain", {"command": "assist_write_brain", "text": "x y", "op": "proofread"})
    assert br.writing
    with pytest.raises(B.Refused) as e:
        br.handle("assist_ask", {"command": "assist_ask", "question": "what is this?", "use_screenshot": False})
    assert e.value.code in ("WRITING_BUSY", "ACCESS_NOT_GRANTED", "NOT_GRANTED")
    br.cancel_brain_work("user_turn")
    br._wjob[1].join(5)


# ------------------------------------------------------------------------------------------- review FB2 regressions
@pytest.mark.parametrize("orig,edited", [
    ("as per clause (ii) of rule 4", "as per clause (iii) of rule 4"),
    ("Section 5(a) applies.", "Section 5(an) applies."),
    ("The leave of Mrs Gupta is sanctioned.", "The leave of Mr Gupta is sanctioned."),
    ("forward to mehta for comments", "forward to mehra for comments"),
    ("Transfer the file from Delhi to Mumbai.", "Transfer the file to Delhi from Mumbai."),
    ("Payment is due on 5 June.", "Payment is due by 5 June."),
    ("please confirm the date", "please conform the date"),
    ("Report weekly.", "Report weakly."),
    ("Permission is granted.", "Permission is grantee."),
    ("The officer is suspended.", "The officer was suspended."),
    ("the officer was present", "the officers were present"),
])
def test_r3_01_reference_name_direction_tense_and_number_changes_are_rewrites(orig, edited):
    r = W.proofread(orig, client=FakeBrain({"status": "ok", "message": "", "text": edited}))
    assert r["suggestions"], (orig, edited)
    assert all(s["class"] == "rewrite" for s in r["suggestions"]), r["suggestions"]


def test_r3_01_safe_changes_stay_corrections_with_windows_agreement(monkeypatch):
    spell = FakeSpell([{"start": 2, "length": 7, "word": "recieve", "action": 2, "replacement": "receive",
                        "suggestions": []}])
    monkeypatch.setattr(W, "default_spell", lambda: spell)
    r = W.proofread("I recieve the the files which was sent.", client=FakeBrain(
        {"status": "ok", "message": "", "text": "I receive the files which were sent."}))
    assert r["suggestions"] and all(s["class"] == "correction" for s in r["suggestions"]), r["suggestions"]


@pytest.mark.parametrize("t", ["No. 12/3/2024-Estt. dated 5.6.2024.", "sub-clause i, ii and iii apply.",
                               "see item i above.", "Annexure A is attached. Annexure a is not.",
                               "As per para i of the order.", "File No. 4/2026-Admn. dated today."])
def test_r3_02_more_administrative_references_are_left_alone(t):
    got = [(s["original"], s["replacements"][0]) for s in rules(t)["suggestions"]]
    assert not any(o in ("d", "i", "a") for o, _ in got), (t, got)
