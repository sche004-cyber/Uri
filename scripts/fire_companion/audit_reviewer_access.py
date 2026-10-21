"""List what each FP-21 reviewer touched, from its preserved transcript.

    python -B scripts/fire_companion/audit_reviewer_access.py docs/companions/fire/v21/evidence/fidelity/p1_raw

For every reviewer<N>_transcript.jsonl.gz: tool-use counts, and every file path
named in a tool input, reduced to its folder. A reviewer complied when the
only folders are its own pack folder and its own answer file's folder.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path, PureWindowsPath


def paths_in(obj) -> list[str]:
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += paths_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out += paths_in(v)
    elif isinstance(obj, str) and (":/" in obj or ":\\" in obj or obj.startswith("/c/")):
        out.append(obj)
    return out


def main() -> None:
    raw = Path(sys.argv[1])
    for t in sorted(raw.glob("reviewer*_transcript.jsonl.gz")):
        tools: dict[str, int] = {}
        folders: set[str] = set()
        with gzip.open(t, "rt", encoding="utf-8") as f:
            for line in f:
                m = json.loads(line).get("message", {})
                if m.get("role") != "assistant" or not isinstance(m.get("content"), list):
                    continue
                for c in m["content"]:
                    if c.get("type") != "tool_use":
                        continue
                    tools[c["name"]] = tools.get(c["name"], 0) + 1
                    for p in paths_in(c["input"]):
                        folders.add(str(PureWindowsPath(p.split()[0]).parent).lower())
        print(t.name, json.dumps(tools), sorted(folders))


if __name__ == "__main__":
    main()
