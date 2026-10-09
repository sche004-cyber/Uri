"""Schedule specifications -> concrete occurrences.

Three kinds, all expressed in a named IANA timezone (default Asia/Kolkata) and converted to UTC only for storage:

  once               {"kind": "once", "at": "2026-10-09T15:30", "tz": "Asia/Kolkata"}
  recurring          {"kind": "recurring", "freq": "hourly|daily|weekly|monthly|yearly", "interval": 1,
                      "time": "09:00", "start": "2026-10-10", "end": null, "weekdays": [0, 4]}
  calendar_relative  {"kind": "calendar_relative", "calendar": "in_festivals", "selection": ["diwali", ...],
                      "offset_days": -2, "time": "09:00", "tz": "Asia/Kolkata"}

Occurrence identity (`key`) is stable and never derived from the computed instant for calendar-relative schedules:
a festival occurrence is keyed `<festival_key>:<year>`. When a refreshed calendar moves the festival, the SAME
occurrence is moved instead of a second one being created (duplicate prevention across calendar refreshes).

Monthly schedules on a day the month does not have (31st) skip that month (RFC 5545 behaviour), never clamp.
"""
from __future__ import annotations

import calendar as _cal
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import DEFAULT_TZ

KINDS = ("once", "recurring", "calendar_relative")
FREQS = ("hourly", "daily", "weekly", "monthly", "yearly")
MAX_OCCURRENCES_PER_EXPANSION = 5000


class ScheduleError(ValueError):
    pass


@dataclass(frozen=True)
class Occurrence:
    key: str
    due_utc: datetime
    deadline_utc: datetime | None = None
    meta: dict = field(default_factory=dict)


def zone(name) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleError(f"UNKNOWN_TIMEZONE:{name}") from exc


def _parse_time(s) -> time:
    try:
        hh, mm = str(s).split(":")[:2]
        return time(int(hh), int(mm))
    except (ValueError, TypeError) as exc:
        raise ScheduleError(f"BAD_TIME:{s}") from exc


def _parse_date(s) -> date:
    try:
        return date.fromisoformat(str(s))
    except (ValueError, TypeError) as exc:
        raise ScheduleError(f"BAD_DATE:{s}") from exc


def local_to_utc(d: date, t: time, tz: ZoneInfo) -> datetime:
    """Wall-clock local time -> aware UTC. A wall time inside a DST gap is moved forward by the gap (round trip)."""
    naive = datetime.combine(d, t)
    aware = naive.replace(tzinfo=tz, fold=0)
    back = aware.astimezone(timezone.utc).astimezone(tz)
    if back.replace(tzinfo=None) != naive:          # nonexistent local time: use the normalized instant
        aware = back
    return aware.astimezone(timezone.utc)


