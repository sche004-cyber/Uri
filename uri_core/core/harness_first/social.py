"""Lightweight turn inspection: is this turn purely social (greeting, thanks,
farewell, acknowledgement, small talk, a question about URI itself)?

Deterministic and conservative. A turn is admitted only when every word is in
a closed social vocabulary, it names no file, link, number or action, and it
is short. Anything else returns None and continues down the normal chain, so
a miss costs latency, never correctness. The existing conversational
classifier's whole-message patterns are checked first (reused, not copied).
"""
from __future__ import annotations

import re
from typing import Optional

from uri_core.core import conversational_classifier as _conv

MAX_WORDS = 9

_GREETING = frozenset("hi hii hello helo hey hiya heya yo namaste namaskar greetings morning afternoon evening".split())
_THANKS = frozenset("thanks thank thx ty cheers appreciated appreciate grateful".split())
_FAREWELL = frozenset("bye goodbye goodnight later cya farewell".split())
_ACK = frozenset("ok okay okey k kk noted cool great awesome perfect nice fine alright sure gotcha understood".split())
_SELF = frozenset("who what what's whats are you can do help me with your name".split())
_FILLER = frozenset(
    "uri there so much a lot very again all for now that's thats it is how doing today the good night "
    "see you take care have day nice to meet too and well i im i'm am fine got just tomorrow soon how's going helped that".split())
_VOCAB = _GREETING | _THANKS | _FAREWELL | _ACK | _SELF | _FILLER

_ACTION_HINT = re.compile(
    r"https?://|@|\d|\.(pdf|docx?|xlsx?|csv|txt|pptx)\b|"
    r"\b(send|read|open|search|find|upload|delete|draft|write|convert|check|show|get|make|create|remember|"
    r"recall|email|mail|file|attach|summari[sz]e|translate|print|book|schedule|remind)\b", re.I)


def _intent_from_tokens(tokens: list[str]) -> str:
    t = set(tokens)
    if t & _FAREWELL or {"see", "you"} <= t or {"take", "care"} <= t or "night" in t and "good" in t:
        return "farewell"
    if t & _THANKS:
        return "thanks"
    if t & {"who", "what", "what's", "whats"} and ("you" in t or "your" in t):
        return "about_uri"
    if t & _GREETING:
        return "greeting"
    if "how" in t and "you" in t or {"you", "there"} <= t:
        return "greeting"
    return "acknowledgement"


def social_intent(text: str) -> Optional[str]:
    """Return the social intent, or None when the turn is not purely social."""
    raw = (text or "").strip()
    if not raw or len(raw) > 80 or _ACTION_HINT.search(raw):
        return None
    whole = _conv._TRAILING_PUNCTUATION.sub("", raw).strip()
    for i, pat in enumerate(_conv._WHOLE_MESSAGE_PATTERNS):
        if pat.match(whole):
            if re.search(r"\bgood\s+night\b", whole, re.I):
                return "farewell"
            if i == 1:   # the live pattern groups thanks with acknowledgements ("ok", "got it", "great")
                return "thanks" if re.search(r"\b(thanks|thank|thx|ty|cheers)\b", whole, re.I) else "acknowledgement"
            return ("greeting", "thanks", "farewell")[i]
    tokens = re.findall(r"[a-z']+", raw.casefold())
    if not tokens or len(tokens) > MAX_WORDS or any(t not in _VOCAB for t in tokens):
        return None
    social = _GREETING | _THANKS | _FAREWELL | _ACK
    if not (set(tokens) & social) and not ({"who", "what", "what's", "whats"} & set(tokens) and {"you", "your"} & set(tokens)) \
            and not ({"how", "you"} <= set(tokens)) and not ({"see", "you"} <= set(tokens)) \
            and not ({"take", "care"} <= set(tokens)) and not ({"good", "night"} <= set(tokens))             and not ({"you", "there"} <= set(tokens)):
        return None
    return _intent_from_tokens(tokens)
