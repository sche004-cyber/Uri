"""Deterministic text-intent classification: is this turn a writing task for the draft desk, or not?

No model call, sub-millisecond. Biased to FALL THROUGH: anything it is not sure about goes to the existing
Operational Intelligence path (triage -> answer channel / Core) unchanged. In particular:
  * greetings, questions and analysis are never captured;
  * a request that also asks URI to send, save, file, print, upload or remember goes to Core, which alone acts;
  * revision words ("make", "remove", "replace") are read as draft edits ONLY while a draft is active, and never
    when the object is a file, a message store, memory or the system.

Kinds:
  DRAFT_NEW   create a document from instructions ("draft a letter to the warden about ...")
  EXPAND      rough notes -> a full draft ("expand these notes into a notice: ...")
  CORRECT     grammar/spelling/punctuation only, meaning preserved ("correct this: ...")
  REWRITE     restyle given text ("rewrite politely: ...", "make this more formal: ...")
  REVISE      change the active draft ("make the first paragraph shorter")
  UNDO, REDO, ORIGINAL, DISCARD, SHOW    deterministic draft operations (no model)
  NONE        not a text task
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import triage as T

NONE, DRAFT_NEW, EXPAND, CORRECT, REWRITE, REVISE = "NONE", "DRAFT_NEW", "EXPAND", "CORRECT", "REWRITE", "REVISE"
UNDO, REDO, ORIGINAL, DISCARD, SHOW = "UNDO", "REDO", "ORIGINAL", "DISCARD", "SHOW"
DETERMINISTIC = (UNDO, REDO, ORIGINAL, DISCARD, SHOW)
BRAIN_KINDS = (DRAFT_NEW, EXPAND, CORRECT, REWRITE, REVISE)

_LEAD = r"^\s*(?:(?:uri|hey uri|ok(?:ay)? uri)[,:!]?\s+)?(?:(?:please|pls|kindly|now|also|just|ok(?:ay)?|so|and)[,]?\s+)*" \
        r"(?:(?:can|could|would|will) you\s+(?:please\s+)?|i (?:want|need|would like) you to\s+|help me\s+|let'?s\s+)?"

DOC_NOUNS = (r"letter|e-?mail|mail|note|office note|notice|circular|memo(?:randum)?|report|summary|application|"
             r"office order|order|reply|response|message|minutes|request|complaint|announcement|invitation|"
             r"statement|agenda|draft|leave application|cover letter|representation|patra|chitthi|aavedan|"
             r"praarthna patra|prarthna patra|suchna")
_CREATE_VERBS = r"draft|write|compose|prepare|create|make|generate|frame|type(?: out)?|put together|pen|do"
_DRAFT_NEW = re.compile(_LEAD + r"(?:" + _CREATE_VERBS + r")\s+(?:me\s+|up\s+)?(?:(?:a|an|the|one|my|our|this|that|"
                        r"short|brief|formal|polite|official|proper|quick|professional|detailed|simple|new|another)\s+){0,4}"
                        r"(?:[\w-]+\s+){0,2}(?:" + DOC_NOUNS + r")\b", re.I)
_DRAFT_WANT = re.compile(r"^\s*(?:(?:uri|hey uri)[,:!]?\s+)?i (?:need|want|would like) (?:a|an|to (?:draft|write|send) a)\s+"
                         r"(?:[\w-]+\s+){0,3}(?:" + DOC_NOUNS + r")\b", re.I)
# Hinglish: "<noun> ... likho / likh do / bana do / taiyar karo / draft karo"
_DRAFT_HINGLISH = re.compile(r"\b(?:" + DOC_NOUNS + r")\b.{0,120}?\b(?:likho|likh do|likhiye|likh dijiye|likhna hai|"
                             r"bana do|banao|banaiye|bana dijiye|taiyar karo|taiyar kar do|draft karo|draft kar do)\b",
                             re.I | re.S)

_EXPAND = re.compile(_LEAD + r"(?:expand|turn|convert|develop|build|flesh out|make)\s+(?:these|this|my|the following|"
                     r"the)?\s*(?:rough\s+)?(?:notes?|points?|bullets?|outline|jottings)\s+(?:in)?to\b", re.I)
_CORRECT = re.compile(_LEAD + r"(?:correct|proofread|proof-read|fix|check|improve|clean up|tidy up|edit)\s+"
                      r"(?:the\s+|my\s+|its\s+)?(?:(?:grammar|spelling|punctuation|typos?|english|language|mistakes?|"
                      r"errors?)(?:\s+(?:and|&)\s+(?:grammar|spelling|punctuation|typos?))*(?:\s+(?:in|of)\s+(?:this|it|"
                      r"the following|my (?:text|message|paragraph|note|draft)))?|this|it|the following|"
                      r"my (?:text|message|paragraph|note|sentence|draft))\b", re.I)
_CORRECT_BARE = re.compile(r"^\s*(?:grammar check|spell ?check|proofread)\s*[:\-]", re.I)
_REWRITE = re.compile(_LEAD + r"(?:rewrite|re-write|rephrase|reword|paraphrase|polish|simplify|shorten|condense|"
                      r"summari[sz]e|tighten|formali[sz]e|soften|"
                      r"draft (?:this|it|the following)(?: (?:more )?(?:formally|politely|professionally|properly))?|"
                      r"make (?:this|it|the following|my (?:text|message|note|paragraph))\s+(?:a (?:bit|little) |more |less |"
                      r"sound |look )*(?:formal|polite|professional|concise|shorter|longer|clearer|diplomatic|friendly|"
                      r"simple|simpler|courteous|firm|respectful|official|crisp|better))\b", re.I)

# Things only Core may do. A request that asks URI to act goes to the existing path (Core), whatever else it says:
#   * an imperative action at the start of the request or of any sentence of its instruction ("Email the principal.");
#   * a sequenced action anywhere, also after a colon ("..., then email it to the principal", "Finally, save it.");
#   * a coordinated action ("... and send it") unless it sits inside a reported request or infinitive that belongs to
#     the document ("asking parents to sign it and send the form");
#   * a destination or file format ("to my desktop", "as a PDF").
# The draft desk adds a model-side guard on top (`actions_requested`), like the answer channel's ACTION marker.
_CORE_VERBS = (r"send|email|e-mail|mail|forward|post|publish|upload|print|share|save|store|attach|schedule|"
               r"remind me|remember|memori[sz]e|note down|overwrite")
_START_ACTION = re.compile(
    r"^\s*(?:(?:uri|hey uri)[,:!]?\s+)?(?:(?:please|pls|kindly|now|also|just|then|and|finally)[,]?\s+|"
    r"(?:can|could|would|will) you\s+)*(?:" + _CORE_VERBS + r")\b", re.I)
# Sequencing words make an instruction to URI even inside dictated content.
_SEQUENCED = re.compile(r"(?:^|[,;.!?\n]|\b(?:and))\s*(?:then|and then|after that|afterwards|finally|also)[,]?\s+"
                        r"(?:please\s+)?(?:" + _CORE_VERBS + r")\b", re.I)
_DESTINATION = re.compile(
    r"\b(?:in|into|to|on) (?:the |my )?(?:shared |google )?(?:desktop|folder|drive|documents|downloads)\b|"
    r"\bas (?:a |an )?(?:file|pdf|docx|word (?:file|document)|text file)\b|\.(?:docx|pdf|txt)\b", re.I)
_COORDINATED = re.compile(
    r"\b(?:and|&)\s+(?:please\s+)?(?:send|email|e-mail|mail|forward|save|print|upload|share|post|publish|attach|"
    r"schedule|remind me|remember)\b|"
    r"\b(?:send|email|e-mail|mail|forward|save|print|upload|share|post)\s+(?:it|this|that)\b", re.I)
_SENTENCE = re.compile(r"(?:^|[.!?;\n]+)\s*([^.!?;\n]+)")
_DETERMINERS = r"(?:the|a|an|my|our|his|her|their|your|this|that|these|those|all|every|him|them|me|us|you|it)"
_RECIPIENTS = (r"(?:warden|principal|sir|madam|manager|teacher|office|department|hod|dean|director|parents?|students?|"
               r"staff|everyone|committee|accounts|registrar|librarian|admin|management|team|class|hostel|school|college)")
_INFINITIVE = re.compile(r"\bto\s+(?!" + _DETERMINERS + r"\b|" + _RECIPIENTS + r"\b)[a-z][\w-]*(?:\s+[\w'-]+){0,4}\s*$")
_REPORTED = re.compile(r"\b(?:ask|asks|asking|asked|request|requests|requesting|requested|tell|tells|telling|told|"
                       r"instruct\w*|remind\w*|urg\w*|direct\w*|inform\w*|want|wants|expect\w*)\b[^.;:!?,]*\bto\b", re.I)


def _content_context(t, pos):
    """The coordinated action at `pos` belongs to a reported request or infinitive in the SAME clause (a comma ends
    the clause, so "asking parents to sign the form, then email it" is not exempt)."""
    clause = re.split(r"[.;:!?,\n]", t[:pos])[-1]
    if re.match(r"\s*(?:and|&)?\s*please\b", t[pos:], re.I):
        return False                      # "... and please email it" is addressed to URI
    return bool(_INFINITIVE.search(clause) or _REPORTED.search(clause))


# Objects that are not the draft: edits to these are actions or code work, never draft revisions.
_FOREIGN_OBJECT = re.compile(
    r"\b(?:files?|folders?|directory|inbox|mailbox|my emails|calendar|meeting|reminders?|memory|memories|settings?|"
    r"code|bug|function|repo(?:sitory)?|script|app|program|database|spreadsheet|sheet|account|password|"
    r"brain|model|harness)\b", re.I)


_DOC_OBJECT = re.compile(r"\s*(?:it|this|that|the (?:letter|draft|e-?mail|mail|note|notice|document|circular|memo|"
                         r"report|reply|application))\b", re.I)


def _core_only(t: str) -> bool:
    """True when the request asks URI to act (send, save, file, remember ...): such turns go to Core."""
    if _DESTINATION.search(t):
        return True
    instruction, payload = split_payload(t)
    head = instruction if payload is not None else t
    if _SEQUENCED.search(head):
        return True
    if payload is not None:
        # Inside dictated content "then send the form to the office" belongs to the document; "then email it"
        # (the document itself) is an instruction to URI.
        for m in _SEQUENCED.finditer(payload):
            if _DOC_OBJECT.match(payload, m.end()):
                return True
    for m in _SENTENCE.finditer(head):
        if _START_ACTION.match(m.group(1)):
            return True
    for m in _COORDINATED.finditer(t):
        if not _content_context(t, m.start()):
            return True
    return False


_CODE = re.compile(r"\b(?:code|bug|function|stack ?trace|compile|repo(?:sitory)?|python|flutter|script)\b", re.I)

_UNDO = re.compile(r"^\s*(?:(?:uri|ok|okay|no|please)[,!]?\s+)*(?:undo|revert|roll back|rollback|go back|take back|"
                   r"cancel)(?:\s+(?:that|this|it|the|my|your))?(?:\s+(?:last|previous|latest))?(?:\s+(?:change|changes|"
                   r"edit|edits|correction|revision|one|step|version))?(?:\s+(?:please|pls))?\s*[.!]?\s*$|"
                   r"^\s*(?:undo|revert)\s+(?:karo|kar do|kijiye)\s*[.!]?\s*$|"
                   r"^\s*(?:pehle|pichla|pehle wala|purana)\s+(?:wala\s+)?(?:version\s+)?(?:wapas|vapas)\s+(?:lao|karo|kar do)\s*[.!]?\s*$|"
                   r"^\s*(?:go back|revert) to (?:the )?(?:previous|last|earlier) (?:version|draft)\s*[.!]?\s*$", re.I)
_REDO = re.compile(r"^\s*(?:(?:uri|ok|okay|please)[,!]?\s+)*(?:redo|re-do|put (?:it|that) back|reapply|re-apply)"
                   r"(?:\s+(?:that|the|it|my))?(?:\s+(?:last|previous))?(?:\s+(?:change|edit|correction|one))?"
                   r"(?:\s+(?:please|pls))?\s*[.!]?\s*$", re.I)
_ORIGINAL = re.compile(r"^\s*(?:(?:uri|please)[,!]?\s+)*(?:show|display|let me see|give me|what was)(?: me)? "
                       r"(?:the |my )?(?:original|first version|first draft|raw transcript|transcript|what i (?:said|typed))"
                       r"(?:\s+\w+){0,3}\s*[.?!]?\s*$", re.I)
_DISCARD = re.compile(r"^\s*(?:(?:uri|please|ok)[,!]?\s+)*(?:discard|close|clear|drop|abandon|throw away|scrap)"
                      r"\s+(?:the |this |my )?(?:draft|document|letter|email|note)\s*[.!]?\s*$|"
                      r"^\s*(?:start over|start afresh|forget (?:the|this) draft)\s*[.!]?\s*$", re.I)
_SHOW = re.compile(r"^\s*(?:(?:uri|please)[,!]?\s+)*(?:show|display|read out|let me see)(?: me)? (?:the |my )?"
                   r"(?:current |latest )?(?:draft|letter|email|document|version)\s*[.?!]?\s*$", re.I)

# Revision cues: only consulted when a draft is active.
_DROP_QUESTION = re.compile(r"^\s*(?:(?:uri|ok|okay|no)[,!]?\s+)*(?:cancel|never ?mind|forget (?:it|that|about it)|skip (?:it|that)|"
                            r"leave it|drop (?:it|that)|no thanks|chhodo|rehne do|jane do)\b(?:\s+(?:that|the|this|my))?"
                            r"(?:\s+(?:question|request|draft|one))?\s*[.!]?\s*$", re.I)


def drops_question(text: str) -> bool:
    return bool(_DROP_QUESTION.match(text or ""))


_REVISE_START = re.compile(
    r"^\s*(?:(?:uri|ok|okay|no|also|and|but|now|please|pls|kindly|sorry|hmm|actually|wait|then|oh)[,!.]?\s+)*"
    r"(?:(?:can|could|would) you\s+(?:please\s+)?)?"
    r"(?:make|keep|change|replace|remove|delete|drop|cut|add|insert|include|mention|use|say|don'?t|do not|dont|"
    r"instead|actually|shorten|lengthen|expand|simplify|tone|rewrite|rephrase|reword|polish|fix|correct|improve|move|"
    r"swap|put|address|sign|end|start|begin|reduce|tighten|soften|strengthen|not|it should|it'?s|its|the date|"
    r"the (?:first|second|third|fourth|fifth|last|final|opening|closing|next|previous|subject|salutation)\b|"
    r"in the (?:first|second|third|fourth|fifth|last|final|opening|closing)\b|refer|call|spell|write|"
    r"capitali[sz]e|split|merge|combine|leave|omit|skip|mark|bold|correct the|update|set|i meant|i mean|"
    r"that should be|it should be|should be|it was|make that)\b", re.I)
_REVISE_ANY = re.compile(
    r"\b(?:paragraph|para|sentence|subject line|salutation|closing|sign-?off|signature|tone|wording|phrase|"
    r"the letter|the email|the draft|the note|the notice|more formal|less formal|more polite|more diplomatic|"
    r"shorter|longer|concise|instead of|rather than|replace .* with|change (?!of\b)[^.!?;]{1,60}? to|"
    r"karo|kar do|kijiye|rakho|hatao|hata do|badlo|badal do|chhota|chota|lamba|formal)\b", re.I)
_HINGLISH_EDIT = re.compile(r"\b(?:karo|kar do|kijiye|rakho|hatao|hata do|badlo|badal do|likho|daalo|daal do|"
                            r"jodo|jod do|nikalo|nikal do|chhota|chota|lamba)\b", re.I)

_ORDINALS = {"first": 0, "1st": 0, "opening": 0, "pehla": 0, "pehle": 0, "second": 1, "2nd": 1, "doosra": 1,
             "dusra": 1, "doosre": 1, "dusre": 1, "third": 2, "3rd": 2, "teesra": 2, "tisra": 2, "teesre": 2,
             "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1, "final": -1, "closing": -1, "concluding": -1}
_PARA_REF = re.compile(r"\b(first|1st|opening|second|2nd|third|3rd|fourth|4th|fifth|5th|last|final|closing|concluding|"
                       r"pehla|pehle|doosra|dusra|doosre|dusre|teesra|tisra|teesre)\s+(?:body\s+)?(?:paragraph|para)\b|"
                       r"\b(?:paragraph|para)\s+(?:no\.?\s*|number\s+)?(\d{1,2})\b", re.I)
_ROLE_REF = {"subject": re.compile(r"\bsubject(?: line)?\b", re.I),
             "salutation": re.compile(r"\b(?:salutation|greeting line|opening line|dear .* line)\b", re.I),
             "closing": re.compile(r"\b(?:closing line|sign-?off|complimentary close|yours (?:faithfully|sincerely) line)\b", re.I),
             "signature": re.compile(r"\b(?:signature|sign(?:ed)? (?:block|as)|my name at the end)\b", re.I),
             "recipient": re.compile(r"\b(?:address(?:ee)? block|recipient(?:'s)? address|to address)\b", re.I)}
_GLOBAL = re.compile(r"\b(?:it|whole|entire|overall|everything|throughout|all (?:the )?paragraphs|the (?:letter|email|"
                     r"draft|note|notice|document|text|message|circular|report)|tone|language|wording|style|"
                     r"isko|isse|poora|pura)\b", re.I)
_EDIT_VERB = re.compile(r"\b(?:make|rewrite|re-write|rephrase|reword|change|shorten|lengthen|expand|simplify|soften|"
                        r"polish|improve|fix|correct|use|tighten|condense|formali[sz]e|tone (?:it )?down|redo|revise|"
                        r"karo|kar do|kijiye|rakho)\b", re.I)
_KEEP_REST = re.compile(r"\b(?:keep|leave)\b.{0,40}\b(?:else|rest|same|as it is|as is|unchanged|untouched)\b", re.I)
_CLAUSE_SPLIT = re.compile(r"[,;.!?]+|\b(?:and|but|also|then)\b", re.I)
_PHRASE_SWAP = re.compile(
    r"(?:don'?t|do not|dont)\s+(?:say|write|use|mention)\s+[\"'“‘]?(.{2,120}?)[\"'”’]?\s*[.,;]\s*(?:instead\s+)?(?:say|write|use|put)|"
    r"replace\s+[\"'“‘]?(.{2,120}?)[\"'”’]?\s+with\b|"
    r"change\s+(?!of\b)[\"'“‘]?(.{2,120}?)[\"'”’]?\s+to\b|"
    r"instead of\s+[\"'“‘]?(.{2,120}?)[\"'”’]?\s*[,]?\s*(?:say|write|use|put)\b", re.I | re.S)

# UIV2-F1 (2026-10-16): with a draft open, ordinary conversation must never be taken as an edit. Openers that are
# just as common in plain chat ("say hello", "write a haiku", "call me Ravi", "it's raining", "not now", "make me a
# plan", "add milk to the list") count as a revision only when the message is ANCHORED to the document. Strong edit
# verbs ("remove", "replace", "rephrase", "don't ...") and explicit corrections ("I meant Tuesday") need no anchor.
_PREFIX = r"^\s*(?:(?:uri|ok|okay|no|also|and|but|now|please|pls|kindly|sorry|hmm|actually|wait|then|oh)[,!.]?\s+)*" \
          r"(?:(?:can|could|would) you\s+(?:please\s+)?)?"
_WEAK_START = re.compile(
    _PREFIX + r"(?P<verb>make|keep|add|insert|include|use|say|call|write|set|update|start|begin|end|put|address|sign|"
    r"mark|leave|skip|spell|refer|drop|cut|fix|correct|improve|expand|simplify|polish|change|move|it'?s|its|not|"
    r"instead|actually|it should|that should|should|i meant|i mean|it was|make that)\b", re.I)
_PRONOUN_OK = ("make", "keep", "add", "insert", "include", "write", "put", "address", "sign", "end", "start", "begin",
               "spell", "change", "move", "fix", "correct", "improve", "expand", "simplify", "polish", "cut", "refer")
# A part of a document, named with a determiner ("the date", "a line", "that word"; never "in three words").
# Time, name and report also name unrelated Workspace tasks; a quoted phrase only anchors when it occurs in the draft.
_ANCHOR = re.compile(
    r"\b(?:the|that|this|these|those|a|an|another|one|each|every|my|our|its|first|second|third|last|final|"
    r"opening|closing|next|previous)\s+(?:[\w-]+\s+){0,2}?(?:line|lines|word|words|point|points|heading|title|date|"
    r"day|recipient|greeting|ending|opening|subject|bullet|bullets|sentence|sentences|para|paragraph|"
    r"paragraphs|wording|tone|version|draft|letter|e-?mail|note|notice|circular|memo|application|reply|"
    r"message|document|text|amount|figure|number|deadline|venue|signature|details?)\b", re.I)
_CORRECTION = re.compile(r"\bnot\s+\w+\s+\w+[^,.;!?]{0,60},\s*(?:but\s+)?\w|"
                         r"\b(?:i meant|i mean)\b(?!\s+to\b)|\bmake that\b", re.I)
# "my appointment", "my last message": the user's own thing, not the open draft (unless the draft names it).
_MY_OBJECT = re.compile(r"\b(?:my|your)\s+(?:last\s+|previous\s+|next\s+|own\s+)?(?P<noun>[a-z]+)", re.I)
_DRAFT_WORDS = frozenset("draft letter note notice email mail document text application circular memo reply "
                         "signature".split())
_CORRECTION_CONTEXT = re.compile(r"^\s*(?:actually|sorry|no[,!]?|wait|i mean|i meant|make that)\b", re.I)
_SET_FIELD = re.compile(_PREFIX + r"set\s+(?:the|a|my|your)\s+(?:date|day|time)\b", re.I)
_DOCUMENT_REF = re.compile(r"\b(?:draft|letter|document|e-?mail|note|notice|circular|memo|application)\b", re.I)
_LANGUAGE_OBJECT = re.compile(r"(?:the\s+)?(?:grammar|spelling|punctuation|typos?|language|flow|clarity|style|"
                              r"formatting|wording|tone)\b", re.I)


_STOP = frozenset("the and for with that this from have has had was were are you your our their them they she him "
                  "her his its not but all any can could would should will shall about into onto over under then than "
                  "also just very more less some what when where which who why how please actually instead".split())


def _content_tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}|\d+", (s or "").lower()) if w not in _STOP}


def _shares_draft_content(t: str, draft_text: str | None) -> bool:
    """A correction reusing the document's own words can refer to it without saying "draft"."""
    if not draft_text or not _CORRECTION_CONTEXT.match(t):
        return False
    shared = _content_tokens(t) & _content_tokens(draft_text)
    return len(shared) >= 2 or any(w.isdigit() for w in shared)


