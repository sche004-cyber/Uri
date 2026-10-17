"""One-off: harness for runtime-c (code 4d782ef1). Reviewer R1-08: copy the worker's worker-instance.json (its
brain_profile note) into each run's evidence; CRASH-1 E0: sample system commit with the GPU census."""
from pathlib import Path

p = Path(__file__).resolve().parent / "live_session.py"
s = p.read_bytes().decode()
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
pairs = [
    ('ROOT / "runtime-b"\n', 'ROOT / "runtime-c"\n'),
    ("        samples.append(dict(utc=now(), adapter_dedicated_mib=c.get(\"adapter_dedicated_mib\"), card_mib=c.get(\"card_mib\"),\n",
     "        vm = psutil.virtual_memory()\n"
     "        try:\n"
     "            sw = psutil.swap_memory()\n"
     "            commit_free = round((vm.available + sw.free) / 2**20)\n"
     "        except Exception:\n"
     "            commit_free = None\n"
     "        samples.append(dict(utc=now(), adapter_dedicated_mib=c.get(\"adapter_dedicated_mib\"), card_mib=c.get(\"card_mib\"),\n"
     "                            commit_free_est_mib=commit_free,\n"),
    ("        (OUT / \"session-final.json\").write_text(json.dumps(record, indent=1, default=str))\n",
     "        wi = pathlib.Path(CURRENT[\"client_root\"]) / \"control\" / \"worker-instance.json\"\n"
     "        if wi.exists():\n"
     "            (OUT / \"worker-instance.json\").write_bytes(wi.read_bytes())\n"
     "        (OUT / \"session-final.json\").write_text(json.dumps(record, indent=1, default=str))\n"),
]
for a, b in pairs:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
if crlf:
    s = s.replace("\n", "\r\n")
p.write_bytes(s.encode())
print("patched-c")
