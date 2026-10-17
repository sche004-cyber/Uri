"""Copy the UI V2 live harness and point it at the post-integration canonical tree (exact string edits only)."""
from pathlib import Path

S = Path(r"C:\Users\cheta\Development\uri-ui-v2p-run\tools")
L = Path(r"D:\uri-dev\uri-ui-v2-freeze\live\tools")
UI = r"D:\uri-dev\uri-ui-v2-freeze\ui-7893aaed"
RT = r"D:\uri-dev\uri-ui-v2-freeze\rt-7893aaed"


def edit(name, reps):
    s = (S / name).read_text(encoding="utf-8")
    for a, b in reps:
        assert s.count(a) == 1, (name, a)
        s = s.replace(a, b)
    (L / name).write_bytes(s.encode("utf-8"))


edit("live_session.py", [
    ('SRC, RT = pathlib.Path(r"C:\\Users\\cheta\\Development\\uri-ui-v2p"), ROOT / "runtime2"'.replace("\\\\", "\\"),
     f'SRC, RT = pathlib.Path(r"{UI}"), pathlib.Path(r"{RT}")'),
    ('cache = ROOT.parent / "uri-core-live-verification-20261014/fixtures',
     'cache = pathlib.Path(r"C:\\Users\\cheta\\Development").joinpath("uri-core-live-verification-20261014") / "fixtures'.replace("\\\\", "\\")),
])
edit("run_live_ui.py", [
    ('SRC = pathlib.Path(r"C:\\Users\\cheta\\Development\\uri-ui-v2p")'.replace("\\\\", "\\"),
     f'SRC = pathlib.Path(r"{UI}")'),
])
edit("go_override.sh", [
    ("R=/c/Users/cheta/Development/uri-ui-v2p-run", "R=/d/uri-dev/uri-ui-v2-freeze/live"),
    ("PY=$R/runtime2/.venv/Scripts/python.exe", "PY=/d/uri-dev/uri-ui-v2-freeze/rt-7893aaed/.venv/Scripts/python.exe"),
    ("r'C:\\Users\\cheta\\Development\\uri-ui-v2p'".replace("\\\\", "\\"), f"r'{UI}'"),
])
print("ok")
