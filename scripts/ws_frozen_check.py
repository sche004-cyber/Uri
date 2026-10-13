"""PROPOSAL ONLY: exact-blob reconciliation of recorded D12/D2/D33 exceptions.

This file is not the active scripts/ws_frozen_check.py. Owner activation approval
is required. The original checkpoint and protected path boundary are immutable.
"""
import hashlib
import io
import json
import stat
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
ANCHOR = "1b5423bc15fd7e5da9161c862cf839925da9f2eb"
# Reviewed constants, not a caller-editable manifest or path-wide permission.
PROVENANCE = {
    "docs/graphify/GRAPHIFY_LEAK_1_PLAN_AND_ACCEPTANCE.md": "1eeb1f9132d7b314420a1751b4574088e830ae6a2923e86a932e433bbcdeea6f",
    "docs/ssrf/SSRF_1_PLAN_AND_ACCEPTANCE.md": "fac7a8681b0ff83923a34073b16da8d5dc3630fba89a211ff712c12432e5dba9",
    "docs/web/IDN_1B_PLAN_AND_ACCEPTANCE.md": "387a29366348a5b492885fd121d97a81d60f0080fff30ad9dda3aee069aeb71b",
}
APPROVED = {
    "uri_core/app/server.py": {
        "sha256": "59cfde59c709fa7f83df84e957f5962701276afce54cb196541134a9a43cf4f8",
        "decisions": ["GRAPHIFY-LEAK-1/D12"],
        "commits": ["9ae7c60cd02b3a7be87a465db4170705d28f9d72", "6c62281fb6b37acfc486fa29468e66824912e151"],
        "provenance": ["docs/graphify/GRAPHIFY_LEAK_1_PLAN_AND_ACCEPTANCE.md"],
    },
    "uri_core/tools/fetch_url.py": {
        "sha256": "404e60921c207753868589b8a16f409ee80f35a01b0a33e8400d8780d93139e8",
        "decisions": ["SSRF-1/D2", "IDN-1b/D33"],
        "commits": ["f44f70a58e49d9ebe9559004bc81b7c62c0d8fe7", "a5a31435035c88ab5c3a868796f96232bc036759", "6a33c1b5dbfe0c3694963416310945db8ee06b9d"],
        "provenance": ["docs/ssrf/SSRF_1_PLAN_AND_ACCEPTANCE.md", "docs/web/IDN_1B_PLAN_AND_ACCEPTANCE.md"],
    },
}


def git(tree, *args):
    p = subprocess.run(["git", "-C", str(tree), *args], capture_output=True)
    if p.returncode:
        raise ValueError("GIT_REFUSED:" + " ".join(args[:2]))
    return p.stdout


