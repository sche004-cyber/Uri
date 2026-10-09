"""Regressions for findings from the first live Runtime v1 matrix (LQ-1..LQ-4, 2026-10-09 07:13)."""
from uri_operational_intelligence import text_verify as V


def test_lq1_number_word_compared_by_value():
    assert not V._phrase_present("two", "All forty-two rooms; three rooms had damaged windows.")
    assert V.check_facts([{"key": "rooms", "value": "three", "superseded": ["two"]}],
                         "All forty-two rooms; three rooms had damaged windows.", "two rooms, sorry, three rooms") == []
    assert V._phrase_present("five", "Five students left.")


def test_lq2_three_word_value_survives_one_reworded_word():
    assert V._value_present("needs pest control", "the storage area requires pest control")
    assert not V._value_present("needs pest control", "the storage area is clean")


def test_lq3_title_case_subject_is_not_a_name():
    assert V.check_new_details("Subject: Unauthorized Absence of Students from Hostel\n\nSeven students left.",
                               "seven students left the hostel") == []
    assert V.check_new_details("Seven students left, said Mr. Sharma.", "seven students left")


def test_lq4_dont_say_x_verifies_the_replaced_phrase():
    v, u = V.verified_superseded("Actually, don't say without permission. Say they left without recording.",
                                 ["left the hostel without permission"])
    assert v == ["left the hostel without permission"] and u == []


def test_lq7_multi_paragraph_body_becomes_blocks():
    from uri_operational_intelligence import draft_store as DS
    d = DS.Draft(session_id="s", doc_type="letter", tone="", source={}, original_text="x")
    blocks = DS.blocks_from_model(d, [{"role": "salutation", "text": "Sir,"},
                                      {"role": "body", "text": "First para.\n\nSecond para."},
                                      {"role": "signature", "text": "A\nB"}])
    assert [(b.role, b.text) for b in blocks] == [("salutation", "Sir,"), ("body", "First para."),
                                                  ("body", "Second para."), ("signature", "A\nB")]
    d.push(blocks=blocks, facts=(), exclusions=(), missing=(), op="created", instruction="", summary="",
           changed=(), removed=(), flags=())
    out, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "replace", "block_id": "b3", "text": "Two.\n\nThree."}])
    assert [b.text for b in out if b.role == "body"] == ["First para.", "Two.", "Three."]
    assert [b.id for b in out][:3] == ["b1", "b2", "b3"]


def test_lq10_possessive_matches():
    assert V._value_present("warden", "To [Warden's Name], Respected Sir")


def test_lq11_escalation_is_flagged_unless_user_said_it():
    f = V.check_escalation("I request you to take disciplinary action.", "seven students left without permission")
    assert f and f[0]["code"] == "ESCALATION_ADDED" and "disciplinary" in f[0]["detail"]
    assert V.check_escalation("Please take disciplinary action.", "ask for disciplinary action") == []


def test_lq13_ambiguous_date_change_asks_without_model(tmp_path):
    import json
    from tests.oi.fake_llama import FakeLlama
    from tests.oi.test_oi_orchestrator import FakeCore
    from tests.ws.test_ti_desk_bridge import CREATE, turn
    from tests.ws.test_ws_worker_bridge import make
    with FakeLlama() as fake:
        b, frames, _ = make(fake, tmp_path, FakeCore())
        two = dict(CREATE, blocks=[{"role": "body", "text": "Pay by the 5th; late fee from the 15th."}], facts=[])
        fake.scripts.append({"json": json.dumps(two)})
        turn(b, "Write a notice that the hostel fee must be paid by the 5th, and the late fee applies from the 15th.")
        n = len(fake.requests)
        turn(b, "Change the date to the 10th.")
        assert len(fake.requests) == n
        assert frames.data("draft.clarify")[-1]["question"] == "Which date should change: the 5th or the 15th?"
