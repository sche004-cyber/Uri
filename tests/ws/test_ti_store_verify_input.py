"""Draft versions (TI-AC2/3), deterministic verification (TI-AC4) and the input contract (TI-AC6)."""
import pytest

from uri_operational_intelligence import draft_store as DS
from uri_operational_intelligence import text_input as TI
from uri_operational_intelligence import text_verify as V


def _draft(texts=("To the Warden", "Subject: Students", "Respected Sir,", "Para one.", "Para two.", "Yours faithfully,")):
    d = DS.Draft(session_id="s", doc_type="letter", tone="formal", source={"source": "typed"}, original_text="orig")
    roles = ["recipient", "subject", "salutation", "body", "body", "closing"]
    blocks = [DS.Block(d.new_id(), r, t) for r, t in zip(roles, texts)]
    d.push(blocks=blocks, facts=[], exclusions=[], missing=[], op="created", instruction="i1", summary="v1",
           changed=[b.id for b in blocks], removed=[], flags=[])
    return d


# ---- store --------------------------------------------------------------------------------------------------
def test_edits_keep_untouched_blocks_byte_identical():
    d = _draft()
    cur = d.current
    blocks, applied, dropped = DS.apply_edits(d, cur.blocks, [{"op": "replace", "block_id": "b4", "text": "Shorter."}])
    assert [b.text for b in blocks] == ["To the Warden", "Subject: Students", "Respected Sir,", "Shorter.", "Para two.",
                                        "Yours faithfully,"]
    assert all(blocks[i] is cur.blocks[i] for i in (0, 1, 2, 4, 5))
    assert DS.diff_ids(cur.blocks, blocks) == (["b4"], [])


def test_edits_outside_target_are_dropped():
    d = _draft()
    edits = [{"op": "replace", "block_id": "b4", "text": "A."}, {"op": "replace", "block_id": "b5", "text": "B."},
             {"op": "delete", "block_id": "b2"}, {"op": "replace", "block_id": "b99", "text": "x"}]
    blocks, applied, dropped = DS.apply_edits(d, d.current.blocks, edits, allowed_ids={"b4"})
    assert [b.text for b in blocks][3:5] == ["A.", "Para two."] and blocks[1].text == "Subject: Students"
    assert len(applied) == 1 and {x["reason"] for x in dropped} == {"OUTSIDE_TARGET", "UNKNOWN_BLOCK_OR_OP"}


def test_insert_delete_and_new_ids():
    d = _draft()
    blocks, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "insert_after", "block_id": "b5", "role": "body",
                                                         "text": "Para three."}, {"op": "delete", "block_id": "b4"}])
    assert [b.text for b in blocks] == ["To the Warden", "Subject: Students", "Respected Sir,", "Para two.",
                                        "Para three.", "Yours faithfully,"]
    assert blocks[4].id == "b7"


def test_undo_redo_and_truncation_keep_original():
    d = _draft()
    v1 = d.current
    for i in (2, 3):
        b, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "replace", "block_id": "b4", "text": "v%d" % i}])
        d.push(blocks=b, facts=[], exclusions=[], missing=[], op="revised", instruction="i%d" % i, summary="v%d" % i,
               changed=["b4"], removed=[], flags=[])
    assert d.current.n == 3 and d.can_undo and not d.can_redo
    assert d.undo().n == 2 and d.can_redo
    assert d.redo().n == 3
    d.undo()
    b, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "replace", "block_id": "b5", "text": "branch"}])
    d.push(blocks=b, facts=[], exclusions=[], missing=[], op="revised", instruction="i4", summary="v4",
           changed=["b5"], removed=[], flags=[])
    assert [v.n for v in d.versions] == [1, 2, 4] and not d.can_redo
    assert d.versions[0] is v1 and d.original_text == "orig"
    snap = d.to_dict()
    assert snap["first"]["text"] == v1.text() and snap["previous"]["n"] == 2 and snap["position"] == 3
    r = d.restore(1)
    assert r.op == "restored" and r.text() == v1.text() and r.n == 5 and len(d.versions) == 4
    with pytest.raises(DS.DraftError):
        DS.Draft(session_id="s", doc_type="x", tone="", source={}, original_text="").undo()


def test_version_cap_keeps_first():
    d = _draft()
    for i in range(DS.MAX_VERSIONS + 5):
        b, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "replace", "block_id": "b4", "text": "n%d" % i}])
        d.push(blocks=b, facts=[], exclusions=[], missing=[], op="revised", instruction="x", summary="", changed=["b4"],
               removed=[], flags=[])
    assert len(d.versions) == DS.MAX_VERSIONS and d.versions[0].n == 1 and d.current.text().count("n%d" % (DS.MAX_VERSIONS + 4))


