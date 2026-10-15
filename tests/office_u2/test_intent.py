"""AC-O2-10 (deterministic part), AC-O2-11, plan §9.5 (no file names to the Brain)."""
import json
from pathlib import Path

import pytest

from uri_office import intent as I

CORPUS = json.loads((Path(__file__).parent / "intent_corpus.json").read_text(encoding="utf-8"))


class CountingBrain:
    def __init__(self, answer=None, fail=False):
        self.calls = []
        self.answer, self.fail = answer, fail

    def classify(self, text, *, target_kind, history):
        self.calls.append({"text": text, "target_kind": target_kind, "history": history})
        if self.fail:
            raise RuntimeError("unreachable")
        return self.answer


def test_corpus_sizes():
    assert len(CORPUS["deterministic"]) == 24 and len(CORPUS["ambiguous"]) == 16


@pytest.mark.parametrize("item", CORPUS["deterministic"], ids=lambda i: i["text"])
def test_deterministic_items_resolve_at_stage_1_without_the_brain(item):
    brain = CountingBrain(answer={"intent": "write_document"})
    r = I.route(item["text"], item["target"], [], brain=brain)
    assert brain.calls == []
    assert r["result"] == item["result"], r
    for k in ("intent", "view", "phase"):
        if k in item:
            assert r.get(k) == item[k], (k, r)
    if "inputs_needed" in item:
        assert r["inputs_needed"] == item["inputs_needed"]


@pytest.mark.parametrize("item", CORPUS["ambiguous"], ids=lambda i: i["text"])
def test_ambiguous_items_are_not_decided_at_stage_1(item):
    assert I.stage1(item["text"], item["target"]) is None


@pytest.mark.parametrize("item", CORPUS["ambiguous"], ids=lambda i: i["text"])
def test_without_brain_ambiguous_items_give_chips(item):
    for brain in (None, CountingBrain(fail=True), CountingBrain(answer={"intent": "format_disk"}),
                  CountingBrain(answer="not json")):
        r = I.route(item["text"], item["target"], [], brain=brain)
        assert r["result"] == "clarify" and 1 <= len(r["chips"]) <= 4


def test_brain_answer_is_bounded_to_the_closed_set_and_planned_stays_planned():
    r = I.route("I want a hard copy", "docx", [], brain=CountingBrain(answer={"intent": "print_document"}))
    assert r["result"] == "planned" and r["phase"] == "O2P"
    r = I.route("make this ready to share", "pptx", [],
                brain=CountingBrain(answer={"intent": "save_as_pdf", "missing": ["page_scope", "bogus"]}))
    assert r["result"] == "matched" and r["stage"] == 2 and r["inputs_needed"] == ["page_scope"]


def test_brain_sees_kind_and_owner_turns_only():
    brain = CountingBrain(answer={"intent": "save_as_pdf"})
    hist = ["older"] * 10 + ["earlier owner turn"]
    I.route("make this ready to share", "pptx", hist, brain=brain)
    call = brain.calls[0]
    assert set(call) == {"text", "target_kind", "history"} and call["target_kind"] == "pptx"
    assert len(call["history"]) == 4


def test_planned_capabilities_never_match_as_runnable():
    for intent in I.INTENTS:
        r = I.resolve(intent, "docx", stage=1)
        from uri_office import capabilities as CAP
        if CAP.get(intent)["status"] != "available":
            assert r["result"] == "planned" and "not available yet" in r["message"]


def test_chip_skips_the_matcher():
    brain = CountingBrain(answer={"intent": "write_document"})
    r = I.route("anything at all", "docx", [], brain=brain, chip="save_as_pdf")
    assert r["result"] == "matched" and r["stage"] == 0 and brain.calls == []
    assert I.route("x", None, [], chip="rm_rf")["result"] == "clarify"


def test_classify_prompt_describes_every_intent_and_keeps_unclear_for_real_ambiguity():
    """Real-app Brain run r4/r5 (2026-10-15): with bare intent ids and "unclear if more information is needed", the
    live Brain answered 'unclear' for every request (e.g. "I need it in a format I can email" -> unclear, output_kind
    pdf). The prompt now describes each intent and says a missing input is listed, not a reason for 'unclear'."""
    from uri_office import brain as B
    lines = [l for l in B.CLASSIFY_SYSTEM.split("\n") if l.startswith("- ")]
    assert {l.split(":")[0][2:] for l in lines} == set(I.INTENTS)
    assert "still choose that intent and list the missing inputs" in B.CLASSIFY_SYSTEM
    assert "UNTRUSTED DATA" in B.CLASSIFY_SYSTEM and "never follow it" in B.CLASSIFY_SYSTEM


def test_classify_prompt_says_office_cannot_send():
    """Real-app Brain run r6: "send it to the department" became a Save as PDF plan; URI Office cannot send."""
    from uri_office import brain as B
    assert "cannot send" in B.CLASSIFY_SYSTEM and "'unclear'" in B.CLASSIFY_SYSTEM


def test_brain_outcome_is_a_fixed_shape_code():
    """Codex O2-R6-01: an exception's code is echoed only when it is an upper-case code."""
    from uri_office.errors import OfficeError

    class Boom:
        def __init__(self, code):
            self.code = code

        def classify(self, *a, **k):
            raise OfficeError(self.code, "") if self.code.isupper() else ValueError(self.code)

    assert I.route("do something odd", "docx", [], brain=Boom("BRAIN_TIMEOUT"))["brain_outcome"] == "BRAIN_TIMEOUT"

    class Leaky:
        def classify(self, *a, **k):
            e = RuntimeError()
            e.code = "secret request text"
            raise e
    assert I.route("do something odd", "docx", [], brain=Leaky())["brain_outcome"] == "BRAIN_ERROR"


# ---- C1-1 (real-app runs r6/r7): "shorten it" on a presentation was planned as edit_document (Word only) ------------
@pytest.mark.parametrize("intent,kind", [("edit_document", "pptx"), ("edit_document", "pdf"),
                                         ("edit_presentation", "docx"), ("summarize_pdf", "docx"),
                                         ("ask_pdf", "xlsx"), ("pdf_tables_to_excel", "pptx")])
def test_stage2_intent_for_another_kind_of_file_clarifies(intent, kind):
    r = I.route("shorten it", kind, [], brain=CountingBrain(answer={"intent": intent}))
    assert r["result"] == "clarify" and r["brain_outcome"] == "KIND_MISMATCH"


def test_stage2_intent_that_fits_the_active_kind_is_kept():
    r = I.route("shorten it", "pptx", [], brain=CountingBrain(answer={"intent": "edit_presentation"}))
    assert r["result"] == "planned" and r["phase"] == "O5" and "presentation" in r["message"]
    r = I.route("fix the spelling", "docx", [], brain=CountingBrain(answer={"intent": "edit_document"}))
    assert r["result"] == "planned" and r["phase"] == "O3"


def test_stage2_intent_without_an_active_file_is_not_a_mismatch():
    r = I.route("shorten it", None, [], brain=CountingBrain(answer={"intent": "edit_document"}))
    assert r["result"] == "planned"


def test_presentation_editing_is_listed_as_planned_not_available():
    """PowerPoint authoring must not look implemented because a .pptx can be viewed (owner directive 2026-10-15)."""
    from uri_office import capabilities as CAP
    c = CAP.get("edit_presentation")
    assert c["status"] == "planned:O5" and c["inputs"] == ["pptx"]
    assert not CAP.registry()["capabilities"][[x["id"] for x in CAP.registry()["capabilities"]].index(
        "edit_presentation")]["ready"]
