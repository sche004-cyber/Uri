"""Recent files (plan §5 `recent.py`): `<state>/recent.json` with path, kind, last opened and size only.
No content and no hash. A recent entry is not a grant: re-opening one goes through the picker again."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

MAX_ITEMS = 50
KINDS = ("xlsx", "docx", "pptx", "pdf")


class Recent:
    def __init__(self, state: Path):
        self.file = Path(state) / "recent.json"
        self._lock = threading.Lock()

    def _load(self) -> list:
        try:
            items = json.loads(self.file.read_text(encoding="utf-8"))
            return [i for i in items if isinstance(i, dict) and i.get("kind") in KINDS][:MAX_ITEMS]
        except (OSError, ValueError):
            return []

    def _save(self, items: list):
        tmp = self.file.with_name(f"recent.json.{uuid.uuid4().hex[:6]}.tmp")
        tmp.write_text(json.dumps(items), encoding="utf-8")
        os.replace(tmp, self.file)

    def add(self, path: Path, kind: str, size: int):
        with self._lock:
            items = [i for i in self._load() if os.path.normcase(i["path"]) != os.path.normcase(str(path))]
            items.insert(0, {"path": str(path), "kind": kind, "last_opened": time.time(), "size": int(size)})
            self._save(items[:MAX_ITEMS])

    def listing(self) -> dict:
        return {"items": self._load()}

    def remove(self, path) -> dict:
        with self._lock:
            items = [i for i in self._load() if os.path.normcase(i["path"]) != os.path.normcase(str(path))]
            self._save(items)
        return {"items": items}

    def clear(self) -> dict:
        with self._lock:
            self._save([])
        return {"items": []}
