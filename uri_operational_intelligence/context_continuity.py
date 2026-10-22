"""Context continuity for the answer channel: conversations longer than the Brain's context window (Lifecycle V3.1
amendment, 2026-10-21).

The default Brain profile has a 32K window with Vision; a bigger window needs a model reload and (with Vision) is not
a qualified profile. So long conversations continue by *compaction and rollover*, never by reloading:

* Every turn is written to a durable transcript (SQLite under the client's ``control/oi`` state) BEFORE the Brain is
  asked, and the answer after. A worker crash leaves the turn marked interrupted, never lost; a restarted worker
  continues from the transcript (closes CONTEXT-1: history used to live only in worker memory).
* Before each request the prompt is budgeted in tokens: system + memory evidence + current turn (+ images) + the
  answer's reserved ``max_tokens`` + a safety margin, against the running profile's ``n_ctx``. Tokens are estimated
  per character run (words, digits, symbols, non-ASCII), fitted to the Runtime v1 tokenizer (``llama-tokenize`` on
  prose, code, JSON, logs, hex ids, base64, Chinese: estimate/actual 0.93-1.74), times 1.08, times a factor
  calibrated on the server's own measured ``prompt_n`` / ``cache_n`` that can only raise the estimate (persisted).
  No extra model call and no tokenizer at run time.
* While everything fits, the history is sent verbatim (append-only, so the server's prompt cache reuses the prefix).
  When it would not, a *rollover* advances a compaction boundary with hysteresis (a checkpoint record is written
  first): turns before the boundary are replaced by a deterministic, stable block holding PINNED turns (instructions,
  decisions, approvals, draft/action evidence) verbatim or, under pressure, as excerpts and an index - and a one-line
  digest of every other turn. Turns after the boundary stay verbatim. Earlier turns relevant to the current request
  are retrieved from the transcript (lexical, IDF-weighted) and placed just before it.
* Nothing is dropped silently: every compose returns a report (also attached to the answer metrics) that counts
  what was compacted, excerpted, indexed or omitted; originals stay in the transcript and remain retrievable.

Vision: images are counted in the budget when a message carries them; the profile (and the mmproj) is never changed.

Boundary: answer-channel context only; no authority. Data stays on this computer, in the client's state root.
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from pathlib import Path

MARGIN_TOKENS = 512          # template/role overhead slack on top of the per-message overhead
MSG_OVERHEAD_TOKENS = 8      # chat template tokens per message (role tags, separators)
TOKEN_SAFETY = 1.08         # the fitted estimate is >= 0.93 x actual on every measured content type
FACTOR_BOUNDS = (1.0, 2.0)   # calibration only raises the estimate: one prose-heavy session never makes a dense
                             # (ids, base64) turn look smaller than it is
IMAGE_TOKENS = 1536          # per image when the caller does not know (Qwen VL ~1.3K for 1024x1024)
VERBATIM_HIGH = 0.55         # rollover when verbatim history would exceed this share of the free budget
VERBATIM_LOW = 0.30          # ... and keep only this share after the rollover (hysteresis: rare prefix changes)
VERBATIM_CAP = 0.25          # one recent turn above this share of the free budget is shown as an excerpt
INTERRUPTED_NOTE_TOKENS = 20  # "[This request was interrupted before URI answered.]"
COMPACT_SHARE = 0.30         # pinned + digest block
RETRIEVE_SHARE = 0.12        # relevant earlier turns for the current request
PIN_EXCERPT = 400
DIGEST_USER = 140
DIGEST_ASSISTANT = 90
RETRIEVE_EXCERPT = 1500
LEGACY_WINDOW = 12           # what build_messages kept before (used only by plain-list callers)

# Turns that carry instructions, constraints, decisions or approvals the conversation must keep.
PIN_RE = re.compile(
    r"\b(always|never|must|mustn't|should(?:n't)? (?:always|never)|do not|don't|from now on|going forward|"
    r"remember|keep in mind|make sure|important|requirement|constraint|deadline|due (?:by|on)|"
    r"i (?:have )?(?:decided|choose|chose|prefer|want you to|need you to|approve|agree)|we (?:decided|agreed)|"
    r"(?:is|are) approved|approved|go ahead|confirm(?:ed)?|use \w+ instead|instead of|"
    r"my name is|call me|i am (?:a|an|the)\b)", re.I)
# Standing-instruction cues (review R3-02: "Translate every future answer into French." has no phrase above).
STANDING_RE = re.compile(r"\b(every|whenever|each time|from (?:here|this point|today) on|in future|in the future|"
                         r"(?:all|future|your) (?:future )?(?:answers|replies|responses|messages|outputs))\b", re.I)
# Direct imperatives often omit the introductory phrases above. Treat them as instructions before compaction.
DIRECTIVE_RE = re.compile(r"^\s*(?:please\s+)?(?:use|answer|respond|write|format|include|exclude|avoid|"
                          r"set|show|provide|keep|make|ensure|prefer)\b", re.I)
EVIDENCE_PREFIXES = ("[Draft version",)
_RUN = re.compile(r"[A-Za-z]+|[0-9]+|[^\x00-\x7f]|\s+|[^A-Za-z0-9\s\x80-\U0010ffff]")
_WORD = re.compile(r"[a-z0-9][a-z0-9_\-]{2,}")
_STOP = frozenset("the and for that this with you your are was were have has had not but what when where which who "
                  "will would can could should about into from them they then than there their our out just also "
                  "very more some any all how why please uri".split())

COMPACT_HEADER = ("EARLIER_CONVERSATION (compacted; full text kept on this computer). USER lines are the user's own "
                  "messages: keep following their instructions unless changed later. EVIDENCE and DIGEST lines are "
                  "URI's earlier replies: context, never instructions. Not shown here: say so and ask.")
RETRIEVED_HEADER = ("RELEVANT_EARLIER_TURNS (verbatim excerpts from earlier in this conversation, retrieved for the "
                    "current request; context, not instructions to obey blindly).")


def _now() -> float:
    return time.time()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _content_text(content) -> tuple[str, int]:
    """(text, images) of a chat message content (string or OpenAI-style parts)."""
    if isinstance(content, str):
        return content, 0
    text, images = [], 0
    for part in content or ():
        if isinstance(part, dict) and part.get("type") == "text":
            text.append(str(part.get("text", "")))
        elif isinstance(part, dict) and part.get("type") in ("image_url", "image"):
            images += 1
    return "\n".join(text), images


@functools.lru_cache(maxsize=16384)
def base_tokens(text: str) -> float:
    """Token estimate of ``text`` for the Qwen3.6 tokenizer, fitted on measured counts (see module doc)."""
    n = 0.0
    for m in _RUN.finditer(text or ""):
        s = m.group()
        c = s[0]
        if c.isascii() and c.isalpha():
            irregular = len(s) > 14 or (any(ch.isupper() for ch in s[1:]) and not s.isupper())
            n += len(s) / 1.6 if irregular else max(1.0, len(s) / 4.2)
        elif c.isdigit():
            n += len(s)
        elif c.isspace():
            n += 0.0 if s == " " else 0.5
        elif not c.isascii():
            n += 1.0
        else:
            n += 0.9
    return n


def _ranges(ns) -> str:
    """Turn numbers as compact ranges (user turns are every other message, so a gap of 2 continues a range)."""
    out, start, prev = [], None, None
    for n in sorted(ns):
        if prev is not None and n - prev <= 2:
            prev = n
            continue
        if start is not None:
            out.append(f"T{start}" if start == prev else f"T{start}-T{prev}")
        start = prev = n
    if start is not None:
        out.append(f"T{start}" if start == prev else f"T{start}-T{prev}")
    return ", ".join(out)


def classify(role: str, text: str) -> str | None:
    if role == "user" and (PIN_RE.search(text or "") or DIRECTIVE_RE.search(text or "") or
                           STANDING_RE.search(text or "")):
        return "instruction"
    if role == "assistant" and (text or "").startswith(EVIDENCE_PREFIXES):
        return "evidence"
    return None


class TranscriptStore:
    """Durable per-session transcript, compaction checkpoints and the token calibration. Thread-safe."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA busy_timeout=30000")
        with self._lock:
            for stmt in (
                "CREATE TABLE IF NOT EXISTS turns(session TEXT NOT NULL, n INTEGER NOT NULL, role TEXT NOT NULL, "
                "content TEXT NOT NULL, ts REAL NOT NULL, state TEXT NOT NULL, pin TEXT, images INTEGER NOT NULL "
                "DEFAULT 0, prompt_tokens INTEGER, predicted_tokens INTEGER, PRIMARY KEY(session, n))",
                "CREATE TABLE IF NOT EXISTS checkpoints(session TEXT NOT NULL, seq INTEGER NOT NULL, ts REAL NOT "
                "NULL, boundary INTEGER NOT NULL, through_n INTEGER NOT NULL, reason TEXT NOT NULL, report TEXT NOT "
                "NULL, PRIMARY KEY(session, seq))",
                "CREATE TABLE IF NOT EXISTS calib(k TEXT PRIMARY KEY, v REAL NOT NULL)",
            ):
                self.db.execute(stmt)
            # A turn still 'pending' at start-up was cut off by a crash or a stop: it is kept, marked interrupted.
            self.db.execute("UPDATE turns SET state='interrupted' WHERE state='pending'")
        self._rows = {}              # session -> turn rows in order (write-through cache; the table is append-only)

    def _cached(self, session):
        rows = self._rows.get(session)
        if rows is None:
            rows = self._rows[session] = [dict(r) for r in self.db.execute(
                "SELECT * FROM turns WHERE session=? ORDER BY n", (session,))]
        return rows

    def close(self):
        with self._lock:
            self.db.close()

    def begin(self, session: str, user_text: str, images: int = 0) -> int:
        with self._lock:
            n = self._next(session)
            row = {"session": session, "n": n, "role": "user", "content": user_text, "ts": _now(),
                   "state": "pending", "pin": classify("user", user_text), "images": images, "prompt_tokens": None,
                   "predicted_tokens": None}
            self.db.execute("INSERT INTO turns(session, n, role, content, ts, state, pin, images) "
                            "VALUES(?,?,?,?,?,?,?,?)", tuple(row[k] for k in ("session", "n", "role", "content",
                                                                              "ts", "state", "pin", "images")))
            self._cached(session).append(row)
            return n

    def finish(self, session: str, n: int, answer_text: str | None, *, interrupted=False) -> int | None:
        with self._lock:
            state = "interrupted" if interrupted else "done"   # F5-04: Core actions/cards end without text
            row = None
            # R1-05: the user turn's state and the answer row commit together, or neither does (a crash between
            # them must leave the turn pending, i.e. interrupted at the next start, never 'done' without its answer)
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("UPDATE turns SET state=? WHERE session=? AND n=?", (state, session, n))
                if answer_text:
                    row = {"session": session, "n": self._next(session), "role": "assistant",
                           "content": answer_text, "ts": _now(), "state": "done",
                           "pin": classify("assistant", answer_text), "images": 0, "prompt_tokens": None,
                           "predicted_tokens": None}
                    self.db.execute("INSERT INTO turns(session, n, role, content, ts, state, pin) "
                                    "VALUES(?,?,?,?,?,?,?)",
                                    tuple(row[k] for k in ("session", "n", "role", "content", "ts", "state", "pin")))
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            for r in self._cached(session):
                if r["n"] == n:
                    r["state"] = state
            if row is None:
                return None
            self._cached(session).append(row)
            return row["n"]

    def _next(self, session):
        rows = self._cached(session)
        return (rows[-1]["n"] if rows else 0) + 1

    def turns(self, session: str, *, include_pending=False) -> list[dict]:
        with self._lock:
            rows = self._cached(session)
            return list(rows) if include_pending else [r for r in rows if r["state"] != "pending"]

    def recent_messages(self, session: str, limit: int) -> list[dict]:
        with self._lock:
            rows = self.db.execute("SELECT role, content FROM turns WHERE session=? AND state<>'pending' "
                                   "ORDER BY n DESC LIMIT ?", (session, limit)).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def boundary(self, session: str) -> int:
        with self._lock:
            r = self.db.execute("SELECT boundary FROM checkpoints WHERE session=? ORDER BY seq DESC LIMIT 1",
                                (session,)).fetchone()
            return r["boundary"] if r else 0

    def checkpoint(self, session: str, boundary: int, through_n: int, reason: str, report: dict) -> int:
        with self._lock:
            r = self.db.execute("SELECT MAX(seq) s FROM checkpoints WHERE session=?", (session,)).fetchone()
            seq = (r["s"] or 0) + 1
            self.db.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?)",
                            (session, seq, _now(), boundary, through_n, reason, json.dumps(report, sort_keys=True)))
            return seq

    def checkpoints(self, session: str) -> list[dict]:
        with self._lock:
            return [{**dict(r), "report": json.loads(r["report"])} for r in self.db.execute(
                "SELECT * FROM checkpoints WHERE session=? ORDER BY seq", (session,))]

    def observe(self, session: str, n: int | None, prompt_tokens: int, predicted_tokens: int):
        if n is None:
            return
        with self._lock:
            self.db.execute("UPDATE turns SET prompt_tokens=?, predicted_tokens=? WHERE session=? AND n=?",
                            (prompt_tokens, predicted_tokens, session, n))
            for r in self._cached(session):
                if r["n"] == n:
                    r["prompt_tokens"], r["predicted_tokens"] = prompt_tokens, predicted_tokens

    def get_calib(self, k: str, default: float) -> float:
        with self._lock:
            r = self.db.execute("SELECT v FROM calib WHERE k=?", (k,)).fetchone()
            return r["v"] if r else default

    def set_calib(self, k: str, v: float):
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO calib VALUES(?,?)", (k, float(v)))

    def forget(self, session: str):
        with self._lock:
            self.db.execute("DELETE FROM turns WHERE session=?", (session,))
            self._rows.pop(session, None)
            self.db.execute("DELETE FROM checkpoints WHERE session=?", (session,))


