"""Deterministic interpreter for festival-greeting scheduling requests (A2UI slice, docs/a2ui/A2UI_ARCHITECTURE.md).

    "URI, schedule Claude to create a festival GIF two days before each major Indian festival and bring it to me
     for approval."
 -> {"domain": "scheduler", "kind": "festival_gif_schedule", "interpreter": INTERPRETER,
     "request": {"offset_days": 2, "time": "09:00", "festivals": None (= the major list), "assumptions": [...]}}

It recognises ONE request family and returns None for everything else, so ordinary questions stay conversational
("when is Diwali?", "schedule a meeting"). It has no authority: the result is a request for the scheduler to PROPOSE;
the owner sees, edits and confirms the proposal. Every default it applies is stated in `assumptions`.
It is labelled deterministic; it is not the Brain.
"""
from __future__ import annotations

import re

INTERPRETER = "deterministic.schedule_intent.v1"
OFFSETS = (1, 2, 3, 5, 7)
NUM = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "a week": 7, "one week": 7}
# Calendar keys (uri_scheduler/data/in_festivals.json); tests check every value exists there.
NAMES = {
    "diwali": "diwali", "deepavali": "diwali", "holi": "holi", "dussehra": "dussehra", "dasara": "dussehra",
    "vijaya dashami": "dussehra", "vijayadashami": "dussehra", "christmas": "christmas", "eid ul fitr": "eid_ul_fitr",
    "eid-ul-fitr": "eid_ul_fitr", "id-ul-fitr": "eid_ul_fitr", "bakrid": "eid_ul_zuha", "eid ul adha": "eid_ul_zuha",
    "eid-ul-zuha": "eid_ul_zuha", "janmashtami": "janmashtami", "ram navami": "ram_navami", "guru nanak": "guru_nanak_jayanti",
    "gurpurab": "guru_nanak_jayanti", "mahavir jayanti": "mahavir_jayanti", "buddha purnima": "buddha_purnima",
    "ganesh chaturthi": "ganesh_chaturthi", "onam": "onam", "pongal": "pongal", "makar sankranti": "makar_sankranti",
    "raksha bandhan": "raksha_bandhan", "rakhi": "raksha_bandhan", "losar": "losar", "losoong": "losoong_namsoong",
    "saga dawa": "saga_dawa", "pang lhabsol": "pang_lhabsol", "lhabab duechen": "lhabab_duechen", "dasain": "dasain_sikkim",
    "tihar": "tihar_sikkim", "chhath": "chhath_puja", "bhai dooj": "bhai_dooj", "karva chauth": "karva_chauth",
}
SIKKIM = ("losar", "saga_dawa", "pang_lhabsol", "dasain_sikkim", "lhabab_duechen", "tihar_sikkim", "sakewa",
          "kagyed_dance", "losoong_namsoong", "chasok_tongnam", "barahimijong", "tamu_lochar", "sonam_lochhar",
          "maghe_sankranti", "bhumchu")
MAJOR = ("holi", "ram_navami", "mahavir_jayanti", "buddha_purnima", "eid_ul_fitr", "eid_ul_zuha", "janmashtami",
         "dussehra", "diwali", "guru_nanak_jayanti", "christmas", "milad_un_nabi")
OTHER_HARNESS = re.compile(r"\b(codex|gemini|gpt|chatgpt|openai|antigravity|hermes|ollama)\b")

_SCHEDULE = re.compile(r"\b(schedule|every|each|before (?:each|every|all)|ahead of|in advance|recurring|automatically)\b")
_FESTIVAL = re.compile(r"\bfestival|\bfestivals\b|" + "|".join(re.escape(k) for k in NAMES))
_ARTIFACT = re.compile(r"\b(gif|gifs|greeting|greetings|animation|animated|card|cards|wish|wishes)\b")
_QUESTION = re.compile(r"^\s*(when|what|which|is|are|does|do|how many|list)\b")
_OFFSET = re.compile(r"\b(\d{1,2}|a week|one week|a|one|two|three|four|five|six|seven)\s+(day|days|week)\s+(?:before|ahead|prior|in advance)")
_TIME = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\b")


