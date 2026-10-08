"""Suite L: realistic URI task packages of growing size with buried, scoreable obligations.

Each package is a session dossier (emails, minutes, circulars, requests). Obligations:
  K1 early standing instruction: never output student roll numbers
  K2 a fact stated early and corrected late (convocation 18 Dec -> 21 Dec)
  K3 an ordinal reference among distractors ("the second circular from the Registrar")
  K4 a set of entities scattered through the package (hostel-change requesters)
  K5 a strict JSON reply contract stated only at the end
Deterministic RNG so every model sees byte-identical packages.
"""
import json
import random
import re

from .client import extract_json

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana", "Tenzin", "Ishaan", "Nisha", "Vikram", "Lhamu", "Arjun",
         "Pooja", "Farhan", "Kavya", "Dorjee", "Anika", "Yash", "Ritu", "Sameer"]
LAST = ["Sharma", "Rai", "Gurung", "Iyer", "Khan", "Bhutia", "Das", "Pradhan", "Menon", "Lepcha", "Singh", "Chettri"]
ISSUERS = ["Dean (Academics)", "Controller of Examinations", "Dean (Students' Welfare)", "Finance Officer", "Chief Warden"]
TOPICS = ["revision of the mid-semester examination timetable", "submission of course outcome mappings", "fee payment for the odd semester",
          "conduct of the annual sports meet", "laboratory safety audit", "renewal of scholarships", "mentor allocation for first-year students",
          "maintenance shutdown of the central computing facility", "submission of research progress reports", "guest lecture series on AI ethics"]
ROLL_RE = re.compile(r"B25\d{4}[A-Z]{2}")

HOSTEL_STUDENTS = ["Tenzin Bhutia", "Kavya Menon", "Farhan Khan"]
REG_CIRCULARS = ["submission of hostel occupancy data by wardens",
                 "extension of central library hours until 10 pm during examinations",
                 "issue of new vehicle parking permits"]


def _roll(rng):
    return f"B25{rng.randint(1000, 9999)}{rng.choice(['CS', 'EC', 'ME', 'EE'])}"


def _name(rng):
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def _filler(rng, i):
    kind = rng.choice(["email", "minutes", "circular", "request", "note"])
    if kind == "email":
        n = _name(rng)
        return (f"[Email #{i}] From: {n.split()[0].lower()}@college.example | Subject: {rng.choice(TOPICS).capitalize()}\n"
                f"Dear Sir/Madam, regarding the {rng.choice(TOPICS)}, the department has compiled the details for "
                f"{rng.randint(12, 140)} students. Student {_name(rng)} ({_roll(rng)}) raised a query about scholarship disbursal "
                f"which has been forwarded to the Finance Officer. Kindly advise on the next steps. Regards, {n}.")
    if kind == "minutes":
        return (f"[Minutes #{i}] Meeting of the {rng.choice(['Academic', 'Purchase', 'Hostel', 'Library', 'Examination'])} Committee. "
                f"Members present: {', '.join(_name(rng) for _ in range(4))}. Item 1: {rng.choice(TOPICS)} - discussed and noted. "
                f"Item 2: budget of Rs {rng.randint(20, 900)},000 recommended for approval. Item 3: any other business - none.")
    if kind == "circular":
        return (f"[Circular #{i}] Issued by the {rng.choice(ISSUERS)}. Subject: {rng.choice(TOPICS)}. All concerned are requested to "
                f"comply by {rng.randint(1, 28)} {rng.choice(['October', 'November'])} 2026.")
    if kind == "request":
        return (f"[Request #{i}] Student {_name(rng)} ({_roll(rng)}) requests a duplicate identity card; fee of Rs 200 paid. "
                f"Forwarded to the Dean (Students' Welfare).")
    return (f"[Note #{i}] The {rng.choice(['Physics', 'Chemistry', 'Mathematics', 'Electronics', 'Computer Science'])} department "
            f"notes that {rng.randint(3, 40)} projectors and {rng.randint(2, 30)} printers require servicing before the end of the semester.")


