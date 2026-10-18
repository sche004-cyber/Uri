"""One-off: point the harness at runtime-b and write/remove the worker's profile selection file with the Brain profile."""
from pathlib import Path

p = Path(__file__).resolve().parent / "live_session.py"
s = p.read_bytes().decode()
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
pairs = [
    ('ROOT / "runtime"\n', 'ROOT / "runtime-b"\n'),
    ("    if PROFILE:\n        cfg = RP.derive_config(cfg, *parse_profile(PROFILE))\n",
     "    from uri_operational_intelligence import runtime_profile_selection as PS\n"
     "    sel = PS.selection_path(CURRENT[\"client_root\"])\n"
     "    if PROFILE:\n        cfg = RP.derive_config(cfg, *parse_profile(PROFILE))\n"
     "        PS.write(CURRENT[\"client_root\"], *parse_profile(PROFILE))   # the worker verifies the same profile\n"
     "    else:\n        sel.unlink(missing_ok=True)                                  # frozen: no selection file\n"),
]
for a, b in pairs:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_bytes(s.encode())
print("patched-b")
