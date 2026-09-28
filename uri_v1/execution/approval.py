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


# A question, or a turn led by a question, modal or conditional word, asks about or
# hypothesizes a grant; it never makes one (Codex probe of f9ac385, plan AC-H5: "can I
# use sheets?", "should we allow network", "maybe use sheets", "if you use sheets it
# breaks"). Same precedent as M36's recorder, which refuses questions as transitions.
# Leading-word only, so an explicit grant with a trailing condition ("yes, allow access
# to /data if needed") is unaffected; any "?" anywhere is enough to refuse.
UNCERTAIN_LEADS = frozenset({"can", "could", "should", "would", "will", "do", "does", "how", "what", "why",
                             "if", "maybe", "might", "may", "perhaps"})


def approval_uncertain(raw_text: str) -> bool:
    """True if `raw_text` is a question or a hypothetical rather than a grant."""
    if "?" in raw_text or "？" in raw_text:  # ASCII or fullwidth question mark
        return True
    tokens = _TOKEN_RE.findall(raw_text.casefold())
    return bool(tokens) and tokens[0] in UNCERTAIN_LEADS


def approval_withheld(raw_text: str) -> bool:
    """The single test every approval/grant gate applies: declined, or not actually given."""
    return approval_declined(raw_text) or approval_uncertain(raw_text)


# -- positive allowlist (Codex bridge probe of c7832b9) -------------------------------------------
# A leading-word denylist kept leaking ("please can we use sheets", "I guess use sheets", "use
# sheets maybe", "we could use sheets"). Following M36's certainty gate (`affirmative_words`,
# `STATUS_FILLERS`), a turn is a grant only if, once the granted data itself (capability names,
# the granted path, write-back file names) is taken out, every remaining word is a grant verb
# or one of these closed fillers, and at least one grant verb is present. Anything else --
# hedges, questions, conditions, extra clauses -- is not a grant.
#
# Codex re-check of 249660e: a declarative ("I use sheets", "I allow network") or a time/scope
# qualifier ("for now", "just for this", "allow network on") is not a grant; the one scope
# phrase accepted is the exact "for this run" (`_RUN_SCOPE`), which every grant is bound to.
# Codex re-check of f8115d5: a dangling referent ("use sheets with it", "allow network in that",
# "apply the fix with it") is not a grant either, so the fillers are cut to this minimal set of
# assent and politeness words. Anything a gate needs beyond them (an elevation's own words, a
# capability kind such as "server", "access to <path>") it passes itself as data or extra words.
GRANT_FILLERS = frozenset("yes yeah ok okay sure please go ahead the and thanks thank you".split())
_GRANT_PUNCTUATION = frozenset(",.!:;\"'-")
_RUN_SCOPE = re.compile(r"(?<!\S)for this run(?=$|\s|[,.!:;](?:\s|$))", re.IGNORECASE)


def _standalone(item: str) -> re.Pattern:
    """`item` (optionally in matching quotes) where it stands as a whole word of its own: at
    the start or after whitespace, and at the end, before whitespace, or before sentence-final
    punctuation that is itself followed by whitespace or the end. So "sheets.server",
    "network-server" or "x/sheets" never count as naming "sheets" or "network" (Codex
    re-checks of 249660e and f8115d5)."""
    return re.compile(r"(?<!\S)([\"']?)" + re.escape(item) + r"\1(?=$|\s|[,.!:;](?:\s|$))", re.IGNORECASE)


def names_standalone(text: str, item: str) -> bool:
    return bool(item) and _standalone(str(item)).search(text) is not None


def _strip_data(text: str, data) -> str:
    """Remove each granted item where it stands on its own (see `_standalone`)."""
    for d in sorted({str(x) for x in data if x}, key=len, reverse=True):
        text = _standalone(d).sub(" ", text)
    return text


def approval_given(raw_text: str, verbs, *, data=(), extra_words=()) -> bool:
    """True only for an explicit, unhedged grant: not declined, no question, and every
    word outside `data` is in `verbs`, `extra_words` or `GRANT_FILLERS`, with at least
    one of `verbs` present."""
    if approval_withheld(raw_text): return False
    rest = _RUN_SCOPE.sub(" ", _strip_data(raw_text, data))
    if any(not (c.isascii() and (c.isalnum() or c.isspace())) and c not in _GRANT_PUNCTUATION for c in rest):
        return False
    tokens = _TOKEN_RE.findall(rest.casefold())
    verbs = frozenset(verbs)
    return bool(verbs.intersection(tokens)) and all(t in verbs or t in extra_words or t in GRANT_FILLERS for t in tokens)
