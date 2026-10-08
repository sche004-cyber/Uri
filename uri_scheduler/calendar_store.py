"""Versioned event calendars (festivals) with provenance.

A calendar file (`uri.scheduler.calendar.v1`) lists festivals; each festival has dated occurrences, each tied to a
source record (official notification, transcription, aggregator) and a status:

  published    taken from a cited notification; schedulable
  unverified   conflicting or weak source; NEVER schedulable until the owner confirms it
  withdrawn    removed by a refresh; any scheduled occurrence for it is cancelled by the engine

`diff(old, new)` reports added / moved / withdrawn occurrences so a refresh moves existing scheduled work instead of
duplicating it. A festival listed by several sources (national + state) is one festival key: dedup happens by key.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SCHEMA = "uri.scheduler.calendar.v1"
DATA_DIR = Path(__file__).resolve().parent / "data"
STATUSES = ("published", "unverified", "withdrawn")


class CalendarError(ValueError):
    pass


@dataclass(frozen=True)
class CalendarEvent:
    calendar_id: str
    festival_key: str
    name: str
    category: str
    regions: tuple
    start: date
    status: str
    source_id: str
    version: str
    greeting_appropriate: bool

    @property
    def record_id(self) -> str:
        return f"{self.calendar_id}/{self.festival_key}/{self.start.year}"


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_calendar(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise CalendarError("BAD_SCHEMA")
    for k in ("calendar_id", "version", "sources", "festivals"):
        if k not in data:
            raise CalendarError(f"MISSING:{k}")
    sources = {s["id"] for s in data["sources"]}
    seen = set()
    for f in data["festivals"]:
        key = f.get("festival_key")
        if not key or key in seen:
            raise CalendarError(f"DUPLICATE_OR_EMPTY_KEY:{key}")
        seen.add(key)
        years = set()
        for o in f.get("occurrences", []):
            date.fromisoformat(o["start"])
            if o.get("status") not in STATUSES:
                raise CalendarError(f"BAD_STATUS:{key}")
            if o.get("source") not in sources:
                raise CalendarError(f"UNKNOWN_SOURCE:{key}:{o.get('source')}")
            if o["year"] != int(o["start"][:4]) or o["year"] in years:
                raise CalendarError(f"BAD_YEAR:{key}:{o['year']}")
            years.add(o["year"])
    return data


class Calendar:
    """One or more loaded calendars. `events(calendar_id, selection)` yields only schedulable (published) events."""

    def __init__(self):
        self._data: dict[str, dict] = {}

    @staticmethod
    def load_file(path) -> dict:
        return validate_calendar(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def default(cls) -> "Calendar":
        c = cls()
        for p in sorted(DATA_DIR.glob("*.json")):
            c.put(cls.load_file(p))
        return c

    def put(self, data: dict):
        validate_calendar(data)
        self._data[data["calendar_id"]] = data

    def raw(self, calendar_id) -> dict:
        if calendar_id not in self._data:
            raise CalendarError(f"UNKNOWN_CALENDAR:{calendar_id}")
        return self._data[calendar_id]

    def digest(self, calendar_id) -> str:
        return _sha(self.raw(calendar_id))

    def version(self, calendar_id) -> str:
        return self.raw(calendar_id)["version"]

    def all_events(self, calendar_id, include_unschedulable=False):
        d = self.raw(calendar_id)
        for f in d["festivals"]:
            for o in f.get("occurrences", []):
                if not include_unschedulable and o["status"] != "published":
                    continue
                yield CalendarEvent(d["calendar_id"], f["festival_key"], f["name"], f.get("category", ""),
                                    tuple(f.get("regions", ())), date.fromisoformat(o["start"]), o["status"], o["source"],
                                    d["version"], bool(f.get("greeting_appropriate", True)))

    def events(self, calendar_id, selection):
        sel = set(selection)
        return [e for e in self.all_events(calendar_id) if e.festival_key in sel]

    def festivals(self, calendar_id):
        return [{"festival_key": f["festival_key"], "name": f["name"], "category": f.get("category"),
                 "regions": f.get("regions", []), "greeting_appropriate": f.get("greeting_appropriate", True)}
                for f in self.raw(calendar_id)["festivals"]]

    def source(self, calendar_id, source_id) -> dict | None:
        return next((s for s in self.raw(calendar_id)["sources"] if s["id"] == source_id), None)

    def confirm(self, calendar_id, festival_key, year, *, confirmed_by, note="") -> dict:
        """Owner confirmation of an unverified record: status -> published, version bumped, confirmation recorded."""
        d = json.loads(json.dumps(self.raw(calendar_id)))
        for f in d["festivals"]:
            if f["festival_key"] != festival_key:
                continue
            for o in f["occurrences"]:
                if o["year"] == year:
                    o["status"] = "published"
                    o["confirmed_by"] = confirmed_by
                    o["confirmation_note"] = note
                    d["version"] = d["version"] + "+confirm"
                    self.put(d)
                    return d
        raise CalendarError(f"NO_SUCH_RECORD:{festival_key}:{year}")


def diff(old: dict, new: dict) -> dict:
    """Occurrence-level changes between two versions of the same calendar (published records only)."""
    def index(d):
        out = {}
        for f in d["festivals"]:
            for o in f.get("occurrences", []):
                if o["status"] == "published":
                    out[(f["festival_key"], o["year"])] = o["start"]
        return out
    a, b = index(old), index(new)
    return {"added": sorted(k for k in b if k not in a),
            "withdrawn": sorted(k for k in a if k not in b),
            "moved": sorted((k, a[k], b[k]) for k in a if k in b and a[k] != b[k])}
