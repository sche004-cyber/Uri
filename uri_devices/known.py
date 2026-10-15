"""Known devices (A1 §A6): `<state>/devices/known.json` with each device's id, name and first/last seen time. No
document data. It tells "installed and known" from "new since URI last looked" (the New badge)."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path


class Known:
    def __init__(self, state: Path):
        self.file = Path(state) / "devices" / "known.json"
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def mark(self, devices: list):
        with self._lock:
            data = self._load()
            first_run = not data
            now = time.time()
            for d in devices:
                rec = data.get(d.id)
                if rec is None:
                    rec = data[d.id] = {"name": d.name[:200], "kind": d.kind, "first_seen": now}
                    d.new = not first_run              # on URI's first look nothing is "new"
                rec["last_seen"] = now
                d.first_seen, d.last_seen = rec["first_seen"], now
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_name(f"known.json.{uuid.uuid4().hex[:6]}.tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.file)
