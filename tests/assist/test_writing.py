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
    def check(self, text, lang):
        raise W.WritingError("SPELL_UNAVAILABLE")


class FakeSpell:
    def __init__(self, errors, lang="en-IN"):
        self.errors, self.lang, self.calls = errors, lang, 0

    def check(self, text, lang):
        self.calls += 1
        return {"ok": True, "lang": self.lang, "errors": self.errors}


class FakeBrain:
    def __init__(self, answer, status=BC.COMPLETE):
        self.answer, self.status, self.bodies = answer, status, []

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
