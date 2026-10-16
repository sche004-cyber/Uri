"""Fake `flutter` for the DRV-3 gate tests (TEST ONLY). Behaviour, in the gate's cwd (a Dart package):

Flag files in the folder named by FAKE_FLAGS (set by the wrapper the test writes) steer it:
- ``--version --machine``: prints a version JSON; the framework revision is the content of flag ``rev`` (default rev1).
- ``pub get``: writes .dart_tool/package_config.json, unless flag ``offline_fail`` exists (offline cache miss).
- ``test``: without .dart_tool/package_config.json prints the real Flutter error and exits 1 (the DRV-3 condition);
  with it prints ``--machine`` events for the tests listed in tests.txt (``name=pass|fail``), one per line. A missing
  or empty tests.txt runs no test.
- ``analyze``: exits 1 without package_config.json, else 0.
"""
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
here = Path.cwd()
cfg = here / ".dart_tool" / "package_config.json"
flags = Path(os.environ.get("FAKE_FLAGS", here))

if args[:2] == ["--version", "--machine"]:
    rev = (flags / "rev").read_text().strip() if (flags / "rev").is_file() else "rev1"
    print(json.dumps({"frameworkRevision": rev, "engineRevision": "eng1", "dartSdkVersion": "3.0.0"}))
    sys.exit(0)
if args[:2] == ["pub", "get"]:
    if (flags / "offline_fail").is_file():
        print("Because uri_ui depends on foo any which doesn't exist (could not find package foo in cache), "
              "version solving failed.", file=sys.stderr)
        sys.exit(69)
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text("{}")
    print("Got dependencies!")
    sys.exit(0)
if args[:1] == ["analyze"]:
    sys.exit(0 if cfg.is_file() else 1)
if args[:1] == ["test"]:
    if not cfg.is_file():
        print('Error: cannot run without a dependency on either "package:flutter_test" or "package:test".')
        sys.exit(1)
    spec = here / "tests.txt"
    lines = [x.split("=") for x in spec.read_text().split() if "=" in x] if spec.is_file() else []
    root = (here / "test" / "a_test.dart").as_uri()
    rc = 0
    for i, (name, result) in enumerate(lines, start=1):
        print(json.dumps({"type": "testStart", "test": {"id": i, "name": name, "url": root, "root_url": root}}))
        if result != "pass":
            rc = 1
            print(json.dumps({"type": "error", "testID": i, "error": "TestFailure: expected"}))
        print(json.dumps({"type": "testDone", "testID": i, "result": "success" if result == "pass" else "failure",
                          "hidden": False}))
    print(json.dumps({"type": "done", "success": rc == 0}))
    sys.exit(rc)
sys.exit(2)