# ---- verification ---------------------------------------------------------------------------------------------
def test_numbers_words_and_digits_are_equal():
    assert V.canonical_numbers("seven students on the 6th, twenty-five rupees") >= {7, 6, 25}
    assert V._value_present("seven", "7 students") and V._value_present("7", "Seven students")
    assert V._value_present("the 6th", "on 6th October") and not V._value_present("five", "seven students")


def test_superseded_value_and_unsourced_fact_flags():
    facts = [{"key": "students", "value": "seven", "superseded": ["five"]},
             {"key": "warden", "value": "Mr. Rao", "superseded": []}]
    src = "letter about five students, sorry seven students"
    flags = V.check_facts(facts, "Five students left the hostel.", src)
    codes = [f["code"] for f in flags]
    assert "SUPERSEDED_VALUE_PRESENT" in codes and "FACT_MISSING" in codes and "FACT_UNSOURCED" in codes
    assert V.check_facts(facts[:1], "Seven students left.", src) == []


def test_exclusions_and_correction_cues():
    assert V.check_exclusions(["Rahul"], "The student Rahul left.")[0]["code"] == "EXCLUDED_PHRASE_PRESENT"
    assert V.check_exclusions(["Rahul"], "A student left.") == []
    cues = TI.correction_cues("five students, sorry seven, no wait, on the 6th")
    assert cues and V.check_correction_accounted(cues, [{"key": "k", "value": "v", "superseded": []}], None)
    assert V.check_correction_accounted(cues, [{"key": "k", "value": "v", "superseded": ["x"]}], None) == []


def test_meaning_preserved_for_grammar_only():
    orig = "me and Ramesh goes to Pune on 6 March with 3 bags"
    assert V.check_meaning_preserved(orig, "Ramesh and I go to Pune on 6 March with 3 bags.") == []
    flags = V.check_meaning_preserved(orig, "Ramesh and I go to Mumbai on 7 March with three bags.")
    assert flags[0]["code"] == "MEANING_CHANGED" and "pune" in flags[0]["detail"] and "6" in flags[0]["detail"]


def test_new_detail_ignores_placeholders_and_known_words():
    known = "draft a letter to the warden about seven students who left on Monday"
    assert V.check_new_details("Dear [Warden Name], seven students left on Monday. Signed, [Your Name]", known) == []
    f = V.check_new_details("Seven students left on Monday, 6 October, from Room 204, said Mr. Sharma.", known)
    assert f and all(x in f[0]["detail"] for x in ("6", "204", "october", "sharma"))


# ---- input contract --------------------------------------------------------------------------------------------
def _tx(raw, **kw):
    t = {"raw": raw, "engine": "simulated", "simulated": True}
    t.update(kw)
    return {"schema": TI.SCHEMA, "source": "transcript", "transcript": t}


def test_input_contract_valid():
    assert TI.parse(None, "x") is TI.TYPED
    assert TI.parse({"schema": TI.SCHEMA, "source": "typed"}, "x") is TI.TYPED
    i = TI.parse(_tx("um write a letter", language="en-IN", uncertain=["letter"]), "um write a letter")
    assert i.is_transcript and i.simulated and i.raw == "um write a letter" and i.uncertain == ("letter",)
    real = TI.parse(_tx("hello there", engine="faster-whisper-large-v3-turbo", simulated=False), "hello there")
    assert not real.simulated and real.to_dict()["engine"].startswith("faster-whisper")


@pytest.mark.parametrize("env,text,code", [
    ("x", "x", "INPUT_NOT_OBJECT"),
    ({"schema": "v0", "source": "typed"}, "x", "INPUT_SCHEMA"),
    ({"schema": TI.SCHEMA, "source": "voice"}, "x", "INPUT_SOURCE"),
    ({"schema": TI.SCHEMA, "source": "typed", "transcript": {}}, "x", "INPUT_KEYS"),
    (_tx("a b c"), "a b c d", "TRANSCRIPT_TEXT_MISMATCH"),
    (_tx("a b c", engine="whisper"), "a b c", "TRANSCRIPT_ENGINE"),                  # simulated must say so
    (_tx("a b c", engine="simulated", simulated=False), "a b c", "TRANSCRIPT_ENGINE"),  # a real one must name itself
    (_tx("a b c", simulated="yes"), "a b c", "TRANSCRIPT_SIMULATED"),
    (_tx("a b c", uncertain=["zzz"]), "a b c", "TRANSCRIPT_UNCERTAIN"),
    (_tx("a b c", language="english please"), "a b c", "TRANSCRIPT_LANGUAGE"),
    ({"schema": TI.SCHEMA, "source": "transcript", "transcript": {"raw": "a", "engine": "simulated", "simulated": True,
                                                                  "confidence": 0.9}}, "a", "TRANSCRIPT_KEYS"),
])
def test_input_contract_refusals(env, text, code):
    with pytest.raises(TI.InputRejected) as e:
        TI.parse(env, text)
    assert e.value.code == code


