"""Verify historical runtime output separately from the accepted source checker.

Owner authorization 2026-10-14 permits exactly the two canonical security blobs.
The receipt is descriptive, never authority: expected bytes come from pinned Git
objects and the clean, canonically descended source candidate. No Core edit or
checkpoint reset is performed by verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from scripts import ws_frozen_check as F

ACCEPTED_SOURCE = "e0b5c298d046622d52550f1455ab649070165602"
PATCH_PATH = "docs/governance/windows_restoration/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch"
AUTHORITY_PATH = "docs/governance/windows_restoration/OWNER_RUNTIME_AUTHORIZATION.json"
PATCH_SHA256 = "ba9249dad002e62c6cf1698284e8a2ada325d0afa1444579a371af7fa9caea02"
BEFORE = {
    "uri_core/app/server.py": "7b455f05ae97f7f6cbc944ba5c93998ea64063402568ea9750b70356db4f366b",
    "uri_core/tools/fetch_url.py": "f097006211c2b2c4abc9a4aaf7aa64063ee00a55030559caf857724ce2af9bff",
}


class VerificationError(ValueError):
    pass


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if p.returncode:
        raise VerificationError("GIT_REFUSED:" + " ".join(args[:2]))
    return p.stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def raw(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
        raise VerificationError("UNSAFE_PATH:" + name)
    root = Path(root).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise VerificationError("ROOT_LINK")
    p = root
    for part in parts.parts:
        p = p / part
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise VerificationError("LINK_REFUSED:" + name)
    if not stat.S_ISREG(p.stat().st_mode):
        raise VerificationError("NOT_REGULAR:" + name)
    return p.read_bytes()


def tree(root, revision):
    result = {}
    for row in git(root, "ls-tree", "-r", "-z", revision).split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise VerificationError("UNSUPPORTED_GIT_MODE:" + name.decode())
        result[name.decode()] = (mode, oid)
    return result


def source_authority(source):
    source = Path(source).absolute()
    if Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve() != source.resolve():
        raise VerificationError("SOURCE_ROOT")
    git(source, "merge-base", "--is-ancestor", ACCEPTED_SOURCE, "HEAD")
    if git(source, "diff", "--name-only") or git(source, "diff", "--cached", "--name-only"):
        raise VerificationError("SOURCE_DIRTY")
    frozen = F.check(source)
    if not frozen["ok"]:
        raise VerificationError("SOURCE_FROZEN_REFUSED")
    files = tree(source, "HEAD")
    # Raw comparisons also reject filters/attributes hiding a tool or authority edit.
    for name in (PATCH_PATH, AUTHORITY_PATH, "scripts/oi_materialize_test_runtime.py",
                 "scripts/ws_materialized_verify.py", "scripts/ws_frozen_check.py"):
        if name not in files or blob_id(raw(source, name)) != files[name][1]:
            raise VerificationError("SOURCE_TOOL_OR_AUTHORITY_CHANGED:" + name)
    if digest(raw(source, PATCH_PATH)) != PATCH_SHA256:
        raise VerificationError("PATCH_IDENTITY")
    authority = json.loads(raw(source, AUTHORITY_PATH))
    if authority != {
        "decision": "OWNER_WINDOWS_RESTORATION_20261014",
        "patch_sha256": PATCH_SHA256,
        "historical_head": "e8e3b65259c45fc823addc3ef8969425a265bd1b",
        "checkpoint_sha256": F.ZIP_SHA,
        "approved_blobs": {p: F.APPROVED[p]["sha256"] for p in BEFORE},
        "scope": "Fresh isolated historical runtime only; no other protected change, GPU override or cutover",
    }:
        raise VerificationError("OWNER_AUTHORITY_CHANGED")
    return files, frozen


def expected_files(source, *, exclude_tests=False):
    from scripts import oi_materialize_test_runtime as M
    source = Path(source)
    files, _ = source_authority(source)
    expected = tree(source, M.BASE)
    overlay_data = raw(source, M.OVERLAY_LIST)
    if overlay_data != git(source, "show", ACCEPTED_SOURCE + ":" + M.OVERLAY_LIST):
        raise VerificationError("OVERLAY_LIST_CHANGED")
    overlay = tree(source, M.OVERLAY_COMMIT)
    for path in overlay_data.decode().splitlines():
        if path.strip():
            expected[path.strip()] = overlay[path.strip()]
    for prefix in M.OI_PATHS:
        if exclude_tests and prefix in M.TEST_PATHS:
            continue
        chosen = {p: entry for p, entry in files.items() if p == prefix or p.startswith(prefix + "/")}
        if set(chosen) & set(expected):
            raise VerificationError("CANDIDATE_PATH_COLLISION:" + prefix)
        expected.update(chosen)
    for path in M.REPLACED_PATHS:
        expected[path] = files[path]
    for path in BEFORE:
        expected[path] = files[path]
    return expected


def reconcile(source, runtime):
    source_authority(source)
    for path, sha in BEFORE.items():
        if digest(raw(runtime, path)) != sha:
            raise VerificationError("TRANSITION_BEFORE_CHANGED:" + path)
    patch = Path(source) / PATCH_PATH
    git(runtime, "apply", "--check", str(patch))
    git(runtime, "apply", str(patch))
    result = {}
    for path, before in BEFORE.items():
        after = digest(raw(runtime, path))
        if after != F.APPROVED[path]["sha256"]:
            raise VerificationError("TRANSITION_AFTER_CHANGED:" + path)
        result[path] = {"before_sha256": before, "after_sha256": after}
    return result


def verify(source, runtime):
    from scripts import oi_materialize_test_runtime as M
    source, runtime = Path(source).absolute(), Path(runtime).absolute()
    result = {"ok": False, "source": str(source), "runtime": str(runtime)}
    try:
        for root in (source, runtime):
            if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
                raise VerificationError("ROOT_LINK")
        source_authority(source)
        head = git(source, "rev-parse", "HEAD").decode().strip()
        source_tree = git(source, "rev-parse", "HEAD^{tree}").decode().strip()
        if Path(git(runtime, "rev-parse", "--show-toplevel").decode().strip()).resolve() != runtime.resolve():
            raise VerificationError("RUNTIME_ROOT")
        if git(runtime, "rev-parse", "HEAD").decode().strip() != M.BASE:
            raise VerificationError("HISTORICAL_HEAD_CHANGED")
        if git(runtime, "diff", "--cached", "--name-only", M.BASE):
            raise VerificationError("RUNTIME_INDEX_CHANGED")
        hidden = [r for r in git(runtime, "ls-files", "-v", "-z").decode().split("\0") if r and r[0] != "H"]
        if hidden:
            raise VerificationError("HIDDEN_INDEX_FLAGS")
        receipt = json.loads(raw(runtime, "OI_MATERIALIZATION_RECEIPT.json"))
        if (Path(receipt["candidate_source"]).resolve() != source.resolve()
                or receipt["candidate_head"] != head or receipt["candidate_tree"] != source_tree
                or receipt["head"] != M.BASE or receipt["overlay_commit"] != M.OVERLAY_COMMIT
                or receipt["security_patch_sha256"] != PATCH_SHA256):
            raise VerificationError("RECEIPT_IDENTITY")
        if type(receipt["oi_tests_included"]) is not bool:
            raise VerificationError("RECEIPT_TEST_SCOPE")
        expected = expected_files(source, exclude_tests=not receipt["oi_tests_included"])
        mismatches = []
        for name, (_mode, oid) in expected.items():
            if blob_id(raw(runtime, name)) != oid:
                mismatches.append(name)
        if mismatches:
            raise VerificationError("OUTPUT_CHANGED:" + ",".join(mismatches[:10]))
        extras = []
        for current, dirs, names in os.walk(runtime, followlinks=False):
            rel = Path(current).relative_to(runtime)
            if not rel.parts:
                dirs[:] = [d for d in dirs if d not in (".git", ".venv", "work")]
            for d in dirs:
                p = Path(current) / d
                if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                    raise VerificationError("OUTPUT_DIRECTORY_LINK:" + p.relative_to(runtime).as_posix())
            for name in names:
                path = (rel / name).as_posix()
                if path not in expected and path not in (".git", "OI_MATERIALIZATION_RECEIPT.json"):
                    extras.append(path)
        if extras:
            raise VerificationError("UNKNOWN_OUTPUT:" + ",".join(sorted(extras)[:10]))
        for path, spec in F.APPROVED.items():
            if digest(raw(runtime, path)) != spec["sha256"]:
                raise VerificationError("APPROVED_BLOB_CHANGED:" + path)
        for path, sha in F.PROVENANCE.items():
            if digest(raw(runtime, path)) != sha:
                raise VerificationError("PROVENANCE_CHANGED:" + path)
        result.update(ok=True, source_head=head, source_tree=source_tree, historical_head=M.BASE,
                      checked_files=len(expected), checkpoint_sha256=F.ZIP_SHA,
                      approved_blobs={p: F.APPROVED[p]["sha256"] for p in BEFORE},
                      note="Execution dependencies/state retain existing C1 identity and permission gates; this verifies source output, not live qualification.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runtime")
    ap.add_argument("--source", default=str(SOURCE))
    args = ap.parse_args()
    result = verify(args.source, args.runtime)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
