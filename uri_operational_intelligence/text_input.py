"""Text and speech input contract (`uri.text_input.v1`) and deterministic transcript cleanup.

The same text intelligence serves typed text and transcribed speech. A turn may carry an optional input envelope:

    {"schema": "uri.text_input.v1",
     "source": "typed" | "transcript",
     "transcript": {                      # required when source == "transcript", absent otherwise
         "raw": str,                      # exactly what the recogniser produced (kept, shown, never rewritten)
         "engine": str,                   # recogniser id; "simulated" when no recogniser was involved
         "simulated": bool,               # True when the text was typed or scripted to stand in for speech
         "language": str | None,          # BCP-47 hint, e.g. "en-IN", "hi-IN"; None when unknown
         "uncertain": [str] }}            # spans the recogniser marked low-confidence (possible mishearing)

Rules (validated here, fail closed):
  * For a transcript, the turn text must equal `transcript.raw`. The interpretation is produced by URI, never by
    the caller, so the original can always be compared with the result.
  * `engine == "simulated"` if and only if `simulated` is true. A real recogniser must name itself.
  * Unknown keys are refused. Sizes are bounded.

No speech recognition runs in this module. Nothing here claims that a microphone works.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SCHEMA = "uri.text_input.v1"
SOURCES = ("typed", "transcript")
MAX_RAW = 20000
MAX_UNCERTAIN = 32


class InputRejected(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TextInput:
    source: str = "typed"
    raw: str | None = None
    engine: str | None = None
    simulated: bool = False
    language: str | None = None
    uncertain: tuple = field(default_factory=tuple)

    @property
    def is_transcript(self):
        return self.source == "transcript"

    def to_dict(self):
        if not self.is_transcript:
            return {"source": "typed"}
        return {"source": "transcript", "raw": self.raw, "engine": self.engine, "simulated": self.simulated,
                "language": self.language, "uncertain": list(self.uncertain)}


TYPED = TextInput()


def parse(envelope, text: str) -> TextInput:
    """Validate an optional input envelope against the turn text. None means typed input."""
    if envelope is None:
        return TYPED
    if not isinstance(envelope, dict):
        raise InputRejected("INPUT_NOT_OBJECT")
    if envelope.get("schema") != SCHEMA:
        raise InputRejected("INPUT_SCHEMA")
    src = envelope.get("source")
    if src not in SOURCES:
        raise InputRejected("INPUT_SOURCE")
    if src == "typed":
        if set(envelope) != {"schema", "source"}:
            raise InputRejected("INPUT_KEYS")
        return TYPED
    if set(envelope) != {"schema", "source", "transcript"}:
        raise InputRejected("INPUT_KEYS")
    t = envelope["transcript"]
    if not isinstance(t, dict) or not set(t) <= {"raw", "engine", "simulated", "language", "uncertain"} \
            or not {"raw", "engine", "simulated"} <= set(t):
        raise InputRejected("TRANSCRIPT_KEYS")
    raw, engine, simulated = t["raw"], t["engine"], t["simulated"]
    if not isinstance(raw, str) or not raw.strip() or len(raw) > MAX_RAW:
        raise InputRejected("TRANSCRIPT_RAW")
    if raw != text:
        raise InputRejected("TRANSCRIPT_TEXT_MISMATCH")
    if not isinstance(simulated, bool):
        raise InputRejected("TRANSCRIPT_SIMULATED")
    if not isinstance(engine, str) or not engine.strip() or len(engine) > 80 or (engine == "simulated") != simulated:
        raise InputRejected("TRANSCRIPT_ENGINE")
    lang = t.get("language")
    if lang is not None and (not isinstance(lang, str) or not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", lang)):
        raise InputRejected("TRANSCRIPT_LANGUAGE")
    unc = t["uncertain"] if "uncertain" in t else []     # a supplied value must be a list (no coercion)
    if not isinstance(unc, list) or len(unc) > MAX_UNCERTAIN or not all(isinstance(u, str) and 0 < len(u) <= 200 and u in raw
                                                                     for u in unc):
        raise InputRejected("TRANSCRIPT_UNCERTAIN")
    return TextInput("transcript", raw, engine, simulated, lang, tuple(unc))


# ---- deterministic cleanup ---------------------------------------------------------------------------------------
# Fillers only. Nothing here decides which of two values the speaker meant: that is interpretation (Brain).
_FILLERS = re.compile(r"(?<![\w'])(?:u+m+|u+h+|e+r+m+|hmm+|mm+)(?![\w'])[,.]?", re.I)
_REPEAT = re.compile(r"\b(\w+)(\s+\1\b)+", re.I)
_SPACE_PUNCT = re.compile(r"\s+([,.;:!?])")
_MULTI = re.compile(r"[ \t]{2,}")
_VALID_DOUBLES = {"had", "that", "is", "do", "very", "so", "no", "bye", "knock", "ha", "bara", "jaldi", "dheere"}


def clean_transcript(raw: str) -> str:
    """Remove hesitation fillers and immediate word repeats ("the the"), tidy spacing. Keeps every content word
    and every self-correction: "five, sorry, seven" survives intact for the Brain to resolve."""
    t = _FILLERS.sub("", raw)
    t = _REPEAT.sub(lambda m: m.group(0) if m.group(1).lower() in _VALID_DOUBLES else m.group(1), t)
    t = _SPACE_PUNCT.sub(r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    t = _MULTI.sub(" ", t)
    t = re.sub(r"^[\s,]+", "", t).strip()
    return t


# Spoken self-correction cues. Used to (a) tell the Brain a correction is likely and (b) verify that its answer
# accounts for one. Matching a cue never changes text by itself.
_CORRECTION_CUES = re.compile(
    r"\b(?:sorry|no,? wait|wait,? no|i mean|i meant|no,? i meant|actually|rather|correction|scratch that|"
    r"not (?:\w+[ ,]+){0,3}but|make that|let me rephrase|oops|nahi(?:n)?,?|matlab|"
    r"no no|nope)\b|\bno,(?=\s)", re.I)       # "on Tuesday, no, Wednesday" (live finding LQ-15)


def correction_cues(text: str) -> list:
    return [m.group(0) for m in _CORRECTION_CUES.finditer(text or "")]
