"""Markdown summary of queue_manifest.json for the research report (read-only).

  python model_lab/uri_engine/queue_summary.py
"""
from __future__ import annotations

import json
from pathlib import Path

EVID = Path(__file__).resolve().parent.parent / "evidence" / "uri_engine"


def main():
    m = json.loads((EVID / "queue_manifest.json").read_text(encoding="utf-8"))
    print("| id | group | status | attempts | start | elapsed s | rc | peak VRAM MiB | min free RAM MiB | outputs |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for e in m["entries"]:
        ts = e.get("telemetry_summary") or {}
        outs = ", ".join(Path(o.get("file", o.get("pattern", ""))).name for o in e.get("outputs", []) if o.get("ok"))
        note = e.get("block_reason", "")
        ev = [x for x in e.get("events", []) if x.get("event") != "marked_interrupted_on_startup"]
        if any(x.get("event") == "marked_interrupted_on_startup" for x in e.get("events", [])):
            note = (note + " " if note else "") + f"attempt 1 interrupted by the 14:25 freeze"
        if ev:
            note = (note + " " if note else "") + "; ".join(f"{x['event']}: {x.get('detail', '')}" for x in ev)
        print(f"| {e['id']} | {e.get('group', '')} | {e.get('status', 'pending')} | {e.get('attempts', 0)} | {str(e.get('start', '-'))[11:]} | "
              f"{e.get('elapsed_s', '-')} | {e.get('exit_code', '-')} | {ts.get('peak_vram_mib', '-')} | {ts.get('min_free_ram_mib', '-')} | "
              f"{outs or note or '-'} |")


if __name__ == "__main__":
    main()