class ContextManager:
    """Composes the answer-channel history for one session under the running profile's context window."""

    def __init__(self, store: TranscriptStore, context_window, *, image_tokens: int = IMAGE_TOKENS):
        self.store = store
        self.context_window = context_window if callable(context_window) else (lambda: int(context_window))
        self.image_tokens = image_tokens
        self._last = {}              # session -> (base tokens sent, user turn n, images, messages) for calibration
        self._force = set()          # sessions whose next compose must roll over (measured near-overflow)
        self._factor = store.get_calib("token_factor", 1.0)
        self._words = {}             # (session, n) -> word set; turn content never changes once written

    # ---- tokens -------------------------------------------------------------------------------------------
    @property
    def token_factor(self) -> float:
        return self._factor

    def tokens(self, text: str, images: int = 0) -> int:
        return int(math.ceil(base_tokens(text) * self._factor * TOKEN_SAFETY)) + MSG_OVERHEAD_TOKENS +             images * self.image_tokens

    def _row_tokens(self, t) -> int:
        b = t.get("_base")
        if b is None:
            b = t["_base"] = base_tokens(t["content"])      # turn content never changes once written
        note = INTERRUPTED_NOTE_TOKENS if t["role"] == "user" and t["state"] == "interrupted" else 0
        return int(math.ceil(b * self._factor * TOKEN_SAFETY)) + MSG_OVERHEAD_TOKENS + note

    def messages_tokens(self, messages) -> int:
        total = 0
        for m in messages:
            text, images = _content_text(m.get("content"))
            total += self.tokens(text, images)
        return total

    def observe(self, session: str, metrics: dict):
        """Feed the server's measured usage back: calibrates the estimate factor and forces a rollover when the
        real prompt came close to the window (the estimate was too optimistic for this content)."""
        prompt = int(metrics.get("prompt_n") or 0) + int(metrics.get("cache_n") or 0)
        predicted = int(metrics.get("predicted_n") or 0)
        sent = self._last.get(session)
        if not prompt or not sent:
            return
        base, n_user, images, n_msgs = sent
        self.store.observe(session, n_user, prompt, predicted)
        text_tokens = prompt - images * self.image_tokens - n_msgs * MSG_OVERHEAD_TOKENS
        if text_tokens > 0 and base > 0:
            obs = min(max(text_tokens / base, FACTOR_BOUNDS[0]), FACTOR_BOUNDS[1])
            cur = self._factor
            # Rise fast when the content is denser than estimated, fall back slowly (never below 1.0).
            alpha = 0.6 if obs > cur else 0.2
            self._factor = max(FACTOR_BOUNDS[0], cur + alpha * (obs - cur))
            self.store.set_calib("token_factor", self._factor)
        if prompt + predicted >= 0.85 * self.context_window():
            self._force.add(session)

    # ---- composing ----------------------------------------------------------------------------------------
    def history(self, session: str) -> "ComposedHistory":
        return ComposedHistory(self, session)

    def compose(self, session: str, *, fixed_messages: list, reserve_tokens: int, query: str = "",
                images: int = 0, force_rollover: bool = False) -> tuple[list, dict]:
        """History messages to place between the fixed prefix (system, memory evidence) and the current turn."""
        n_ctx = int(self.context_window())
        fixed = self.messages_tokens(fixed_messages) + images * self.image_tokens
        free = n_ctx - reserve_tokens - MARGIN_TOKENS - fixed
        turns = self.store.turns(session)
        rep = {"n_ctx": n_ctx, "reserve_tokens": reserve_tokens, "fixed_tokens": fixed, "free_tokens": free,
               "turns_total": len(turns), "token_factor": round(self._factor, 3), "rollover": False,
               "compacted_through": 0, "pinned_verbatim": 0, "pinned_excerpt": 0, "pinned_indexed": 0,
               "pinned_omitted": 0, "digest_lines": 0, "digest_omitted": 0, "retrieved": [], "verbatim_turns": 0,
               "recent_omitted": 0, "recent_pinned_omitted": 0, "history_tokens": 0,
               "interrupted_turns": sum(1 for t in turns if t["state"] == "interrupted")}
        if free <= 0:
            rep["status"] = "CURRENT_TURN_TOO_LARGE"
            rep["history_omitted"] = len(turns)
            return [], rep
        force = force_rollover or session in self._force
        self._force.discard(session)
        boundary = min(self.store.boundary(session), len(turns))
        idx = {t["n"]: i for i, t in enumerate(turns)}
        b = idx.get(boundary + 1, len(turns)) if boundary else 0     # index of the first verbatim turn
        cost = [self._row_tokens(t) for t in turns]
        verbatim_cost = sum(cost[b:])
        if b == 0 and verbatim_cost <= VERBATIM_HIGH * free and not force:
            msgs = self._verbatim(turns)
            total = self.messages_tokens(msgs)
            if total <= free:                       # F5-05: measured after merging and notes, like every path
                rep.update(status="VERBATIM", verbatim_turns=len(turns), history_tokens=total)
                return msgs, rep
            force = True                            # fall through to a rollover
        if verbatim_cost > VERBATIM_HIGH * free or force:
            # Rollover: keep only the newest turns that fit VERBATIM_LOW of the free budget, starting at a user turn.
            keep, nb = 0, len(turns)
            for i in range(len(turns) - 1, -1, -1):
                if keep + cost[i] > VERBATIM_LOW * free and nb < len(turns):
                    break
                keep += cost[i]
                nb = i
            while nb < len(turns) and turns[nb]["role"] != "user":
                nb += 1
            if force and nb <= b and b < len(turns):
                nb = min(len(turns), b + max(1, (len(turns) - b) // 2))
                while nb < len(turns) and turns[nb]["role"] != "user":
                    nb += 1
            if nb > b:
                b = nb
                rep["rollover"] = True
        old, recent = turns[:b], turns[b:]
        block, crep = self._compact(old, COMPACT_SHARE * free)
        rep.update(crep)
        rep["compacted_through"] = old[-1]["n"] if old else 0
        retrieved, rtoks = self._retrieve(old, query, RETRIEVE_SHARE * free, crep["_verbatim_ns"])
        rep["retrieved"] = [t["n"] for t in retrieved]
        rep.pop("_verbatim_ns", None)

        def reported_block():
            older = sum(rep[k] for k in ("pinned_omitted", "user_omitted", "evidence_omitted", "digest_omitted"))
            newer = rep["recent_omitted"]
            if not older and not newer:
                return block
            notice = f"({older} older, {newer} recent turns stored but not shown"
            if rep["omitted_user_turns"]:
                notice += "; user turns not shown: " + _ranges(rep["omitted_user_turns"])
            if rep["recent_pinned_omitted"]:
                notice += f"; {rep['recent_pinned_omitted']} recent pinned omitted"
            notice += "; ask if needed.)"
            return block + "\n" + notice if block else notice

        msgs = []
        prefix = reported_block()
        if prefix:
            msgs += [{"role": "user", "content": prefix}, {"role": "assistant", "content": "Acknowledged."}]
        msgs += self._verbatim(recent, cap=self._cap(free), rep=rep)
        if retrieved:
            text = RETRIEVED_HEADER + "\n" + "\n".join(
                f"[T{t['n']} {t['role']}] {t['content'][:RETRIEVE_EXCERPT]}" for t in retrieved)
            msgs += [{"role": "user", "content": text}, {"role": "assistant", "content": "Acknowledged."}]
        total = self.messages_tokens(msgs)
        rep.update(status="COMPACTED", verbatim_turns=len(recent), history_tokens=total)
        if total > free:            # safety net: never send a prompt the estimate says cannot fit
            while total > free and len(recent) > 1:
                before = recent
                recent = recent[1:]
                while recent and recent[0]["role"] != "user":
                    recent = recent[1:]
                removed = before[:len(before) - len(recent)]
                rep["recent_omitted"] += len(removed)
                rep["omitted_user_turns"] = sorted(set(rep["omitted_user_turns"]) |
                                                   {t["n"] for t in removed if t["role"] == "user"})
                rep["recent_pinned_omitted"] += sum(bool(t["pin"]) for t in removed)
                prefix = reported_block()
                msgs = ([{"role": "user", "content": prefix}, {"role": "assistant", "content": "Acknowledged."}]
                        if prefix else []) + self._verbatim(recent, cap=self._cap(free), rep=rep)
                total = self.messages_tokens(msgs)
                rep["verbatim_turns"] = len(recent)
                rep["retrieved"] = []
            rep["history_tokens"] = total
            if total > free:
                rep["status"] = "COMPACTED_OVER_BUDGET"
        if rep["rollover"]:
            rep["checkpoint"] = self.store.checkpoint(session, rep["compacted_through"],
                                                      turns[-1]["n"] if turns else 0,
                                                      "forced" if force else "budget", rep)
        return msgs, rep

    def _cap(self, free) -> int:
        return max(64, int(VERBATIM_CAP * free))

    def _verbatim(self, turns, cap: int | None = None, rep: dict | None = None) -> list:
        """Recent turns as chat messages. A single turn above ``cap`` tokens (e.g. a request refused as too large,
        FB R1-05) is shown as an excerpt with a note; its full text stays in the transcript."""
        msgs = []
        for t in turns:
            content = t["content"]
            if cap is not None and self._row_tokens(t) > cap:
                keep = int(len(content) * cap / max(1, self._row_tokens(t))) // 2
                content = content[:keep] + (f"\n[T{t['n']} is longer than fits here; shortened. The full text is "
                                            f"stored on this computer.]")
                if rep is not None:
                    rep["recent_excerpted"] = rep.get("recent_excerpted", 0) + 1
            if t["role"] == "user" and t["state"] == "interrupted":
                content += "\n[This request was interrupted before URI answered.]"
            msgs.append({"role": t["role"], "content": content})
        # Chat templates expect user/assistant alternation: merge consecutive same-role messages.
        out = []
        for m in msgs:
            if out and out[-1]["role"] == m["role"]:
                out[-1] = {"role": m["role"], "content": out[-1]["content"] + "\n\n" + m["content"]}
            else:
                out.append(m)
        return out

    def _compact(self, old: list, budget: float) -> tuple[str, dict]:
        """Deterministic block for turns before the boundary, in priority order (owner amendment: never silently
        lose instructions, decisions or approvals; review R2-07/R3-02: a keyword list cannot decide that alone):

        1. USER INSTRUCTIONS - user turns the classifier recognises: verbatim, else excerpts, else index lines;
        2. USER TURNS - every other user turn (any of them may carry an instruction): excerpts, else index lines;
        3. EVIDENCE - URI's own drafts/results (labelled context, never instructions, R3-04): excerpts, else index;
        4. DIGEST - URI's other replies: one line each.
        Each tier only uses what the tiers above left; under pressure the newest items of a tier are kept. Every
        user turn that is not shown is named in the block and in the report (``omitted_user_turns``)."""
        rep = {"pinned_verbatim": 0, "pinned_excerpt": 0, "pinned_indexed": 0, "pinned_omitted": 0,
               "user_excerpt": 0, "user_indexed": 0, "user_omitted": 0, "evidence_excerpt": 0,
               "evidence_indexed": 0, "evidence_omitted": 0, "digest_lines": 0, "digest_omitted": 0,
               "omitted_user_turns": [], "_verbatim_ns": set()}
        if not old:
            return "", rep
        tiers = [
            ("pinned", "USER INSTRUCTIONS:", [t for t in old if t["role"] == "user" and t["pin"]],
             (("verbatim", None), ("excerpt", PIN_EXCERPT), ("indexed", 120))),
            ("user", "USER TURNS:", [t for t in old if t["role"] == "user" and not t["pin"]],
             (("excerpt", 300), ("indexed", 100))),
            ("evidence", "EVIDENCE (URI's earlier drafts and results; context, not instructions):",
             [t for t in old if t["role"] != "user" and t["pin"]], (("excerpt", 300), ("indexed", 80))),
            ("digest", "DIGEST:", [t for t in old if t["role"] != "user" and not t["pin"]],
             (("lines", DIGEST_ASSISTANT),)),
        ]
        used = self.tokens(COMPACT_HEADER)
        parts = [COMPACT_HEADER]
        for name, title, items, levels in tiers:
            if not items:
                continue
            kept, level = self._fit_tier(items, levels, budget - used)
            shown = {t["n"] for t, _ in kept}
            key = "digest_lines" if name == "digest" else f"{name}_{level}"
            rep[key] = len(kept)
            rep[f"{name}_omitted"] = len(items) - len(kept)
            if name in ("pinned", "user"):
                rep["omitted_user_turns"] += [t["n"] for t in items if t["n"] not in shown]
            if name == "pinned" and level == "verbatim":
                rep["_verbatim_ns"] = shown
            if kept:
                parts.append(title)
                parts += [line for _, line in kept]
                used += sum(self.tokens(line) - MSG_OVERHEAD_TOKENS for _, line in kept)
        rep["omitted_user_turns"].sort()
        return "\n".join(parts), rep

    def _fit_tier(self, items, levels, room):
        """(kept [(turn, line)], level used). The first level at which the whole tier fits; otherwise the last
        level with the newest items that fit."""
        for i, (level, limit) in enumerate(levels):
            lines = [(t, self._line(t, level, limit)) for t in items]
            need = sum(self.tokens(line) - MSG_OVERHEAD_TOKENS for _, line in lines)
            if need <= room:
                return lines, level
            if i == len(levels) - 1:
                kept, acc = [], 0
                for t, line in reversed(lines):
                    tk = self.tokens(line) - MSG_OVERHEAD_TOKENS
                    if acc + tk > room:
                        continue
                    kept.insert(0, (t, line))
                    acc += tk
                return kept, level
        return [], levels[-1][0]

    @staticmethod
    def _line(t, level, limit) -> str:
        who = "user" if t["role"] == "user" else "URI"
        text = t["content"]
        if limit is not None and len(text) > limit:
            text = text[:limit] + (" ...[indexed]" if level == "indexed" else " ...[excerpt]")
        if level != "verbatim":
            text = text.replace("\n", " ")
        flag = " [interrupted]" if t["state"] == "interrupted" else ""
        return f"T{t['n']} {who}: {text}{flag}"

    def _wordset(self, t) -> frozenset:
        k = (t["session"], t["n"])
        ws = self._words.get(k)
        if ws is None:
            ws = self._words[k] = frozenset(_WORD.findall(t["content"].lower()))
        return ws

    def _retrieve(self, old: list, query: str, budget: float, skip: set) -> tuple[list, int]:
        terms = {w for w in _WORD.findall((query or "").lower()) if w not in _STOP}
        if not terms or not old:
            return [], 0
        docs = [(t, self._wordset(t)) for t in old if t["n"] not in skip]
        if not docs:
            return [], 0
        df = {w: sum(1 for _, ws in docs if w in ws) for w in terms}
        scored = []
        for t, ws in docs:
            s = sum(math.log(1 + len(docs) / df[w]) for w in terms & ws if df[w])
            if s > 0:
                scored.append((s, t["n"], t))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        out, used = [], 0
        for _, _, t in scored:
            tk = self.tokens(t["content"][:RETRIEVE_EXCERPT])
            if used + tk > budget:
                continue
            out.append(t)
            used += tk
        out.sort(key=lambda t: t["n"])
        return out, used


class ComposedHistory(list):
    """A session's history for ``answer.build_messages``. As a plain list it is the last LEGACY_WINDOW messages
    (callers that do not know about compaction behave exactly as before); ``compose`` gives the budgeted version."""

    def __init__(self, manager: ContextManager, session: str):
        super().__init__(manager.store.recent_messages(session, LEGACY_WINDOW))
        self.manager, self.session = manager, session
        self.report = None

    def compose(self, *, fixed_messages, reserve_tokens, query="", images=0, force_rollover=False):
        msgs, rep = self.manager.compose(self.session, fixed_messages=fixed_messages, reserve_tokens=reserve_tokens,
                                         query=query, images=images, force_rollover=force_rollover)
        sent = list(fixed_messages) + msgs
        base = sum(base_tokens(_content_text(m.get("content"))[0]) for m in sent)
        pending = [t["n"] for t in self.manager.store.turns(self.session, include_pending=True)[-4:]
                   if t["state"] == "pending"]
        self.manager._last[self.session] = (base, pending[-1] if pending else None, images, len(sent))
        self.report = rep
        return msgs
