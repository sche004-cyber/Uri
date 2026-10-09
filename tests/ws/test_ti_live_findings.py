"""Regressions for findings from the first live Runtime v1 matrix (LQ-1..LQ-4, 2026-10-09 07:13)."""
from uri_operational_intelligence import text_verify as V


def test_lq1_number_word_compared_by_value():
    assert not V._phrase_present("two", "All forty-two rooms; three rooms had damaged windows.")
    assert V.check_facts([{"key": "rooms", "value": "three", "superseded": ["two"]}],
                         "All forty-two rooms; three rooms had damaged windows.", "two rooms, sorry, three rooms") == []
    assert V._phrase_present("five", "Five students left.")


def test_lq2_reworded_value_is_a_visible_review_not_an_error():
    # Revised after Codex TI r12: a partial match is never "present"; it is reported as FACT_REWORDED (review).
    f = V.check_facts([{"key": "storage", "value": "needs pest control", "superseded": []}],
                      "the storage area requires pest control", "storage needs pest control")
    assert [(x["code"], x["severity"]) for x in f] == [("FACT_REWORDED", "review")]
    f = V.check_facts([{"key": "storage", "value": "needs pest control", "superseded": []}],
                      "the storage area is clean", "storage needs pest control")
    assert [(x["code"], x["severity"]) for x in f] == [("FACT_MISSING", "error")]


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


def test_lq15_to_lq20_precision():
    from uri_operational_intelligence import text_input as TI
    assert TI.correction_cues("paid on Tuesday, no, Wednesday")                                    # LQ-15
    assert V.verified_superseded("paid on Tuesday, no, Wednesday", ["Tuesday"])[0] == ["Tuesday"]
    assert V._value_present("tue", "on Tuesday") and V._value_present("10am-2pm", "from 10:00 AM to 2:00 PM")  # LQ-16
    assert V.check_new_details("from 6:00 PM to 9:00 PM", "from 6 pm to 9 pm") == []
    assert V._value_present("about forty students", "approximately forty students")             # LQ-17
    assert V.check_user_details("Mention that Kavya is the coordinator.", "Kavya is the coordinator.") == []  # LQ-18
    assert V.check_escalation("Water supply will be suspended.", "water supply off") == []        # LQ-19
    assert V.check_user_details("kal se teen din ki chutti", "three days of leave from tomorrow") == []  # LQ-20


def test_lq21_correction_in_a_later_turn():
    prev = "Can we move our meeting to Monday at 3 pm?"
    assert V.verified_across_turns("No, I meant Tuesday.", prev, ["Monday"]) == ["Monday"]
    assert V.verified_across_turns("Make it shorter.", prev, ["Monday"]) == []
    assert V.check_supersession("No, I meant Tuesday.", ["Monday"], instruction="No, I meant Tuesday.",
                                previous_text=prev) == []


def test_lq23_tone_is_not_a_fact():
    from uri_operational_intelligence.draft_desk import _clean_facts
    assert _clean_facts([{"key": "tone", "value": "formal"}, {"key": "day", "value": "Monday"}]) == [
        {"key": "day", "value": "Monday", "superseded": []}]


def test_lq24_visible_correction_needs_no_review_line():
    assert V.correction_visible("Sorry, not two days, three.", "closed for two days", "closed for three days")
    assert V.correction_visible("Actually, don't say without permission. Say they left without recording.",
                                "left without permission", "left without recording")
    assert not V.correction_visible("Sorry, not two days, three.", "closed for two days", "closed for two days")


def test_lq25_list_enumerators_and_placeholders_are_not_quantities():
    text = "Seven students left.\n1. [Student Name 1]\n5. [Student Name 5]\n7. [Student Name 7]"
    assert V.canonical_numbers(text) == {7}
    assert V.check_facts([{"key": "students", "value": "seven", "superseded": ["five"]}], text,
                         "five students, sorry seven students") == []



# Codex TI round 12: precision fixes must never hide a change an earlier check reported.
def test_r12_partial_match_is_never_silent():
    f = V.check_facts([{"key": "gate", "value": "north east gate", "superseded": []}],
                      "The north west gate is closed.", "the north east gate is closed")
    assert f and f[0]["severity"] in ("review", "error")


