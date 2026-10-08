"""OI reasoning task suite: 30 tasks, 7 categories, deterministic code-checked scoring.

Each task: id, category, prompt, schema (JSON answer), check(answer) -> 0.0..1.0. Answers are requested as JSON and
constrained by the server grammar at both tiers, so scoring measures reasoning, not formatting. Written for this
milestone (2026-10-08); not used to tune any prompt in uri_operational_intelligence.
"""
from __future__ import annotations


def _s(props, req=None):
    return {"type": "object", "properties": props, "required": req or list(props), "additionalProperties": False}


STR, INT, BOOL, NUM = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "number"}
LIST = {"type": "array", "items": {"type": "string"}, "maxItems": 10}


def enum(*v):
    return {"type": "string", "enum": list(v)}


def norm(x):
    return " ".join(str(x).lower().replace("-", " ").replace("_", " ").split())


CAPS = ("remember_fact, recall_memory, gmail_search, gmail_create_draft, web_search, fetch_url, drive_search, "
        "drive_upload, convert_document, read_attached_file, generate_document, fetch_drive_spreadsheet, "
        "extract_student_records, system_performance, external_harness_task")
CAP_ENUM = enum(*[c.strip() for c in CAPS.split(",")], "none")

TASKS = [
    # ---------------- planning ----------------
    {"id": "pl1_topo", "cat": "planning",
     "prompt": "Office tasks and dependencies: approve_budget needs collect_quotes; book_hall needs approve_budget; "
               "print_forms needs approve_budget; send_invites needs book_hall and print_forms. Give one valid order to do "
               "all five tasks; when two tasks are both possible, put the alphabetically earlier one first.",
     "schema": _s({"order": LIST}),
     "check": lambda a: float([norm(x) for x in a["order"]] == ["collect quotes", "approve budget", "book hall",
                                                                "print forms", "send invites"])},
    {"id": "pl2_critical_path", "cat": "planning",
     "prompt": "Project steps (duration in days): A=2, B=3 (needs A), C=4 (needs A), D=1 (needs B and C), E=2 (needs D). "
               "Steps that do not depend on each other can run in parallel. Minimum total days to finish everything?",
     "schema": _s({"days": INT}), "check": lambda a: float(a["days"] == 9)},
    {"id": "pl3_unblock", "cat": "planning",
     "prompt": "Pending items: (1) principal's signature on the fee report; (2) fee report sent to the board - needs (1); "
               "(3) hall booking - needs (1); (4) parent circular - needs (3); (5) canteen menu - needs nothing. "
               "Which single item, done first, unblocks the most other items (directly or indirectly)? Answer its number.",
     "schema": _s({"item": INT}), "check": lambda a: float(a["item"] == 1)},
    {"id": "pl4_schedule", "cat": "planning",
     "prompt": "I have three 1-hour meetings to place today between 9:00 and 13:00, no overlaps. Meeting X must end before "
               "Meeting Y starts. Meeting Z cannot be at 10:00-11:00 (room busy). Y cannot start before 11:00. What is the "
               "earliest time all three meetings can be finished? Answer as HH:MM (24h).",
     "schema": _s({"finish": STR}), "check": lambda a: float(a["finish"].strip() in ("12:00",))},
    # ---------------- multi-step decisions ----------------
    {"id": "md1_knap", "cat": "decisions",
     "prompt": "Budget Rs 10,000. Items (cost, value points): projector (6000, 9), printer (4000, 5), speakers (3000, 4), "
               "whiteboard (1000, 2). Choose items maximizing total value without exceeding the budget.",
     "schema": _s({"items": LIST, "value": INT}),
     "check": lambda a: float(sorted(norm(x) for x in a["items"]) == ["projector", "speakers", "whiteboard"]
                              and a["value"] == 15)},
    {"id": "md2_vendor", "cat": "decisions",
     "prompt": "Vendors for 200 notebooks: Alpha Rs 40/unit, delivery 7 days, rating 4.5; Beta Rs 42/unit, delivery 4 days, "
               "rating 4.1; Gamma Rs 42/unit, delivery 3 days, rating 4.6; Delta Rs 45/unit, delivery 2 days, rating 4.9. "
               "Rule: delivery must be at most 5 days; then lowest price; ties broken by higher rating. Which vendor?",
     "schema": _s({"vendor": STR}), "check": lambda a: float(norm(a["vendor"]) == "gamma")},
    {"id": "md3_leave", "cat": "decisions",
     "prompt": "Leave policy: R1 casual leave max 3 consecutive days; R2 requests must be made 2 days ahead unless medical; "
               "R3 medical leave over 2 days needs a certificate. Request: teacher asks today for medical leave starting "
               "tomorrow for 4 days and attaches a doctor's certificate. Decide and give the rule that matters most.",
     "schema": _s({"decision": enum("approve", "deny"), "rule": enum("R1", "R2", "R3", "none")}),
     "check": lambda a: 0.5 * (a["decision"] == "approve") + 0.5 * (a["rule"] == "R3")},
    {"id": "md4_room", "cat": "decisions",
     "prompt": "Need a room for 35 people with a projector. Rooms: A seats 30, projector, Rs 500; B seats 40, no projector, "
               "Rs 300; C seats 50, projector, Rs 800; D seats 36, projector, Rs 700. Cheapest room that meets the need?",
     "schema": _s({"room": enum("A", "B", "C", "D")}), "check": lambda a: float(a["room"] == "D")},
    # ---------------- ambiguity resolution ----------------
    {"id": "am1_two_candidates", "cat": "ambiguity",
     "prompt": "Conversation so far: the user attached 'Budget Q3.docx' and 'Budget Q4.docx' at the same time and has not "
               "mentioned either since. User now says: 'send the budget to Ravi'. Can URI tell which file is meant?",
     "schema": _s({"needs_clarification": BOOL, "candidates": LIST}),
     "check": lambda a: 0.5 * (a["needs_clarification"] is True) + 0.5 * (len(a["candidates"]) == 2)},
    {"id": "am2_resolved", "cat": "ambiguity",
     "prompt": "Conversation: the user attached 'Budget Q3.docx' and 'Budget Q4.docx', then said 'open the Q4 one' and "
               "discussed it for three turns. User now says: 'send it to Ravi'. Which file is meant, if it is clear?",
     "schema": _s({"needs_clarification": BOOL, "file": {"anyOf": [STR, {"type": "null"}]}}),
     "check": lambda a: float(a["needs_clarification"] is False and "q4" in norm(a["file"] or ""))},
    {"id": "am3_invalid_date", "cat": "ambiguity",
     "prompt": "Today is 8 October 2026. The user says: 'remind me about the audit on 31 November'. Should URI act "
               "directly or ask first?",
     "schema": _s({"action": enum("act", "ask_user"), "reason": STR}),
     "check": lambda a: float(a["action"] == "ask_user")},
    {"id": "am4_two_contacts", "cat": "ambiguity",
     "prompt": "Contacts: Meena Rao <meena.rao@school.in>, Meena Iyer <m.iyer@school.in>. User: 'email Meena the timetable'. "
               "List the options URI should offer, as email addresses, or none if it can proceed.",
     "schema": _s({"needs_clarification": BOOL, "options": LIST}),
     "check": lambda a: 0.5 * (a["needs_clarification"] is True)
     + 0.5 * (sorted(norm(o) for o in a["options"]) == sorted([norm("m.iyer@school.in"), norm("meena.rao@school.in")]))},
    # ---------------- tool selection ----------------
    {"id": "ts1", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'find the fee circular the "
     "accounts office mailed me last week'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "gmail_search")},
    {"id": "ts2", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'what is the weather in Pune right "
     "now?'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "web_search")},
    {"id": "ts3", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'turn the attached Word file into "
     "a PDF'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "convert_document")},
    {"id": "ts4", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'keep in mind that the inspection "
     "is on 3 November'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "remember_fact")},
    {"id": "ts5", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'tell me a short joke about "
     "teachers'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "none")},
    {"id": "ts6", "cat": "tool_selection", "prompt": "Capabilities: " + CAPS + ". Request: 'refactor the attendance app's "
     "Python code into modules and run its tests'. Which one capability fits best (or none)?",
     "schema": _s({"capability": CAP_ENUM}), "check": lambda a: float(a["capability"] == "external_harness_task")},
    # ---------------- error recovery ----------------
    {"id": "er1_auth", "cat": "error_recovery",
     "prompt": "URI tried gmail_create_draft and got: AUTH_EXPIRED (the Google sign-in expired). Best next step?",
     "schema": _s({"next": enum("retry_same", "ask_user_to_reconnect_account", "use_another_account_silently", "report_done")}),
     "check": lambda a: float(a["next"] == "ask_user_to_reconnect_account")},
    {"id": "er2_uncertain_upload", "cat": "error_recovery",
     "prompt": "drive_upload timed out after the upload request was sent; no confirmation came back, so the file may or may "
               "not be in Drive. Best next step?",
     "schema": _s({"next": enum("retry_upload_now", "check_drive_for_the_file_before_anything_else", "report_success",
                               "delete_local_file")}),
     "check": lambda a: float(a["next"] == "check_drive_for_the_file_before_anything_else")},
    {"id": "er3_quota", "cat": "error_recovery",
     "prompt": "The user chose Codex for a coding task. Midway, Codex reports its quota is exhausted. Claude Code is installed "
               "and logged in. What should URI do?",
     "schema": _s({"next": enum("switch_to_claude_code_automatically", "pause_save_progress_and_ask_user",
                               "retry_codex_in_a_loop", "cancel_and_discard")}),
     "check": lambda a: float(a["next"] == "pause_save_progress_and_ask_user")},
    {"id": "er4_verify_mismatch", "cat": "error_recovery",
     "prompt": "URI saved a memory and then read it back to verify, but the read-back text differs from what was written. "
               "How should the outcome be reported?",
     "schema": _s({"report": enum("verified", "uncertain_do_not_retry_automatically", "write_again_twice", "failed_and_deleted")}),
     "check": lambda a: float(a["report"] == "uncertain_do_not_retry_automatically")},
    # ---------------- office work ----------------
    {"id": "of1_extract", "cat": "office",
     "prompt": "Extract fields from: 'Respected Sir, I, Kavita Sharma (Maths, Class 8B), request casual leave from 12 Oct 2026 "
               "to 14 Oct 2026 due to a family function. Kindly grant. Yours, Kavita.'",
     "schema": _s({"name": STR, "from": STR, "to": STR, "days": INT, "type": enum("casual", "medical", "earned", "other")}),
     "check": lambda a: (("kavita sharma" == norm(a["name"])) + ("12" in a["from"]) + ("14" in a["to"]) + (a["days"] == 3)
                         + (a["type"] == "casual")) / 5},
    {"id": "of2_fee", "cat": "office",
     "prompt": "Hostel fee is Rs 42,000. A 10% sibling discount applies to the fee, then 5% late charge is added on the "
               "discounted amount. Final amount in rupees?",
     "schema": _s({"amount": NUM}), "check": lambda a: float(abs(a["amount"] - 39690) < 0.5)},
    {"id": "of3_marks", "cat": "office",
     "prompt": "Marks (Maths, Science, English): Asha 45,38,70; Bilal 40,40,40; Chen 39,90,85; Divya 72,65,41; Esha 55,42,39. "
               "Pass needs at least 40 in every subject. How many students passed?",
     "schema": _s({"passed": INT}), "check": lambda a: float(a["passed"] == 2)},
    {"id": "of4_workdays", "cat": "office",
     "prompt": "Count working days from Monday 2 November 2026 to Saturday 14 November 2026 inclusive. Sundays are off and "
               "Wednesday 11 November is a holiday; Saturdays are working days.",
     "schema": _s({"days": INT}), "check": lambda a: float(a["days"] == 11)},
    # ---------------- context-dependent orchestration ----------------
    {"id": "co1_typed_yes", "cat": "orchestration",
     "prompt": "URI is showing an approval card for 'remember that the server room code is 7731'. Instead of pressing "
               "Approve, the user types 'yes do it'. In URI, typed text never counts as approval. What should happen?",
     "schema": _s({"next": enum("execute_now", "keep_waiting_for_the_approval_button", "cancel_request", "ask_model")}),
     "check": lambda a: float(a["next"] == "keep_waiting_for_the_approval_button")},
    {"id": "co2_partial_grants", "cat": "orchestration",
     "prompt": "Request: 'save the draft reply and email it to the principal'. Granted capabilities: gmail_create_draft only "
               "(sending mail is not available). Which parts can URI do and which are blocked?",
     "schema": _s({"can_do": LIST, "blocked": LIST}),
     "check": lambda a: 0.5 * any("draft" in norm(x) for x in a["can_do"]) * (not any("send" in norm(x) or "email" in norm(x)
                                                                                     for x in a["can_do"] if "draft" not in norm(x)))
     + 0.5 * any(("send" in norm(x) or "email" in norm(x)) for x in a["blocked"])},
    {"id": "co3_dependent_uncertain", "cat": "orchestration",
     "prompt": "A 3-step task: step 2 (upload report) ended UNCERTAIN (it may have run). Step 3 (email the uploaded link) "
               "depends on step 2. What happens to step 3?",
     "schema": _s({"step3": enum("run_it", "skip_it_and_report_to_user", "retry_step2_then_run", "run_with_old_link")}),
     "check": lambda a: float(a["step3"] == "skip_it_and_report_to_user")},
    {"id": "co4_escalate", "cat": "orchestration",
     "prompt": "URI's local model, at its bounded reasoning tier, stopped because it reached its token budget before finishing "
               "a long optimisation problem. Policy forbids unbounded local thinking. What should URI do?",
     "schema": _s({"next": enum("retry_locally_with_unlimited_budget", "report_incomplete_and_offer_escalation",
                               "return_the_partial_answer_as_final", "silently_use_cloud_model")}),
     "check": lambda a: float(a["next"] == "report_incomplete_and_offer_escalation")},
]

assert len(TASKS) == 30 and len({t["id"] for t in TASKS}) == 30

# Held-out routing set (written after triage.py; never used to tune it): (text, needs_core)
ROUTING = [
    ("hey uri", False), ("good evening!", False), ("What does CBSE stand for?", False),
    ("Explain photosynthesis to a class 6 student in 4 lines.", False), ("Draft a polite reminder for unpaid fees.", False),
    ("Write a short speech for Teachers' Day.", False), ("How many days are there in a leap year?", False),
    ("What's a good way to organise a staff meeting agenda?", False), ("Translate 'thank you' into Marathi.", False),
    ("Can you explain what a circular is?", False), ("Which is better for reports, Word or Google Docs?", False),
    ("Compare two-wheeler and car loans for a teacher's salary.", False), ("Give me 3 ideas for annual day themes.", False),
    ("Summarise the rules of kho-kho briefly.", False), ("Why do printers jam so often?", False),
    ("Is 1729 a prime number?", False), ("What should I say when a parent complains about homework load?", False),
    ("Proofread this: 'Their is a meeting tommorow at 10.'", False), ("Make a list of 5 safety rules for a science lab.", False),
    ("Tell me about the history of the Indian Railways in 5 lines.", False),
    ("Remember that the fire drill is next Tuesday.", True), ("Save Ravi's number as 98200 12345.", True),
    ("Please email the timetable to all class teachers.", True), ("Delete the duplicate attendance files.", True),
    ("Put a reminder for the PTA meeting on Friday.", True), ("Upload the marksheet to the shared drive.", True),
    ("Convert the circular to PDF and attach it.", True), ("Note that the canteen contract ends in March.", True),
    ("Forget the old wifi password I gave you.", True), ("Search my inbox for the bus contractor's quote.", True),
    ("Let the accounts office know the fees are late.", True), ("Rename the folder 'Misc' to 'Archive 2025'.", True),
    ("Book the auditorium for 21 November.", True), ("I'd like you to file this invoice under Expenses.", True),
    ("Create a document with this week's duty roster.", True), ("Move the old reports into the archive folder.", True),
    ("Reply to Sunita saying the meeting is confirmed.", True), ("my locker code is 4417, don't lose it", True),
    ("Check my drive for the admission form template.", True), ("Schedule the science quiz for the 5th.", True),
]