def to_utc(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ScheduleError("NAIVE_DATETIME")
        return value.astimezone(timezone.utc)
    raise ScheduleError("NOT_A_DATETIME")


def validate(spec: dict) -> dict:
    """Normalize and validate. Returns a new dict; raises ScheduleError with a stable code."""
    if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
        raise ScheduleError("BAD_KIND")
    out = dict(spec)
    out["tz"] = spec.get("tz") or DEFAULT_TZ
    zone(out["tz"])
    kind = spec["kind"]
    if kind == "once":
        try:
            dt = datetime.fromisoformat(str(spec["at"]))
        except (KeyError, ValueError) as exc:
            raise ScheduleError("BAD_AT") from exc
        if dt.tzinfo is not None:
            raise ScheduleError("AT_MUST_BE_LOCAL_WALL_TIME")
        out["at"] = dt.isoformat(timespec="seconds")
    elif kind == "recurring":
        if spec.get("freq") not in FREQS:
            raise ScheduleError("BAD_FREQ")
        interval = int(spec.get("interval", 1))
        if interval < 1 or interval > 1000:
            raise ScheduleError("BAD_INTERVAL")
        out["interval"] = interval
        out["time"] = _parse_time(spec.get("time", "09:00")).strftime("%H:%M")
        out["start"] = _parse_date(spec["start"]).isoformat() if spec.get("start") else None
        if out["start"] is None:
            raise ScheduleError("RECURRING_NEEDS_START")
        out["end"] = _parse_date(spec["end"]).isoformat() if spec.get("end") else None
        wd = spec.get("weekdays")
        if wd is not None:
            if spec["freq"] != "weekly" or not wd or any(int(x) not in range(7) for x in wd):
                raise ScheduleError("BAD_WEEKDAYS")
            out["weekdays"] = sorted({int(x) for x in wd})
    else:
        if not spec.get("calendar"):
            raise ScheduleError("CALENDAR_REQUIRED")
        sel = spec.get("selection")
        if not isinstance(sel, list) or not sel or not all(isinstance(s, str) and s for s in sel):
            raise ScheduleError("SELECTION_REQUIRED")
        out["selection"] = sorted(set(sel))
        out["offset_days"] = int(spec.get("offset_days", 0))
        if abs(out["offset_days"]) > 366:
            raise ScheduleError("BAD_OFFSET")
        out["time"] = _parse_time(spec.get("time", "09:00")).strftime("%H:%M")
    return out


def _recurring_dates(spec, start: date, stop: date):
    """Yield local dates (and hour for hourly) of a recurring rule from its anchor until `stop` (inclusive)."""
    freq, n = spec["freq"], spec["interval"]
    anchor = _parse_date(spec["start"])
    end = _parse_date(spec["end"]) if spec.get("end") else None
    last = min(stop, end) if end else stop
    if freq in ("daily", "hourly"):
        d = anchor
        if start > anchor and freq == "daily":
            d = anchor + timedelta(days=((start - anchor).days // n) * n)
        step = n if freq == "daily" else 1
        while d <= last:
            yield d
            d += timedelta(days=step)
    elif freq == "weekly":
        days = spec.get("weekdays") or [anchor.weekday()]
        week0 = anchor - timedelta(days=anchor.weekday())
        w = week0
        if start > week0:
            w = week0 + timedelta(weeks=((start - week0).days // 7 // n) * n)
        while w <= last:
            for wd in days:
                d = w + timedelta(days=wd)
                if anchor <= d <= last:
                    yield d
            w += timedelta(weeks=n)
    elif freq == "monthly":
        y, m, k = anchor.year, anchor.month, 0
        while True:
            yy, mm = y + (m - 1 + k) // 12, (m - 1 + k) % 12 + 1
            if date(yy, mm, 1) > last:
                return
            if anchor.day <= _cal.monthrange(yy, mm)[1]:
                d = date(yy, mm, anchor.day)
                if d >= anchor:
                    yield d
            k += n
    elif freq == "yearly":
        yy = anchor.year
        while date(yy, 1, 1) <= last:
            try:
                d = date(yy, anchor.month, anchor.day)
            except ValueError:          # Feb 29 in a non-leap year: skipped
                d = None
            if d and d >= anchor:
                yield d
            yy += n


def expand(spec: dict, window_start: datetime, window_end: datetime, calendar=None) -> list[Occurrence]:
    """Occurrences whose due instant lies in [window_start, window_end] (UTC-aware). Calendar-relative occurrences
    whose due instant is in the window are returned with `deadline_utc` = start of the festival day (local)."""
    spec = validate(spec)
    tz = zone(spec["tz"])
    ws, we = to_utc(window_start), to_utc(window_end)
    out: list[Occurrence] = []
    if spec["kind"] == "once":
        at = datetime.fromisoformat(spec["at"])
        due = local_to_utc(at.date(), at.time(), tz)
        if ws <= due <= we:
            out.append(Occurrence("once", due, None, {"local": spec["at"], "tz": spec["tz"]}))
        return out
    if spec["kind"] == "recurring":
        t = _parse_time(spec["time"])
        lo = ws.astimezone(tz).date() - timedelta(days=1)
        hi = we.astimezone(tz).date() + timedelta(days=1)
        if spec["freq"] == "hourly":
            # Anchored at start date + time; the interval runs continuously across day boundaries (review round 4, F4).
            anchor = datetime.combine(_parse_date(spec["start"]), t)
            end_d = _parse_date(spec["end"]) if spec.get("end") else None
            step = timedelta(hours=spec["interval"])
            first_local = ws.astimezone(tz).replace(tzinfo=None) - timedelta(days=1)
            k = max(0, int((first_local - anchor) / step))
            cur = anchor + k * step
            last_local = we.astimezone(tz).replace(tzinfo=None) + timedelta(days=1)
            while cur <= last_local and (end_d is None or cur.date() <= end_d):
                due = local_to_utc(cur.date(), cur.time(), tz)
                if ws <= due <= we:
                    out.append(Occurrence(cur.isoformat(timespec="minutes"), due, None, {"tz": spec["tz"]}))
                if len(out) > MAX_OCCURRENCES_PER_EXPANSION:
                    raise ScheduleError("EXPANSION_TOO_LARGE")
                cur += step
            return out
        for d in _recurring_dates(spec, lo, hi):
            due = local_to_utc(d, t, tz)
            if ws <= due <= we:
                out.append(Occurrence(datetime.combine(d, t).isoformat(timespec="minutes"), due, None, {"tz": spec["tz"]}))
            if len(out) > MAX_OCCURRENCES_PER_EXPANSION:
                raise ScheduleError("EXPANSION_TOO_LARGE")
        return out
    if calendar is None:
        raise ScheduleError("CALENDAR_UNAVAILABLE")
    t = _parse_time(spec["time"])
    for ev in calendar.events(spec["calendar"], spec["selection"]):
        due_date = ev.start + timedelta(days=spec["offset_days"])
        due = local_to_utc(due_date, t, tz)
        if ws <= due <= we:
            out.append(Occurrence(f"{ev.festival_key}:{ev.start.year}", due, local_to_utc(ev.start, time(0, 0), tz),
                                  {"festival_key": ev.festival_key, "festival": ev.name, "festival_date": ev.start.isoformat(),
                                   "calendar_record": ev.record_id, "calendar_version": ev.version, "tz": spec["tz"],
                                   "due_local": datetime.combine(due_date, t).isoformat(timespec="minutes")}))
    return sorted(out, key=lambda o: (o.due_utc, o.key))


def describe(spec: dict) -> str:
    """Plain-language interpretation shown to the owner before activation."""
    s = validate(spec)
    if s["kind"] == "once":
        return f"Once at {s['at'].replace('T', ' ')} ({s['tz']})"
    if s["kind"] == "recurring":
        every = "" if s["interval"] == 1 else f"every {s['interval']} "
        unit = {"hourly": "hour", "daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}[s["freq"]]
        days = ""
        if s.get("weekdays"):
            days = " on " + ", ".join(_cal.day_name[d] for d in s["weekdays"])
        return (f"Every {every}{unit}{days} at {s['time']} ({s['tz']}) from {s['start']}"
                + (f" until {s['end']}" if s.get("end") else ""))
    off = s["offset_days"]
    rel = "on the day of" if off == 0 else (f"{-off} calendar day{'s' if off != -1 else ''} before" if off < 0
                                            else f"{off} calendar day{'s' if off != 1 else ''} after")
    return f"{rel} each selected event in '{s['calendar']}' at {s['time']} ({s['tz']}): {', '.join(s['selection'])}"
