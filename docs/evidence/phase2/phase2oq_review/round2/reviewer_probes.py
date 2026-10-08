"""Synthetic qualification probes; creates only work/c1/oq-r2-probe state."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TREE = ROOT / "uri-agent"
sys.path.insert(0, str(TREE))
from uri_supervisor_bridge import qualification as q

base = TREE / "work/c1/oq-r2-probe"
base.mkdir(parents=True, exist_ok=True)
vendor = base / "vendor" / q.CODEX_NATIVE_TRIPLE
bin_dir = vendor / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
exe = bin_dir / "codex.exe"
exe.write_bytes(b"synthetic binary")
meta = vendor / "codex-package.json"

def attempt(label, path):
    try:
        pins, resolves = q.launch_chain_for("codex_cli", path)
        result = ("ACCEPTED", len(pins), len(resolves))
    except q.QualificationError as exc:
        result = ("REFUSED", exc.code)
    print(label, result)

meta.unlink(missing_ok=True)
attempt("missing descriptor", exe)
elsewhere = base / "codex-package.json"
elsewhere.write_text(json.dumps({"layoutVersion": 1, "version": "0.158.0", "target": q.CODEX_NATIVE_TRIPLE,
                                 "entrypoint": "bin/codex.exe"}))
attempt("descriptor elsewhere", exe)
renamed = bin_dir / "renamed.exe"
renamed.write_bytes(b"synthetic binary")
attempt("renamed in vendor", renamed)
other = base / "outside" / "renamed.exe"
other.parent.mkdir(exist_ok=True)
other.write_bytes(b"synthetic binary")
attempt("renamed outside vendor", other)
meta.write_bytes(elsewhere.read_bytes())
attempt("recognised descriptor", exe)
pins, resolves = q.launch_chain_for("codex_cli", exe)
rec = {"provider": "codex_cli", "spec_id": "codex_cli", "level": "NATIVE_QUALIFIED",
       "executable": str(exe), "pinned_files": pins}
print("worker recognised pins", q._pins_recognised_codex_layout(rec))
rec["pinned_files"] = {k: v for k, v in pins.items() if not k.endswith("codex-package.json")}
print("worker descriptor stripped", q._pins_recognised_codex_layout(rec))
meta.write_text(meta.read_text() + " ")
try:
    q.check_launch_chain(pins, resolves)
except q.QualificationError as exc:
    print("descriptor edited after signing", exc.code)