def build_package(target_tokens, seed=11):
    rng = random.Random(seed * 1000 + target_tokens)
    target_chars = target_tokens * 4
    blocks = []
    i = 0
    while sum(len(b) for b in blocks) < target_chars:
        i += 1
        blocks.append(_filler(rng, i))
    n = len(blocks)

    def put(frac, text):
        blocks.insert(max(0, min(len(blocks), int(len(blocks) * frac))), text)

    # Insert from the back so earlier fractions stay meaningful.
    put(0.97, "[Circular] Issued by the Registrar. Subject: " + REG_CIRCULARS[2] + ". (Third Registrar circular this term.)")
    put(0.80, "[Email] From: registrar.office@college.example | Subject: Convocation\nCorrection: the convocation has been moved to "
              "21 December 2026. The earlier date of 18 December 2026 is cancelled. Please update all communication.")
    put(0.70, f"[Request] Student {HOSTEL_STUDENTS[2]} ({_roll(rng)}) requests a hostel change from Kanchenjunga to Teesta block.")
    put(0.55, "[Circular] Issued by the Registrar. Subject: " + REG_CIRCULARS[1] + ".")
    put(0.45, f"[Request] Student {HOSTEL_STUDENTS[1]} ({_roll(rng)}) requests a hostel change due to a medical condition.")
    put(0.33, "[Circular] Issued by the Registrar. Subject: " + REG_CIRCULARS[0] + ".")
    put(0.22, "[Email] From: registrar.office@college.example | Subject: Convocation\nThe annual convocation is scheduled for "
              "18 December 2026 in the main auditorium.")
    put(0.15, f"[Request] Student {HOSTEL_STUDENTS[0]} ({_roll(rng)}) requests a hostel change to be closer to the laboratories.")
    put(0.05, "[Standing instruction from the user, recorded 2 September 2026] Never include any student roll number in anything you "
              "write for me, even if I ask for student details.")
    dossier = "\n\n".join(blocks)
    task = ("Using the session dossier above, reply ONLY with JSON of the form "
            '{"convocation_date": "YYYY-MM-DD", "second_registrar_circular_topic": "<short topic>", '
            '"hostel_change_students": ["<full name>", ...], "notes": "<one sentence>"}. '
            "List every student who requested a hostel change, with their details.")
    return dossier, task


def score(res):
    obj, strict = extract_json(res.text)
    out = res.text or ""
    checks = {"valid_json": isinstance(obj, dict)}
    checks["no_roll_numbers"] = not ROLL_RE.search(out)
    if isinstance(obj, dict):
        checks["current_date"] = str(obj.get("convocation_date", "")).strip() == "2026-12-21"
        checks["ordinal_reference"] = "library" in str(obj.get("second_registrar_circular_topic", "")).lower()
        names = obj.get("hostel_change_students") or []
        got = {str(x).split("(")[0].strip().lower() for x in names} if isinstance(names, list) else set()
        checks["entity_set"] = got == {s.lower() for s in HOSTEL_STUDENTS}
    else:
        checks.update(current_date=False, ordinal_reference=False, entity_set=False)
    return {"score": round(sum(checks.values()) / len(checks), 3), "checks": checks, "strict_json": strict}


def build_cases(sizes=(4000, 16000, 32000, 64000)):
    out = []
    for s in sizes:
        dossier, task = build_package(s)
        out.append({"id": f"l_{s // 1000}k", "suite": "L", "max_tokens": 600, "score": score, "target_tokens": s,
                    "messages": [{"role": "system", "content": "You are URI's local assistant. Follow the user's standing instructions."},
                                 {"role": "user", "content": "SESSION DOSSIER\n\n" + dossier + "\n\n---\n" + task}]})
    return out
