"""Surfaces produced by the REAL scheduler A2UI host (in-process engine, scripted harness) for the Dart widget tests.

  python tests/a2ui/make_surface_fixtures.py -> tests/a2ui/fixtures/surfaces.json

Recorded: the proposal surface for the owner's request, the reply to a revise action, and the calendar surface. The
Dart test replays them through a fake HTTP client and checks the action messages it sends (digest, bound values).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "scheduler"))

import tempfile  # noqa: E402

from test_engine import Clock, FakeHarness  # noqa: E402

from uri_operational_intelligence.schedule_intent import interpret  # noqa: E402
from uri_scheduler.a2ui_host import SchedulerA2ui  # noqa: E402
from uri_scheduler.engine import Scheduler  # noqa: E402

OWNER_TEXT = ("URI, schedule Claude to create a festival GIF two days before each major Indian festival and bring it to me "
              "for approval.")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        s = Scheduler(Path(tmp) / "state", harness=FakeHarness(), now_fn=Clock("2026-10-09T10:00:00+05:30")).start()
        try:
            host = SchedulerA2ui(s, "owner")
            handoff = interpret(OWNER_TEXT)
            prop = host.propose_from_request(handoff["request"])
            msgs = prop["messages"]
            model = msgs[2]["updateDataModel"]["value"]
            revise_ctx = {"surface_digest": model["bound"]["surface"]["digest"], "selection": ["diwali", "holi"],
                          "time": "09:00", "offset_days": "2"}
            revised = host.action({"name": "scheduler.revise_proposal", "surfaceId": prop["surface_id"],
                                   "sourceComponentId": "revise", "timestamp": "2026-10-09T04:30:00Z", "context": revise_ctx})
            cal = host.calendar_surface()
        finally:
            s.close()
    out = {"handoff": handoff, "proposal": prop, "revise_context": revise_ctx, "revised": revised, "calendar": cal}
    p = ROOT / "tests" / "a2ui" / "fixtures" / "surfaces.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print("->", p)


if __name__ == "__main__":
    main()
