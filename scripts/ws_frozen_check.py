"""Frozen-boundary check for the working-system integration (WS blueprint AC-2).

    python scripts/ws_frozen_check.py [<tree>]

1. The 121 frozen Phase 1 files in <tree> are byte-identical to the Phase 1 checkpoint zip
   (final-closure-20261005-phase1.zip, SHA-256 31a34dcb...), when the zip is present on this machine.
2. Against the published baseline 037229c, no tracked path under the protected prefixes differs (working tree) and
   no untracked file exists under them.
Exit 0 only when both hold. Prints JSON.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ZIP = Path(r"C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip")
ZIP_SHA = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"
BASELINE = "037229c1fc04eadc6a2e42e92e6ef0d12520d3fe"
PROTECTED = ("uri_core/", "uri_supervisor/", "uri_supervisor_bridge/", "uri_harness_adapters/", "model_lab/integration/",
             "scripts/run_uri_supervised_worker.py", "scripts/run_uri_phase2_server.py",
             "scripts/run_uri_client_worker.py", "scripts/run_uri_isolated_server.py", "scripts/c1_bootstrap.py",
             "uri_ui/lib/services/paired_runtime.dart", "uri_ui/lib/services/supervised_runtime.dart",
             "uri_ui/lib/screens/settings/paired_runtime_screen.dart", "uri_ui/lib/screens/settings/settings_shell.dart",
             "uri_ui/lib/screens/tasks/supervised_execution_screen.dart", ".gitignore")


def main(argv):
    tree = Path(argv[1] if len(argv) > 1 else Path(__file__).resolve().parents[1])
    out = {"tree": str(tree)}
    if ZIP.is_file():
        assert hashlib.sha256(ZIP.read_bytes()).hexdigest() == ZIP_SHA, "CHECKPOINT_HASH"
        z = zipfile.ZipFile(ZIP)
        names = [n for n in z.namelist() if not n.startswith("GIT_")]
        drift = [n for n in names if not (tree / n).is_file() or (tree / n).read_bytes() != z.read(n)]
        out["phase1_frozen"] = {"checked": len(names), "drift": drift}
    else:
        out["phase1_frozen"] = {"checked": 0, "drift": None, "blocked": "checkpoint zip not present"}
    git = lambda *a: subprocess.run(["git", "-C", str(tree), *a], capture_output=True, text=True).stdout.split()
    # Tracked changes against the baseline AND untracked files (Codex WS round 1, F5).
    changed = git("diff", "--name-only", BASELINE) + git("ls-files", "--others", "--exclude-standard")
    out["protected_changed_vs_baseline"] = [p for p in changed if p.startswith(PROTECTED) or p in PROTECTED]
    ok = out["phase1_frozen"]["drift"] == [] and not out["protected_changed_vs_baseline"]
    out["ok"] = ok
    print(json.dumps(out, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
