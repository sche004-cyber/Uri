"""FCV-11: guarded Phase 1 offline rollback. The supported way to run the frozen C7 rollback.

The accepted Phase 1 checkpoint (final-closure-20261005-phase1.zip) restores the pre-security
uri_core/app/server.py (GRAPHIFY-LEAK-1) and, through the e8e3b65 base, the pre-security
uri_core/tools/fetch_url.py (SSRF-1, IDN-1b). The frozen tool (scripts/phase1_offline_rollback.py) restores
them without a warning. This wrapper inspects the checkpoint first and writes nothing until that inspection
passes:

    --inspect          report what the restored tree would hold; write nothing.
    (default)          refuse when a security file would be restored in a known-vulnerable or unknown version.
    --secure-recovery  restore, then apply the owner-authorized security transitions
                       (OWNER_WINDOWS_RESTORATION_20261014). Only for a checkpoint that owner record names.

The checkpoint itself is never modified. The frozen tool is called unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import phase1_offline_rollback as R  # noqa: E402

SECURITY_PATCH = "docs/governance/windows_restoration/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch"
SECURITY_PATCH_SHA256 = "ba9249dad002e62c6cf1698284e8a2ada325d0afa1444579a371af7fa9caea02"
AUTHORITY = "docs/governance/windows_restoration/OWNER_RUNTIME_AUTHORIZATION.json"
AUTHORITY_DECISION = "OWNER_WINDOWS_RESTORATION_20261014"
# path -> versions known to lack the security fix (sha256 -> origin), and the owner-approved secure version.
SECURITY_FILES = {
    "uri_core/app/server.py": {
        "vulnerable": {"7b455f05ae97f7f6cbc944ba5c93998ea64063402568ea9750b70356db4f366b": "Phase 1 checkpoint",
                       "404aad61cf9f0391dba52dad15766d97caf0a96715703d6cdad715902872a42a": "e8e3b65 base"},
        "secure": "59cfde59c709fa7f83df84e957f5962701276afce54cb196541134a9a43cf4f8",
        "fix": "GRAPHIFY-LEAK-1",
    },
    "uri_core/tools/fetch_url.py": {
        "vulnerable": {"f097006211c2b2c4abc9a4aaf7aa64063ee00a55030559caf857724ce2af9bff": "e8e3b65 base"},
        "secure": "404e60921c207753868589b8a16f409ee80f35a01b0a33e8400d8780d93139e8",
        "fix": "SSRF-1 and IDN-1b",
    },
}
# The transition is the exact patch the owner authorized: it applies only to these before-versions.
PATCH_BEFORE = {"uri_core/app/server.py": "7b455f05ae97f7f6cbc944ba5c93998ea64063402568ea9750b70356db4f366b",
                "uri_core/tools/fetch_url.py": "f097006211c2b2c4abc9a4aaf7aa64063ee00a55030559caf857724ce2af9bff"}


class RollbackRefused(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _restored_security_files(archive):
    """The bytes the frozen tool would restore at each security path: the archive member, else the base file."""
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
        out = {p: z.read(p) for p in SECURITY_FILES if p in names}
    for path in SECURITY_FILES:
        if path not in out:
            base = subprocess.run(["git", "-C", str(ROOT), "show", f"{R.BASELINE}:{path}"], capture_output=True)
            if base.returncode == 0:
                out[path] = base.stdout
    return out


def inspect(archive, expected_sha256):
    """Read-only inspection. Raises for an archive the frozen tool would refuse on hash or scope."""
    archive = Path(archive).resolve()
    if not archive.is_relative_to((ROOT / "work/c1/checkpoints").resolve()) or not archive.is_file():
        raise RollbackRefused("CHECKPOINT_SCOPE")
    actual = sha256(archive.read_bytes())
    if actual != expected_sha256:
        raise RollbackRefused("CHECKPOINT_HASH")
    files = {}
    for path, data in sorted(_restored_security_files(archive).items()):
        spec, digest = SECURITY_FILES[path], sha256(data)
        state = ("SECURE" if digest == spec["secure"] else "VULNERABLE" if digest in spec["vulnerable"]
                 else "UNKNOWN")
        files[path] = {"sha256": digest, "state": state, "fix": spec["fix"],
                       "origin": spec["vulnerable"].get(digest)}
    unsafe = sorted(p for p, f in files.items() if f["state"] != "SECURE")
    return {"archive_sha256": actual, "security_files": files, "safe": not unsafe, "unsafe": unsafe}


def _authorized(archive_sha256):
    authority = json.loads((ROOT / AUTHORITY).read_text(encoding="utf-8"))
    return (authority.get("decision") == AUTHORITY_DECISION
            and authority.get("patch_sha256") == SECURITY_PATCH_SHA256
            and authority.get("historical_head") == R.BASELINE
            and authority.get("checkpoint_sha256") == archive_sha256
            and authority.get("approved_blobs") == {p: s["secure"] for p, s in SECURITY_FILES.items()})


def _secure_bytes(current):
    """Apply the authorized patch to the before-versions outside any repository; return the verified results."""
    patch = (ROOT / SECURITY_PATCH).read_bytes()
    if sha256(patch) != SECURITY_PATCH_SHA256:
        raise RollbackRefused("SECURITY_PATCH_CHANGED")
    if {p: sha256(d) for p, d in current.items()} != PATCH_BEFORE:
        raise RollbackRefused("SECURE_RECOVERY_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="uri-secure-rollback-") as tmp:
        for path, data in current.items():
            (Path(tmp) / path).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / path).write_bytes(data)
        env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tmp).parent)}   # never inside a repository
        # Git for Windows enables core.autocrlf system-wide; outside a repository it would write CRLF.
        applied = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply", "-"], cwd=tmp,
                                 input=patch, capture_output=True, env=env)
        if applied.returncode:
            raise RollbackRefused("SECURITY_TRANSITION_FAILED")
        result = {path: (Path(tmp) / path).read_bytes() for path in current}
    if any(sha256(d) != SECURITY_FILES[p]["secure"] for p, d in result.items()):
        raise RollbackRefused("SECURITY_TRANSITION_FAILED")
    return result


def warning(report):
    lines = ["URI ROLLBACK REFUSED: this checkpoint would restore security files without their fixes."]
    for path in report["unsafe"]:
        f = report["security_files"][path]
        what = "a known-vulnerable version" if f["state"] == "VULNERABLE" else "an unrecognised version"
        lines.append(f"  {path}: {what} (missing {f['fix']}), sha256 {f['sha256'][:12]}")
    lines.append("Nothing was written. To restore with the owner-authorized security fixes applied, run:")
    lines.append("  python scripts/fcv_guarded_rollback.py --archive <checkpoint> --sha256 <hash> --secure-recovery")
    return "\n".join(lines)


def rollback(archive, expected_sha256, destination=None, *, secure_recovery=False):
    report = inspect(archive, expected_sha256)
    if report["safe"]:
        return {"rollback": R.rehearse(archive, expected_sha256, destination), "inspection": report,
                "security_transitions": {}}
    if not secure_recovery:
        raise RollbackRefused("UNSAFE_ROLLBACK_REFUSED")
    if not _authorized(report["archive_sha256"]):
        raise RollbackRefused("SECURE_RECOVERY_NOT_AUTHORIZED")
    current = _restored_security_files(Path(archive).resolve())
    secured = _secure_bytes(current)          # every check passes before the frozen tool writes anything
    dest = Path(destination) if destination else ROOT / "work/c1" / ("rollback_" + uuid.uuid4().hex)
    evidence = R.rehearse(archive, expected_sha256, dest)
    try:
        for path, data in secured.items():
            (dest / path).write_bytes(data)
            if sha256((dest / path).read_bytes()) != SECURITY_FILES[path]["secure"]:
                raise RollbackRefused("SECURITY_TRANSITION_FAILED")
    except Exception:
        for path in secured:                   # never leave the vulnerable versions behind
            (dest / path).unlink(missing_ok=True)
        raise
    transitions = {p: {"before_sha256": sha256(current[p]), "after_sha256": sha256(d)} for p, d in secured.items()}
    record = {"schema_version": 1, "status": "SECURE_RECOVERY_APPLIED", "decision": AUTHORITY_DECISION,
              "security_patch_sha256": SECURITY_PATCH_SHA256, "archive_sha256": report["archive_sha256"],
              "archive_modified": False, "security_transitions": transitions,
              "rollback_evidence": "rollback-evidence.json (frozen tool, describes the tree before this step)"}
    (dest / "secure-recovery-evidence.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return {"rollback": evidence, "inspection": report, "security_transitions": transitions,
            "destination": str(dest)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inspect", action="store_true")
    mode.add_argument("--secure-recovery", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            report = inspect(args.archive, args.sha256)
            print(json.dumps(report, indent=2))
            if not report["safe"]:
                print(warning(report), file=sys.stderr)
            return 0 if report["safe"] else 3
        print(json.dumps(rollback(args.archive, args.sha256, secure_recovery=args.secure_recovery), indent=2))
        return 0
    except RollbackRefused as exc:
        if str(exc) == "UNSAFE_ROLLBACK_REFUSED":
            print(warning(inspect(args.archive, args.sha256)), file=sys.stderr)
        print(json.dumps({"refused": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"refused": "OFFLINE_ROLLBACK_REFUSED"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
