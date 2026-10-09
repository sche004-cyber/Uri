"""Schedule expansion, timezone handling and calendar provenance/refresh (pure, no processes)."""
import copy
from datetime import date, datetime, timedelta, timezone

import pytest

from uri_scheduler import timespec
from uri_scheduler.calendar_store import Calendar, CalendarError, diff

UTC = timezone.utc
IST = timedelta(hours=5, minutes=30)


def u(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


def test_once_is_local_wall_time_in_kolkata():
    occ = timespec.expand({"kind": "once", "at": "2026-11-06T09:00"}, u(2026, 1, 1), u(2027, 1, 1))
    assert len(occ) == 1 and occ[0].key == "once"
    assert occ[0].due_utc == datetime(2026, 11, 6, 3, 30, tzinfo=UTC)      # 09:00 IST = 03:30 UTC


def test_once_rejects_aware_datetime_and_bad_tz():
    with pytest.raises(timespec.ScheduleError):
        timespec.validate({"kind": "once", "at": "2026-11-06T09:00+05:30"})
    with pytest.raises(timespec.ScheduleError):
        timespec.validate({"kind": "once", "at": "2026-11-06T09:00", "tz": "Mars/Olympus"})


def test_daily_weekly_monthly_yearly():
    d = timespec.expand({"kind": "recurring", "freq": "daily", "time": "06:15", "start": "2026-10-10"}, u(2026, 10, 9), u(2026, 10, 13))
    assert [o.key for o in d] == ["2026-10-10T06:15", "2026-10-11T06:15", "2026-10-12T06:15"]
    w = timespec.expand({"kind": "recurring", "freq": "weekly", "weekdays": [0, 4], "time": "10:00", "start": "2026-10-05"},
                        u(2026, 10, 5), u(2026, 10, 20))
    assert [o.key[:10] for o in w] == ["2026-10-05", "2026-10-09", "2026-10-12", "2026-10-16", "2026-10-19"]
    m = timespec.expand({"kind": "recurring", "freq": "monthly", "time": "09:00", "start": "2026-01-31"}, u(2026, 1, 1), u(2026, 6, 30))
    assert [o.key[:10] for o in m] == ["2026-01-31", "2026-03-31", "2026-05-31"]        # months without a 31st skipped
    y = timespec.expand({"kind": "recurring", "freq": "yearly", "time": "09:00", "start": "2024-02-29"}, u(2024, 1, 1), u(2029, 1, 1))
    assert [o.key[:10] for o in y] == ["2024-02-29", "2028-02-29"]


def test_interval_and_end():
    d = timespec.expand({"kind": "recurring", "freq": "daily", "interval": 3, "time": "00:00", "start": "2026-10-01",
                         "end": "2026-10-10"}, u(2026, 9, 1), u(2026, 12, 1))
    assert [o.key[:10] for o in d] == ["2026-10-01", "2026-10-04", "2026-10-07", "2026-10-10"]


def test_dst_zone_gap_is_normalized():
    occ = timespec.expand({"kind": "once", "at": "2026-03-08T02:30", "tz": "America/New_York"}, u(2026, 1, 1), u(2027, 1, 1))
    assert occ[0].due_utc == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)        # nonexistent 02:30 -> 03:30 EDT


def test_calendar_relative_two_days_before_in_ist():
    cal = Calendar.default()
    spec = {"kind": "calendar_relative", "calendar": "in_festivals", "selection": ["diwali", "holi"], "offset_days": -2,
            "time": "09:00"}
    occ = timespec.expand(spec, u(2026, 1, 1), u(2028, 1, 1), cal)
    keys = {o.key: o for o in occ}
    assert set(keys) == {"diwali:2026", "diwali:2027", "holi:2026", "holi:2027"}
    d26 = keys["diwali:2026"]
    assert d26.meta["festival_date"] == "2026-11-08" and d26.meta["due_local"] == "2026-11-06T09:00"
    assert d26.due_utc == datetime(2026, 11, 6, 3, 30, tzinfo=UTC)
    assert d26.deadline_utc == datetime(2026, 11, 7, 18, 30, tzinfo=UTC)    # festival day starts 00:00 IST
    assert keys["diwali:2027"].meta["festival_date"] == "2027-10-29"        # not the same Gregorian date each year


def test_calendar_unverified_records_never_expand():
    cal = Calendar.default()
    spec = {"kind": "calendar_relative", "calendar": "in_festivals", "selection": ["losoong_namsoong", "lhabab_duechen"],
            "offset_days": -2}
    assert timespec.expand(spec, u(2026, 1, 1), u(2028, 1, 1), cal) == []
    raw = cal.confirm("in_festivals", "lhabab_duechen", 2026, confirmed_by="owner", note="checked gazette")
    assert raw["version"].endswith("+confirm")
    assert [o.key for o in timespec.expand(spec, u(2026, 1, 1), u(2028, 1, 1), cal)] == ["lhabab_duechen:2026"]


def test_calendar_sources_are_cited_and_validated():
    cal = Calendar.default()
    for e in cal.all_events("in_festivals", include_unschedulable=True):
        src = cal.source("in_festivals", e.source_id)
        assert src and src["url"].startswith("https://") and src["retrieved_at"]
    bad = copy.deepcopy(cal.raw("in_festivals"))
    bad["festivals"][0]["occurrences"][0]["source"] = "nowhere"
    with pytest.raises(CalendarError):
        cal.put(bad)


def test_calendar_diff_reports_moves_and_withdrawals():
    cal = Calendar.default()
    old = cal.raw("in_festivals")
    new = copy.deepcopy(old)
    for f in new["festivals"]:
        if f["festival_key"] == "diwali":
            f["occurrences"][0]["start"] = "2026-11-09"
        if f["festival_key"] == "holi":
            f["occurrences"] = [o for o in f["occurrences"] if o["year"] != 2027]
    d = diff(old, new)
    assert d["moved"] == [(("diwali", 2026), "2026-11-08", "2026-11-09")]
    assert d["withdrawn"] == [("holi", 2027)]


def test_describe_is_plain_language():
    s = timespec.describe({"kind": "calendar_relative", "calendar": "in_festivals", "selection": ["diwali"], "offset_days": -2,
                           "time": "09:00"})
    assert s.startswith("2 calendar days before") and "Asia/Kolkata" in s


def test_r4_hourly_is_anchored_and_crosses_days():
    occ = timespec.expand({"kind": "recurring", "freq": "hourly", "interval": 5, "time": "09:30", "start": "2026-10-10"},
                          u(2026, 10, 9), u(2026, 10, 11, 12))
    keys = [o.key for o in occ]
    assert keys[:5] == ["2026-10-10T09:30", "2026-10-10T14:30", "2026-10-10T19:30", "2026-10-11T00:30", "2026-10-11T05:30"]
    assert all(k >= "2026-10-10T09:30" for k in keys)