def test_r12_clock_times_keep_minutes_and_half_of_day():
    assert V._value_present("6.00 pm", "at 6 PM") and V._value_present("6 pm", "at 6:00 p.m.")
    assert not V._value_present("6.00 pm", "at 6 am")
    assert not V._value_present("6:30 pm", "at 6 pm")


def test_r12_invented_surname_in_title_line_is_visible():
    f = V.check_new_details("Subject: Meeting With Kavya Sharma\n\nKavya will attend.", "a meeting with Kavya")
    assert f and "sharma" in f[0]["detail"]
    assert V.check_new_details("Subject: Unauthorized Absence of Students from Hostel", "students left the hostel") == []


def test_r12_kal_needs_tense():
    assert V.check_user_details("kal meeting hui thi", "The meeting was yesterday.") == []
    assert V.check_user_details("kal meeting hui thi", "The meeting is tomorrow.")          # wrong day is visible
    assert V.check_user_details("kal se teen din ki chutti chahiye", "Leave from tomorrow for three days.") == []
    assert V.check_user_details("kal meeting", "The meeting is tomorrow.")                   # ambiguous: reported


def test_r12_swap_replacement_is_required():
    assert V.swap_pairs("Actually, don't say wing; say east") == [("wing", "east")]
    assert not V.correction_visible("Actually, don't say wing; say east", "The north wing gate.", "The north gate.")
    assert V.correction_visible("Actually, don't say wing; say east", "The north wing gate.", "The north east gate.")


def test_r12_swap_in_desk_makes_new_wording_a_fact(tmp_path):
    import json
    from tests.oi.fake_llama import FakeLlama
    from tests.oi.test_oi_orchestrator import FakeCore
    from tests.ws.test_ti_desk_bridge import CREATE, last_draft, turn
    from tests.ws.test_ws_worker_bridge import make
    with FakeLlama() as fake:
        b, frames, _ = make(fake, tmp_path, FakeCore())
        first = dict(CREATE, facts=[{"key": "place", "value": "north wing gate", "superseded": []}],
                     blocks=[{"role": "body", "text": "The north wing gate is closed."}])
        edit = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
                "edits": [{"op": "replace", "block_id": "b1", "role": "body", "text": "The north gate is closed."}],
                "summary": "Changed."}
        fake.scripts += [{"json": json.dumps(first)}, {"json": json.dumps(edit)}]
        turn(b, "Write a notice that the north wing gate is closed")
        turn(b, "Actually, don't say wing; say east")
        codes = {f["code"] for f in last_draft(frames)["current"]["flags"]}
        assert "FACT_MISSING" in codes or "FACT_REWORDED" in codes


def test_r12_inserted_paragraphs_are_separate_blocks():
    from uri_operational_intelligence import draft_store as DS
    d = DS.Draft(session_id="s", doc_type="letter", tone="", source={}, original_text="x")
    blocks = DS.blocks_from_model(d, [{"role": "body", "text": "First."}])
    d.push(blocks=blocks, facts=(), exclusions=(), missing=(), op="created", instruction="", summary="",
           changed=(), removed=(), flags=())
    out, _, _ = DS.apply_edits(d, d.current.blocks, [{"op": "insert_after", "block_id": "b1", "role": "body",
                                                      "text": "Second.\n\nThird."}])
    assert [b.text for b in out] == ["First.", "Second.", "Third."]



# Codex TI round 13.
def test_r13_currency_prefixed_amounts_and_clock_changes_are_numbers():
    assert V.check_meaning_preserved("Pay Rs5400 today", "Pay Rs5500 today.")
    assert V.check_meaning_preserved("Meet at 6 pm", "Meet at 7 pm.")
    assert V.check_meaning_preserved("Meet at 6 pm", "Meet at 6:00 PM.") == []
    assert V._value_present("6 pm", "at 18:00")


def test_r13_capitalised_run_next_to_a_known_name_is_kept():
    f = V.check_new_details("Subject: Meeting With Kavya Devi Sharma", "a meeting with Kavya")
    assert f and "sharma" in f[0]["detail"] and "devi" in f[0]["detail"]


def test_r13_english_the_is_not_hindi_past():
    assert V.check_user_details("kal meeting with the principal", "The meeting with the principal was yesterday.")


def test_r13_short_and_bounded_swap_values():
    assert V.swap_pairs("don't say A; say B") == [("A", "B")]
    assert V.swap_pairs("Don't say wing, say east and keep the rest unchanged") == [("wing", "east")]