def _anchored(t: str, draft_text: str | None = None) -> bool:
    """True when a revision-looking message refers to the document (UIV2-F1)."""
    head = t[:400]
    mine = _MY_OBJECT.search(head)
    if mine and mine.group("noun").lower() not in _DRAFT_WORDS and \
            mine.group("noun").lower() not in _content_tokens(draft_text):
        return False                        # "change the date of my appointment", "delete my last message"
    if re.search(r"\b(?:change|update|set)\s+your\s+name\b", head, re.I):
        return False                        # "your name" addresses URI, even if the draft has [Your Name]
    if _SET_FIELD.match(t) and not _DOCUMENT_REF.search(head):
        return False                        # setting a date/time can be a Workspace command, not a draft edit
    if _KEEP_REST.search(head) or _CORRECTION.search(head):
        return True
    if _shares_draft_content(head, draft_text):
        return True
    correction = re.search(r",\s*not\s+(\w+)\b", head, re.I)
    if correction and correction.group(1).lower() in _content_tokens(draft_text):
        return True
    tg = targets_for(t)
    if tg["body"] or tg["roles"]:
        return True
    if tg["phrases"]:
        # A phrase to replace is a reference only when it names text in this draft (or says "that"/"it").
        # Otherwise even "replace X with Y" can refer to an unrelated Workspace object.
        if any(p.lower() in ("it", "this", "that") or (draft_text and p.lower() in draft_text.lower())
               for p in tg["phrases"]):
            return True
        if any(_content_tokens(p) & _content_tokens(draft_text) for p in tg["phrases"]):
            return True                     # "replace the name with Ravi" where the draft has "[Your Name]"
        if re.search(r"\b(?:don'?t|do not|dont)\s+(?:say|write|use|mention)\b", head, re.I):
            return True
        if not _ANCHOR.search(head):
            return False
    if draft_text and any(p.lower() in draft_text.lower()
                          for p in re.findall(r"[\"'“‘]([^\"'”’]{2,})[\"'”’]", head)):
        return True
    if _HINGLISH_EDIT.search(head) and re.search(r"\b(?:isko|isse|poora|pura)\b", head, re.I):
        return True
    w = _WEAK_START.match(t)
    if w is None:
        return True                        # a strong edit verb: remove, replace, rephrase, don't ...
    if w.group("verb").lower() in _PRONOUN_OK and re.match(r"\s+(?:it|this|that)\b", t[w.end():], re.I):
        return True                        # "address it to the principal", "make it warmer"
    return bool(_ANCHOR.search(head))


