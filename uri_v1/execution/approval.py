"""Shared negative-intent detection for the M37/M38 approval and permission-grant
gates (Chetan, 2026-09-28): `Workspace.write_back`'s `WritebackApproval`, and the
harness's `ElevationGrant`/`CapabilityGrant`.

`negated()` (`uri_v1.memory.contracts`, M36) catches formal negation ("not",
"never", "don't", ...) and stays exactly as-is here: this module never edits it
and never widens M36's own certainty gate. What it adds is scoped strictly to
this approval path: real replies to an approval prompt also use informal
negative interjections that formal negation words don't cover ("nah", "nope"),
and a reply built entirely of approval-looking words but led by one of those
must still fail closed rather than be read as consent.

This is not a general natural-language negation detector. It must only be used
where a `TrustedInput.raw_text` is being checked for consent to write, escalate
or grant something, never as a substitute for `negated()` elsewhere.
"""
from __future__ import annotations

import re

from uri_v1.memory.contracts import negated

# Informal negative interjections seen in real approval replies. Closed and
# deliberately small, matched only as a whole normalized token (never a
# substring), so it cannot misfire on the object of an approval (e.g. a
# filename or directory name that happens to contain these letters).
INFORMAL_NEGATIVES = frozenset({"nah", "nope"})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def approval_declined(raw_text: str) -> bool:
    """True if `raw_text` reads as a decline of an approval/grant prompt.

    Formal negation is delegated to `negated()`, unchanged. On top of that,
    this also declines whenever any normalized token is one of
    `INFORMAL_NEGATIVES`, the same word-presence shape `negated()` itself
    uses: "nah apply it" and "nope, apply it" must fail closed even though
    "apply" alone would otherwise read as an approval word.
    """
    if negated(raw_text):
        return True
    tokens = _TOKEN_RE.findall(raw_text.casefold())
    return bool(INFORMAL_NEGATIVES.intersection(tokens))
