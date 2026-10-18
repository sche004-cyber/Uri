"""Long-context usable-capacity suite (LC): does the model still retrieve, track corrections and reason over a dossier
that fills most of the allocated window?

The dossier reuses the accepted Suite L generator (model_lab/lab/longctx.py: standing instruction, superseded fact,
ordinal reference, scattered entity set, strict JSON contract) and adds scoreable needles at fixed depths:
  * three single facts at early / middle / late depth;
  * a two-hop fact (coordinator named in one block, budget of that person's event in a far block);
  * an aggregate over three scattered entries (petty-cash voucher PC-17);
  * an absent fact (a question whose answer is NOT in the dossier: must be null, never invented).
Turn 2 re-uses the identical prefix with a new question, to measure prefix-cache reuse on a hybrid model and score a
further needle. Every key is fixed in code; RNG is seeded by size, so every model sees byte-identical dossiers.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "model_lab"))
from lab import longctx as L  # noqa: E402

NEEDLES = [
    (0.08, "[Note] Estate office: the generator servicing contract number for the north campus is GSC-5521."),
    (0.12, "[Note] The annual science exhibition this year is coordinated by Dr. Lhamu Pradhan of the Physics department."),
    (0.30, "[Voucher] Petty cash voucher PC-17 (part 1 of 3): Rs 1,250 paid for poster printing."),
    (0.48, "[Note] Stores: the spare key for the chemistry store room is kept in locker 4417 in the admin block."),
    (0.50, "[Note] Transport office: the school bus with registration SK-04-B-7730 is due for its fitness test on 9 November 2026."),
    (0.62, "[Voucher] Petty cash voucher PC-17 (part 2 of 3): Rs 3,400 paid for exhibition stall hire."),
    (0.85, "[Finance] Approved event budgets: Dr. Lhamu Pradhan's event - Rs 48,500; the inter-house quiz - Rs 12,000; "
           "the alumni meet - Rs 30,000."),
    (0.90, "[Voucher] Petty cash voucher PC-17 (part 3 of 3): Rs 875 paid for refreshments."),
    (0.93, "[Note] IT cell: the new Wi-Fi password for the staff room network is Teesta#2026."),
]

TASK = ("Using the session dossier above, reply ONLY with JSON of the form "
        '{"convocation_date": "YYYY-MM-DD", "second_registrar_circular_topic": "<short topic>", '
        '"hostel_change_students": ["<full name>", ...], "generator_contract": "<id>", "bus_fitness_test_date": "YYYY-MM-DD", '
        '"staff_wifi_password": "<text>", "science_exhibition_budget_rs": <integer>, "pc17_total_rs": <integer>, '
        '"principal_mobile_number": "<number or null if the dossier does not state it>"}. '
        "List every student who requested a hostel change, with their details.")
FOLLOWUP = ("One more question about the same dossier. Reply ONLY with JSON "
            '{"chemistry_store_key_locker": "<locker number>"}.')


def build(target_tokens, tokenize=None, seed=11):
    """Dossier + task for roughly target_tokens prompt tokens. With `tokenize` (server /tokenize), the dossier is
    rescaled once so the real prompt lands within ~3% of the target."""
    def make(chars_per_tok):
        dossier, _ = L.build_package(int(target_tokens * 4 / chars_per_tok), seed=seed)
        blocks = dossier.split("\n\n")
        for frac, text in sorted(NEEDLES, key=lambda x: -x[0]):
            blocks.insert(int(len(blocks) * frac), text)
        return "\n\n".join(blocks)
    dossier = make(4.0)
    if tokenize:
        n = tokenize(dossier)
        dossier = make(4.0 * n / target_tokens)
    return dossier


def messages(dossier):
    return [{"role": "system", "content": "You are URI's local assistant. Follow the user's standing instructions."},
            {"role": "user", "content": "SESSION DOSSIER\n\n" + dossier + "\n\n---\n" + TASK}]


def _obj(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def _int(v):
    try:
        return int(re.sub(r"[^\d]", "", str(v)))
    except ValueError:
        return None


def score(text):
    o = _obj(text)
    c = {"valid_json": isinstance(o, dict), "no_roll_numbers": not L.ROLL_RE.search(text or "")}
    o = o if isinstance(o, dict) else {}
    c["superseded_fact"] = str(o.get("convocation_date", "")).strip() == "2026-12-21"
    c["ordinal_reference"] = "library" in str(o.get("second_registrar_circular_topic", "")).lower()
    names = o.get("hostel_change_students") or []
    got = {str(x).split("(")[0].strip().lower() for x in names} if isinstance(names, list) else set()
    c["entity_set"] = got == {s.lower() for s in L.HOSTEL_STUDENTS}
    c["needle_early"] = str(o.get("generator_contract", "")).strip().upper() == "GSC-5521"
    c["needle_mid"] = str(o.get("bus_fitness_test_date", "")).strip() == "2026-11-09"
    c["needle_late"] = str(o.get("staff_wifi_password", "")).strip() == "Teesta#2026"
    c["two_hop"] = _int(o.get("science_exhibition_budget_rs")) == 48500
    c["aggregate"] = _int(o.get("pc17_total_rs")) == 5525
    v = o.get("principal_mobile_number", "MISSING")
    c["absent_fact_null"] = v is None or str(v).strip().lower() in ("null", "none", "", "not stated", "unknown")
    return {"score": round(sum(c.values()) / len(c), 3), "checks": c}


def score_followup(text):
    o = _obj(text) or {}
    return {"followup_needle": "4417" in str(o.get("chemistry_store_key_locker", ""))}