def ancestor(tree, commit):
    p = subprocess.run(["git", "-C", str(tree), "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True)
    if p.returncode not in (0, 1):
        raise ValueError("PROVENANCE_COMMIT_MISSING:" + commit)
    return p.returncode == 0


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_bytes(tree, name):
    p = tree / name
    for part in [p, *p.parents]:
        if part == tree.parent:
            break
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("LINK_REFUSED:" + name)
    if not stat.S_ISREG(p.stat().st_mode):
        raise ValueError("NOT_REGULAR:" + name)
    return p.read_bytes()


def exact_exception(tree, name):
    spec = APPROVED.get(name)
    if spec is None or not ancestor(tree, ANCHOR):
        return False
    if not all(ancestor(tree, c) for c in spec["commits"]):
        return False
    if digest(regular_bytes(tree, name)) != spec["sha256"]:
        return False
    # Committed and staged content/modes must also be the pinned canonical blob.
    for revision in (ANCHOR, "HEAD"):
        if digest(git(tree, "show", revision + ":" + name)) != spec["sha256"]:
            return False
        if not git(tree, "ls-tree", revision, "--", name).startswith(b"100644 blob "):
            return False
    staged = git(tree, "ls-files", "--stage", "--", name).split(b"\t", 1)[0].split()
    if len(staged) != 3 or staged[0] != b"100644" or staged[2] != b"0":
        return False
    if digest(git(tree, "cat-file", "blob", staged[1].decode("ascii"))) != spec["sha256"]:
        return False
    for witness in spec["provenance"]:
        expected = PROVENANCE[witness]
        if digest(regular_bytes(tree, witness)) != expected:
            return False
        if any(digest(git(tree, "show", ":" + witness if rev == ":" else rev + ":" + witness)) != expected
               for rev in (ANCHOR, "HEAD", ":")):
            return False
        if any(not git(tree, "ls-tree", rev, "--", witness).startswith(b"100644 blob ")
               for rev in (ANCHOR, "HEAD")):
            return False
        witness_stage = git(tree, "ls-files", "--stage", "--", witness).split(b"\t", 1)[0].split()
        if len(witness_stage) != 3 or witness_stage[0] != b"100644" or witness_stage[2] != b"0":
            return False
    return True


def check(tree):
    tree = Path(tree).absolute()
    out = {"tree": str(tree), "ok": False, "recognized_exact_blobs": {}}
    try:
        if Path(git(tree, "rev-parse", "--show-toplevel").decode().strip()).resolve() != tree.resolve():
            raise ValueError("NOT_REPOSITORY_ROOT")
        if not ZIP.is_file():
            raise ValueError("CHECKPOINT_MISSING")
        checkpoint_bytes = ZIP.read_bytes()
        if digest(checkpoint_bytes) != ZIP_SHA:
            raise ValueError("CHECKPOINT_HASH")
        changed = set(git(tree, "diff", "--name-only", "-z", BASELINE).decode().split("\0"))
        changed.update(git(tree, "diff", "--cached", "--name-only", "-z", BASELINE).decode().split("\0"))
        changed.update(git(tree, "diff", "--name-only", "-z", BASELINE, "HEAD").decode().split("\0"))
        # Local/global Git ignores are not authority to add protected files.
        changed.update(git(tree, "ls-files", "--others", "-z").decode().split("\0"))
        # Clean filters/attributes can hide working-copy content from git diff.
        # Compare raw bytes of every baseline protected blob, not only the ZIP.
        for entry in git(tree, "ls-tree", "-r", "-z", BASELINE).split(b"\0"):
            if not entry:
                continue
            metadata, raw_name = entry.split(b"\t", 1)
            name = raw_name.decode()
            if name.startswith(PROTECTED) or name in PROTECTED:
                data = regular_bytes(tree, name)
                blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
                if metadata.split()[2].decode() != blob:
                    changed.add(name)
        hidden = {entry[2:] for entry in git(tree, "ls-files", "-v", "-z").decode().split("\0")
                  if entry and entry[0] != "H" and (entry[2:].startswith(PROTECTED) or entry[2:] in PROTECTED)}
        changed.update(hidden)
        protected = {p for p in changed if p and (p.startswith(PROTECTED) or p in PROTECTED)}
        # Once canonical security fixes are in ancestry, reverting them to the
        # original checkpoint is also refused, even if diff(BASELINE) is empty.
        required = set(APPROVED) if ancestor(tree, ANCHOR) else set()
        accepted = {p for p in protected | required if p not in hidden and exact_exception(tree, p)}
        out["recognized_exact_blobs"] = {p: APPROVED[p] for p in sorted(accepted)}
        with zipfile.ZipFile(io.BytesIO(checkpoint_bytes)) as z:
            names = [n for n in z.namelist() if not n.startswith("GIT_")]
            drift = [n for n in names if regular_bytes(tree, n) != z.read(n)]
        out["phase1_frozen"] = {"checked": len(names), "drift": drift,
                                "unapproved_drift": sorted(set(drift) - accepted)}
        out["protected_changed_vs_baseline"] = sorted(protected)
        out["unapproved_protected_changes"] = sorted((protected | required) - accepted)
        out["ok"] = not out["phase1_frozen"]["unapproved_drift"] and not out["unapproved_protected_changes"]
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        out["error"] = str(exc)
    return out


def main(argv):
    result = check(argv[1] if len(argv) > 1 else Path(__file__).resolve().parents[1])
    print(json.dumps(result, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
