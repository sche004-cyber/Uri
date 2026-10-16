"""UI V2 completion: re-probe of BLK-ENV-1 (GetFinalPathNameByHandleW access denied, 2026-10-13).

Read-only. Opens each path with the same flags as the 2026-10-13 probe and queries all four final-path forms,
then runs the Dart SDK on a script that canonicalizes its own path (the operation Flutter tooling performs).
"""
import ctypes, datetime, hashlib, json, subprocess, sys
from ctypes import wintypes as w
from pathlib import Path

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
k.CreateFileW.restype = w.HANDLE
k.GetFinalPathNameByHandleW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]
k.GetFinalPathNameByHandleW.restype = w.DWORD
k.CloseHandle.argtypes = [w.HANDLE]
DART = Path("C:/Users/cheta/flutter/bin/cache/dart-sdk/bin/dart.exe")
CAND = Path("C:/Users/cheta/Development/uri-ui-v2c")
paths = [DART, CAND / "uri_ui/pubspec.yaml", CAND / "uri_ui/lib/main.dart", CAND]
out = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "python": sys.version, "path_api": []}
for p in paths:
    h = k.CreateFileW(str(p), 0, 7, None, 3, 0x02000000, None)
    item = {"path": str(p), "handle_ok": h != w.HANDLE(-1).value}
    if item["handle_ok"]:
        item["final_paths"] = []
        for flags in (0, 8, 2, 10):
            b = ctypes.create_unicode_buffer(32768)
            ctypes.set_last_error(0)
            n = k.GetFinalPathNameByHandleW(h, b, len(b), flags)
            item["final_paths"].append({"flags": flags, "length": n, "error": ctypes.get_last_error(),
                                        "result": b.value if n else None})
        k.CloseHandle(h)
    else:
        item["open_error"] = ctypes.get_last_error()
    if p.is_file():
        item["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    out["path_api"].append(item)
smoke = Path(__file__).with_name("canon_smoke.dart")
if not smoke.exists(): smoke.write_text("import 'dart:io'; void main() { print(File(Platform.script.toFilePath()).resolveSymbolicLinksSync()); "
                 "print(Directory.current.resolveSymbolicLinksSync()); }\n")
r = subprocess.run([str(DART), "run", str(smoke)], cwd=CAND / "uri_ui", capture_output=True, text=True, timeout=300)
out["dart_smoke"] = {"exit_code": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()[-2000:]}
out["all_final_path_calls_ok"] = all(fp["error"] == 0 and fp["length"] > 0
                                     for it in out["path_api"] for fp in it.get("final_paths", [])) and \
    all(it["handle_ok"] for it in out["path_api"])
out["status"] = "COMPLETED_WITH_RESULT" if out["all_final_path_calls_ok"] and r.returncode == 0 else "FAILED"
print(json.dumps(out, indent=1))