# Requests about an existing schedule (cancel, stop, change ...) are never turned into a NEW proposal (A2UI r2, N1).
_CHANGE = re.compile(r"\b(cancel|stop|pause|resume|delete|remove|disable|turn off|unschedule|edit|change|modify|update|reschedule|undo)\b")
# Asking for the result to be brought back for approval is part of the request, not another action.
_DELIVERY = re.compile(r"\b(bring|send|show|give|return)\s+(it|them|the gifs?|the results?)\s+(back\s+)?to me\b|\bfor (my )?(approval|review)\b")
_MAKE = re.compile(r"\b(create|make|generate|design|draw|prepare|produce|render|animate)\b")
_COMPETING = re.compile(r"\b(email|e-mail|mail|meeting|meet|call|phone|remind|reminder|reminders|message|whatsapp|sms|"
                        r"post|tweet|publish|send|share|upload|invite|invitation|discuss|book|order|buy|pay)\b")


def _norm(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def interpret(text):
    """A scheduling handoff for a festival-greeting request, or None (stay conversational)."""
    if not isinstance(text, str) or len(text) > 2000:
        return None
    t = _norm(text)
    if _QUESTION.match(t) or not (_SCHEDULE.search(t) and _FESTIVAL.search(t) and _ARTIFACT.search(t)):
        return None
    # URI must be asked to MAKE the greeting, and the sentence must not be about another action that only mentions
    # festivals or greetings (an email, a meeting, a reminder, posting ...): those keep the normal path (A2UI r1, F3).
    if _CHANGE.search(t) or not _MAKE.search(t) or _COMPETING.search(_DELIVERY.sub(" ", t)):
        return None
    assumptions = []
    offset = 2
    m = _OFFSET.search(t)
    if m:
        n = NUM.get(m.group(1)) if not m.group(1).isdigit() else int(m.group(1))
        if m.group(2) == "week":
            n = 7 * (n or 1)
        if n not in OFFSETS:
            near = min(OFFSETS, key=lambda o: (abs(o - n), o))
            assumptions.append(f"You asked for {n} days before; the choices are 1, 2, 3, 5 or 7, so I used {near}.")
            n = near
        offset = n
    else:
        assumptions.append("You did not say how early; I used 2 days before.")
    hhmm = "09:00"
    tm = _TIME.search(t)
    if tm:
        h, mi, ap = int(tm.group(1)), int(tm.group(2) or 0), (tm.group(3) or "").replace(".", "")
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mi <= 59:
            hhmm = f"{h:02d}:{mi:02d}"
    else:
        assumptions.append("You did not give a time; I used 09:00 Asia/Kolkata.")
    hits = []
    for phrase, key in NAMES.items():
        m2 = re.search(r"\b" + re.escape(phrase) + r"\b", t)
        if m2:
            hits.append((m2.start(), key))
    named = list(dict.fromkeys(k for _, k in sorted(hits)))       # in the order the owner named them
    festivals = None
    if "sikkim" in t:
        festivals = list(dict.fromkeys(named + list(SIKKIM) + (list(MAJOR) if "major" in t else [])))
        assumptions.append("Sikkim festivals come from the Sikkim gazette; only dated (2026) records can be scheduled.")
    elif named and not re.search(r"\b(each|every|all)\s+(major\s+)?(indian\s+)?festivals?\b", t):
        festivals = named
    else:
        assumptions.append("'Major festivals' means the 12 national festivals; add or remove any below.")
    if OTHER_HARNESS.search(t):
        assumptions.append("Scheduled GIFs are made by Claude only; another provider is never used.")
    return {"domain": "scheduler", "kind": "festival_gif_schedule", "interpreter": INTERPRETER,
            "request": {"festivals": festivals, "time": hhmm, "offset_days": offset, "assumptions": assumptions[:6]}}