def _object_is_draft(t: str) -> bool:
    """'Shorten it' / 'Simplify' / 'Summarise the letter' / 'Polish it a bit' act on the draft; 'Simplify my life',
    'Summarise the news' and 'Polish my shoes' do not (UIV2-F1)."""
    m = re.match(_LEAD + r"[\w'-]+", t, re.I)
    rest = t[m.end():].strip(" .!?") if m else t
    if not rest or re.match(r"(?:it|this|that)\b", rest, re.I) or _LANGUAGE_OBJECT.match(rest):
        return True
    if _ANCHOR.search(rest) or _REVISE_ANY.search(rest):
        return True
    # only manner words left: "a bit", "more formally", "politely please"
    return bool(re.fullmatch(r"(?:(?:a|bit|little|slightly|much|more|less|please|pls|again|further|now)\b\s*|"
                             r"\w+ly\b\s*)+", rest, re.I))


@dataclass
class TextIntent:
    kind: str
    reasons: list = field(default_factory=list)
    payload: str | None = None        # text to correct / rewrite / expand, when given in the same message
    instruction: str = ""             # the user's request with the payload removed
    targets: dict = field(default_factory=dict)   # {"body": [indices], "roles": [...], "phrases": [...], "global": bool}
    ambiguous: list = field(default_factory=list)   # sentences that may be content or an instruction to URI (L-2)

    @property
    def is_text_task(self):
        return self.kind != NONE

    def to_dict(self):
        return {"kind": self.kind, "reasons": list(self.reasons), "has_payload": self.payload is not None,
                "targets": dict(self.targets)}


