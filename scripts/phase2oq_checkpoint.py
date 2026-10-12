"""Cut the Phase 2 OPERATIONAL-QUALIFICATION candidate checkpoint OUTSIDE the tree, with a sidecar manifest.

Same discipline as `phase2close_checkpoint.py` (whose file globs it reuses unchanged): refuses to overwrite, hashes
every file, records git HEAD and status. Adds the operational-qualification globs: tests/phase2oq, PHASE2OQ docs,
phase2oq scripts, the Chat handoff action, the one Chat file that mounts it, and its Chat-pane test.

Usage: python scripts/phase2oq_checkpoint.py <out_dir> [<evidence_dir> ...]      (URI_CANDIDATE_SUFFIX optional)
"""
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("p2c_cp", ROOT / "scripts" / "phase2close_checkpoint.py")
_close = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_close)
GLOBS = _close.GLOBS + ["tests/phase2oq/**/*", "docs/plans/PHASE2OQ_*", "docs/architecture/PHASE2OQ_*", "scripts/phase2oq_*",
                        "uri_ui/lib/widgets/supervised_handoff_action.dart", "uri_ui/lib/screens/ask/ask_uri_screen.dart",
                        "uri_ui/test/chat_supervised_handoff_test.dart"]
SKIP_SUFFIX = _close.SKIP_SUFFIX
CLOSURE_ACCEPTED_SHA256 = "fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298"


def main(out_dir, *evidence_dirs):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    suffix = os.environ.get("URI_CANDIDATE_SUFFIX", "")
    if suffix and not suffix.replace("-", "").isalnum():
        raise SystemExit("BAD_SUFFIX")
    zpath = out_dir / f"phase2oq-candidate-{stamp}{suffix}.zip"
    if zpath.exists() or zpath.with_suffix(".json").exists():
        raise SystemExit("CANDIDATE_EXISTS_REFUSING_TO_OVERWRITE: " + str(zpath))
    files = sorted({p for g in GLOBS for p in ROOT.glob(g)
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix not in SKIP_SUFFIX})
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout
    manifest, ev_count = {}, 0
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(ROOT).as_posix()
            data = p.read_bytes()
            manifest[rel] = hashlib.sha256(data).hexdigest()
            z.writestr(rel, data)
        for evidence_dir in evidence_dirs:
            ev = Path(evidence_dir)
            for p in sorted(ev.rglob("*")):
                if p.is_file() and p.suffix not in SKIP_SUFFIX and "__pycache__" not in p.parts:
                    rel = "evidence/" + ev.name + "/" + p.relative_to(ev).as_posix()
                    data = p.read_bytes()
                    manifest[rel] = hashlib.sha256(data).hexdigest()
                    z.writestr(rel, data)
                    ev_count += 1
        z.writestr("GIT_HEAD.txt", git("rev-parse", "HEAD"))
        z.writestr("GIT_STATUS.txt", git("status", "--short"))
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=1, sort_keys=True))
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    side = {"path": str(zpath), "sha256": sha, "files": len(files), "evidence_files": ev_count,
            "base_commit": git("rev-parse", "--short", "HEAD").strip(), "head": git("rev-parse", "HEAD").strip(),
            "phase2close_accepted_candidate_sha256": CLOSURE_ACCEPTED_SHA256,
            "phase2ops_accepted_candidate_sha256": "9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a",
            "phase1_frozen_checkpoint_sha256": "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7",
            "status": "PHASE 2 OPERATIONAL-QUALIFICATION CANDIDATE, NOT FROZEN, NOT CUT OVER; physical gates PA-1..PA-13 "
                      "and owner decisions (EXE-1b sandbox backend, C6 decision 3, voice, shipping line, freeze, cutover) PENDING"}
    zpath.with_suffix(".json").write_text(json.dumps(side, indent=1))
    print(json.dumps(side, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