def test_cleanup_keeps_self_corrections_and_content():
    raw = "um URI write a a letter to the warden uh about the students leaving hostel yesterday, no wait, on the 6th"
    out = TI.clean_transcript(raw)
    assert out == "URI write a letter to the warden about the students leaving hostel yesterday, no wait, on the 6th"
    assert TI.clean_transcript("he had had enough") == "he had had enough"


# ---- L-2: input modes ---------------------------------------------------------------------------------------------
def test_l2_input_modes_and_scope_fail_closed():
    t = TI.parse({"schema": TI.SCHEMA, "source": "typed", "mode": "dictation"}, "x")
    assert (t.mode, t.scope) == ("dictation", "grammar") and t.to_dict() == {"source": "typed", "mode": "dictation",
                                                                              "scope": "grammar"}
    assert TI.parse({"schema": TI.SCHEMA, "source": "typed", "mode": "command"}, "x").mode == "command"
    assert TI.parse({"schema": TI.SCHEMA, "source": "typed", "mode": "auto"}, "x") is TI.TYPED
    tr = TI.parse({"schema": TI.SCHEMA, "source": "transcript", "mode": "dictation", "scope": "rewrite",
                   "transcript": {"raw": "um hi", "engine": "simulated", "simulated": True}}, "um hi")
    assert tr.is_transcript and tr.scope == "rewrite" and tr.to_dict()["mode"] == "dictation"
    for env, code in [({"mode": "execute"}, "INPUT_MODE"), ({"mode": "command", "scope": "grammar"}, "INPUT_SCOPE"),
                      ({"mode": "dictation", "scope": "verbatim"}, "INPUT_SCOPE"), ({"scope": "grammar"}, "INPUT_SCOPE"),
                      ({"mode": "dictation", "extra": 1}, "INPUT_KEYS")]:
        with pytest.raises(TI.InputRejected) as e:
            TI.parse({"schema": TI.SCHEMA, "source": "typed", **env}, "x")
        assert e.value.code == code
    assert TI.parse(None, "x").mode == "auto"                       # no envelope: unchanged behaviour


# ---- L-4: value reassignment --------------------------------------------------------------------------------------
@pytest.mark.parametrize("ref,rev", [
    ("Ravi paid Rs 500 and Sita paid Rs 700.", "Ravi paid Rs 700 and Sita paid Rs 500."),          # amounts / students
    ("Monday: 7; Tuesday: 8", "Monday: 8; Tuesday: 7"),                                           # quantities / entries
    ("The exam is on 5 March and the meeting is on 9 March.",
     "The meeting is on 5 March and the exam is on 9 March."),                                     # dates / events
    ("Roll no 12 Anil, roll no 15 Sunil.", "Anil has roll number 15 and Sunil has roll number 12."),  # roll numbers
    ("The bus leaves at 18:00 and returns at 21:00.", "The bus returns at 18:00 and leaves at 21:00."),
])
def test_l4_swapped_associations_are_flagged_for_review(ref, rev):
    f = V.check_reassignment(ref, rev)
    assert len(f) == 1 and f[0]["code"] == "VALUE_REASSIGNED" and f[0]["severity"] == "review"
    assert "Changes and Original" in f[0]["detail"]


@pytest.mark.parametrize("ref,rev", [
    ("Ravi paid Rs 500 and Sita paid Rs 700.", "Kindly note that Ravi paid Rs 500, while Sita paid Rs 700."),
    ("Ravi paid Rs 500 and Sita paid Rs 700.", "Ravi and Sita paid Rs 500 and Rs 700 respectively."),   # restructured
    ("Seven students left on Monday.", "Seven students left the hostel on Monday without permission."),
    ("Class A has 30 students and class B has 25 students.", "Class A has 30 students, and class B has 25."),
    ("Ravi paid Rs 500 and Sita paid Rs 700.", "Ravi paid Rs 550 and Sita paid Rs 700."),           # a changed value:
    ("", "Ravi paid Rs 500."),                                                                   # other checks' job
])
def test_l4_legitimate_rewrites_are_not_flagged(ref, rev):
    assert V.check_reassignment(ref, rev) == []


def test_l4_intended_reassignment_stays_possible_and_is_shown_as_asked():
    f = V.check_reassignment("Ravi paid Rs 500 and Sita paid Rs 700.", "Ravi paid Rs 700 and Sita paid Rs 500.",
                             instruction="Actually Ravi paid 700 and Sita paid 500.")
    assert [(x["code"], x["severity"]) for x in f] == [("VALUE_REASSIGNED_AS_ASKED", "info")]