# L-2, dictation versus commands. An explicit content marker ("Write: ...", "Type this: ...", "Dictate: ...") makes
# everything after the colon CONTENT, also sentences that start with an action verb: they are written, never done.
# ("Note down" stays a memory action for Core.)
_CONTENT_MARKER = re.compile(_LEAD + r"(?:write|type|write down|dictate|take dictation)(?:\s+(?:this|the following|"
                             r"exactly|it down|this down|down))?\s*:\s*(\S[\s\S]*)$", re.I)


def action_sentences(text: str) -> list:
    """Sentences of `text` that read as an instruction to URI (the same detector Core routing uses)."""
    return [m.group(1).strip() for m in _SENTENCE.finditer(text or "") if _START_ACTION.match(m.group(1))]


def _ambiguous_actions(t: str) -> list:
    """'Write a notice. Send the form by Friday.': a drafting request followed by sentences that start with an action
    verb whose object is not the document. They may be the notice's own words or an instruction to URI: the desk
    asks (L-2). Anything else that makes the request an action (a destination, 'then email it', 'and send it',
    'send it/this') keeps the existing route to Core."""
    sents = [m for m in _SENTENCE.finditer(t)]
    if len(sents) < 2 or not (_DRAFT_NEW.match(sents[0].group(1)) or _DRAFT_WANT.match(sents[0].group(1))):
        return []
    acts = []
    for m in sents[1:]:
        s = m.group(1)
        a = _START_ACTION.match(s)
        if not a:
            continue
        if _DOC_OBJECT.match(s, a.end()) or re.match(r"\s*(?:it|this|that|me)\b", s[a.end():], re.I):
            return []                      # "Send it to the director." is about the document: an action
        if re.match(r"\s*(?:to\s+)?(?:" + _DETERMINERS + r"\s+)?" + _RECIPIENTS + r"\b", s[a.end():], re.I) \
                or re.match(r"\s*(?:to\s+)?[A-Z][a-z]+\b", s[a.end():]):
            return []                      # "Email the principal." names someone to act towards: an action (Codex TI r2 A1)
        acts.append(s.strip())
    if not acts:
        return []
    rest = t
    for s in acts:
        rest = rest.replace(s, " ")
    if _DESTINATION.search(t) or _SEQUENCED.search(t) or _core_only(rest):
        return []
    for m in _COORDINATED.finditer(t):
        if not _content_context(t, m.start()):
            return []
    return acts


def split_payload(text: str):
    """'Correct this: <payload>' / 'Rewrite politely\\n<payload>' / 'Fix "<payload>"'. Returns (instruction, payload)."""
    t = text.strip()
    m = re.match(r"^(.{3,160}?)(?::\s*|\s*\n+\s*|\s+-\s+)(\S[\s\S]*)$", t)
    if m and len(m.group(2).strip()) >= 3:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.{3,160}?)\s+[\"“‘']([\s\S]{3,})[\"”’']\s*[.!]?\s*$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return t, None


def targets_for(instruction: str) -> dict:
    body, roles, phrases = [], [], []
    for m in _PARA_REF.finditer(instruction):
        if m.group(1):
            body.append(_ORDINALS[m.group(1).lower()])
        elif m.group(2):
            body.append(int(m.group(2)) - 1)
    for role, rx in _ROLE_REF.items():
        if rx.search(instruction):
            roles.append(role)
    for m in _PHRASE_SWAP.finditer(instruction):
        p = next((g for g in m.groups() if g), None)
        if p:
            phrases.append(p.strip(" \"'“”‘’"))
    # Explicit parts win. The edit is whole-document only when some clause asks for an edit of the whole ("make it
    # more diplomatic") without naming a part; "keep everything else the same" never widens it.
    # "it" refers back to a part named in an EARLIER clause ("change the first paragraph and make it shorter"); in a
    # clause before any named part it means the document ("make it more diplomatic and shorten the second
    # paragraph"). Explicit whole-document words ("whole", "the letter", "tone") are global wherever they occur.
    is_global = not (body or roles or phrases)
    named_before = False
    for clause in _CLAUSE_SPLIT.split(instruction):
        if not clause or not clause.strip() or _KEEP_REST.search(clause):
            continue
        if _PARA_REF.search(clause) or any(rx.search(clause) for rx in _ROLE_REF.values()) or \
                any(p.lower() in clause.lower() for p in phrases):
            named_before = True
            continue
        if not _EDIT_VERB.search(clause):
            continue
        explicit = _GLOBAL.search(re.sub(r"\b(?:it|isko|isse)\b", " ", clause, flags=re.I))
        if explicit or (_GLOBAL.search(clause) and not named_before):
            is_global = True
    return {"body": sorted(set(body)), "roles": sorted(set(roles)), "phrases": phrases, "global": is_global}


def classify(text: str, *, has_draft: bool, draft_text: str | None = None) -> TextIntent:
    """``draft_text`` (the open draft's current text, optional) lets a correction that reuses the document's own words
    count as anchored (UIV2-F1)."""
    t = (text or "").strip()
    if not t:
        return TextIntent(NONE, ["empty"])
    head = t[:400]
    if has_draft:
        for kind, rx in ((UNDO, _UNDO), (REDO, _REDO), (ORIGINAL, _ORIGINAL), (DISCARD, _DISCARD), (SHOW, _SHOW)):
            if rx.match(t):
                return TextIntent(kind, ["draft_operation"], instruction=t)
    if T.triage(t).kind == T.TRIVIAL:
        return TextIntent(NONE, ["trivial"])
    m = _CONTENT_MARKER.match(t)
    if m and len(m.group(1).strip()) >= 3:
        return TextIntent(CORRECT, ["dictated_content"], payload=m.group(1).strip(), instruction=t)
    ambiguous = _ambiguous_actions(t)
    if ambiguous:
        return TextIntent(DRAFT_NEW, ["ambiguous_action_sentences"], instruction=t, ambiguous=ambiguous)
    if _core_only(t):
        return TextIntent(NONE, ["core_only_request"])
    if _CODE.search(head) and not _DRAFT_NEW.match(t):
        return TextIntent(NONE, ["code_work"])
    if _EXPAND.match(t):
        ins, payload = split_payload(t)
        return TextIntent(EXPAND, ["expand_notes"], payload=payload, instruction=ins)
    if _CORRECT_BARE.match(t) or (_CORRECT.match(t) and not _FOREIGN_OBJECT.search(split_payload(t)[0])):
        ins, payload = split_payload(t)
        if payload is None and has_draft:
            if not _object_is_draft(t):
                return TextIntent(NONE, ["not_the_draft"])     # UIV2-F1: "fix my wifi" is not an edit
            return TextIntent(REVISE, ["correct_active_draft"], instruction=t, targets=targets_for(t))
        return TextIntent(CORRECT, ["correct_text"], payload=payload, instruction=ins)
    if _REWRITE.match(t) and not _FOREIGN_OBJECT.search(split_payload(t)[0]):
        ins, payload = split_payload(t)
        if payload is None and has_draft:
            if not _object_is_draft(t):
                return TextIntent(NONE, ["not_the_draft"])     # UIV2-F1: "summarise the news" is not an edit
            return TextIntent(REVISE, ["rewrite_active_draft"], instruction=t, targets=targets_for(t))
        return TextIntent(REWRITE, ["rewrite_text"], payload=payload, instruction=ins)
    if _DRAFT_NEW.match(t) or _DRAFT_WANT.match(t) or _DRAFT_HINGLISH.search(head):
        if has_draft and _REVISE_START.match(t) and not re.search(r"\b(?:new|another|fresh|separate)\b", head, re.I) \
                and re.match(r"^\s*(?:\w+[,!]?\s+){0,3}(?:make|write|change|add)\s+(?:it|this|the)\b", t, re.I):
            return TextIntent(REVISE, ["edit_phrased_as_create"], instruction=t, targets=targets_for(t))
        ins, payload = split_payload(t)
        return TextIntent(DRAFT_NEW, ["create_document"], payload=payload if payload and len(payload) > 200 else None,
                          instruction=t)
    if has_draft:
        if _FOREIGN_OBJECT.search(head) and not _REVISE_ANY.search(head):
            return TextIntent(NONE, ["foreign_object"])
        question = t.rstrip().endswith("?")
        starts = bool(_REVISE_START.match(t))
        mentions = bool(_REVISE_ANY.search(head)) or bool(_HINGLISH_EDIT.search(head))
        targets = targets_for(t)
        revision_cue = starts or (mentions and (_EDIT_VERB.search(head) or targets["body"] or targets["roles"]
                                         or targets["phrases"]))
        if revision_cue and (not question or mentions or re.search(r"\b(?:it|this)\b", head, re.I)):
            if not re.match(r"^\s*(?:what|why|how|who|when|where|which|is|are|does|do you|did)\b", t, re.I) or mentions:
                if not _anchored(t, draft_text):
                    return TextIntent(NONE, ["unanchored_with_draft"])   # UIV2-F1: ordinary chat, draft untouched
                return TextIntent(REVISE, ["draft_revision"], instruction=t, targets=targets)
    return TextIntent(NONE, ["not_a_text_task"])
