"""C7 offline source rollback rehearsal. Contains no deployment/cutover action.

Restore an exact code overlay ONLY into a new integration work/c1 directory.
Never restores private databases, sessions, credentials, shortcuts or tasks.
"""
import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path, PurePosixPath
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e8e3b65259c45fc823addc3ef8969425a265bd1b"


# The canonical Phase 1 source set. Source code and the PUBLIC catalogue only: never private
# state, credentials, databases, sessions, logs or UI binaries. (C7 cleanup: the provider adapter
# package, ported reference-binding tests and C4 fixtures are part of the runtime/test source.)
SOURCE_ROOTS = {"uri_core", "uri_harness_adapters", "scripts", "docs", "tests"}
SOURCE_FILES = {".gitignore", "PROJECT_MEMORY.md", "URI_MILESTONE_TRACKER.md",
                "uri_workspace/capabilities_registry.json"}


# FCV-01 (owner authorization required): the accepted Phase 1 freeze checkpoint
# (final-closure-20261005-phase1.zip) also carries the five frozen C6 UI contract sources and
# three Git provenance members. Only these exact names are recognized; any other uri_ui path,
# .dart file or metadata name stays refused.
FROZEN_UI_SOURCES = {"uri_ui/lib/screens/settings/paired_runtime_screen.dart",
                     "uri_ui/lib/screens/settings/settings_shell.dart",
                     "uri_ui/lib/services/paired_runtime.dart",
                     "uri_ui/test/paired_runtime_live_test.dart",
                     "uri_ui/test/paired_runtime_screen_test.dart"}
CHECKPOINT_METADATA = {"GIT_HEAD.txt", "GIT_STATUS.txt", "GIT_DIFF.patch"}


_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", "conin$", "conout$"} | {f"{d}{i}" for d in ("com", "lpt") for i in range(1, 10)}
CATALOGUE = "uri_workspace/capabilities_registry.json"


def _portable_component(part):
    # Windows aliases names (trailing dot/space, 8.3 short names, device names, streams), so two
    # distinct archive names could land on one file and the evidence would describe bytes that
    # are not on disk. Refuse every aliasing form instead of normalising it.
    return (part not in ("", ".", "..") and part[-1] not in ". " and "~" not in part
            and not any(c in '<>:"|?*\\' or ord(c) < 32 for c in part)
            and part.split(".")[0].lower() not in _WINDOWS_RESERVED)


def _catalogue_authority(overlay, base):
    """A restored catalogue may drop capabilities but never widen authority.

    Entries present at the baseline must be restored unchanged. A new entry must be
    unavailable to the server runtime, client-only and require explicit user approval, the posture
    under which catalogue presence grants nothing (external_harness_task).
    """
    try:
        restored = json.loads(overlay)
        baseline = json.loads(base)
        tools = restored["active_tools"]
        if not isinstance(tools, dict) or not isinstance(restored.get("planned_capabilities", {}), dict):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ValueError("CATALOGUE_INVALID") from None
    # Compare JSON values exactly (Python equality treats true == 1 == 1.0).
    same = lambda a, b: json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    if set(restored) - set(baseline) or any(not same(restored[k], baseline[k]) for k in restored
                                            if k not in ("active_tools", "planned_capabilities")):
        raise ValueError("CATALOGUE_AUTHORITY_CHANGED")
    # planned_capabilities is authority-bearing too: CapabilityRegistry turns each entry into a descriptor
    # (honouring its own status/availability/approval), and id-keyed consumers let a later duplicate
    # override an active tool's approval_requirement or effect_type. It may only drop baseline entries.
    planned = restored.get("planned_capabilities", {})
    if any(key not in baseline.get("planned_capabilities", {}) or not same(entry, baseline["planned_capabilities"][key])
           or key in tools for key, entry in planned.items()):
        raise ValueError("CATALOGUE_AUTHORITY_CHANGED")
    for key, entry in tools.items():
        if key in baseline["active_tools"]:
            if not same(entry, baseline["active_tools"][key]):
                raise ValueError("CATALOGUE_AUTHORITY_CHANGED")
        elif (not isinstance(entry, dict) or entry.get("availability") != "unavailable_on_runtime"
                or entry.get("approval_requirement") != "user_approval_required"
                or entry.get("execution_surface") != "paired_client"):
            raise ValueError("CATALOGUE_AUTHORITY_CHANGED")


def _source_member(p):
    if str(p) in SOURCE_FILES or str(p) in FROZEN_UI_SOURCES or str(p) in CHECKPOINT_METADATA:
        return True
    if len(p.parts) == 1:
        return p.name.startswith("test_") and p.suffix == ".py"
    if p.parts[:2] == ("fixtures", "c4_harness"):
        return p.suffix == ".py"
    return p.parts[0] in SOURCE_ROOTS


def rehearse(archive, expected_sha256, destination=None):
    archive = Path(archive).resolve()
    checkpoint_root = ROOT / "work/c1/checkpoints"
    if not archive.is_relative_to(checkpoint_root.resolve()) or not archive.is_file():
        raise ValueError("CHECKPOINT_SCOPE")
    if archive.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("ARCHIVE_LIMIT")
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if len(expected_sha256) != 64 or actual != expected_sha256:
        raise ValueError("CHECKPOINT_HASH")
    destination = Path(destination) if destination else ROOT / "work/c1" / ("rollback_" + uuid.uuid4().hex)
    # Reject redirection/occupied paths before writing anything.
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ValueError("FRESH_DESTINATION_REQUIRED")
    destination = destination.resolve()
    allowed = (ROOT / "work/c1").resolve()
    if allowed != ROOT / "work/c1":
        raise ValueError("ROLLBACK_ROOT_REDIRECTED")
    if not destination.is_relative_to(allowed) or destination == allowed or destination.parent != allowed:
        raise ValueError("ROLLBACK_DESTINATION_SCOPE")
    members = []
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 4096:
            raise ValueError("ARCHIVE_LIMIT")
        total = 0
        names = set()
        for item in z.infolist():
            name = item.filename
            p = PurePosixPath(name)
            mode = (item.external_attr >> 16) & 0o170000
            if (p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name or mode == 0o120000
                    or item.is_dir() or str(p) != name or not p.parts
                    or not all(_portable_component(part) for part in p.parts) or not _source_member(p)):
                raise ValueError("SOURCE_ONLY_ARCHIVE_REQUIRED")
            if (p.suffix not in {".py", ".ps1", ".json", ".md"} and p.name != ".gitignore"
                    and name not in FROZEN_UI_SOURCES and name not in CHECKPOINT_METADATA):
                raise ValueError("SOURCE_ONLY_ARCHIVE_REQUIRED")
            if name.casefold() in names:
                raise ValueError("DUPLICATE_MEMBER")
            names.add(name.casefold())
            total += item.file_size
            if total > 32 * 1024 * 1024 or item.file_size > 4 * 1024 * 1024:
                raise ValueError("ARCHIVE_LIMIT")
        # Check every expansion bound BEFORE CRC/decompression/allocation.
        if z.testzip() is not None:
            raise ValueError("ARCHIVE_INTEGRITY")
        members = [(item.filename, z.read(item)) for item in z.infolist()]
    # Provenance members are verified and recorded, never restored as source. All three or none.
    metadata = {n: d for n, d in members if n in CHECKPOINT_METADATA}
    members = [(n, d) for n, d in members if n not in CHECKPOINT_METADATA]
    if metadata and (set(metadata) != CHECKPOINT_METADATA or metadata["GIT_HEAD.txt"] != (BASELINE + "\n").encode()):
        raise ValueError("CHECKPOINT_METADATA_INVALID")
    # Recover the accepted code base as well as the delta, rather than only
    # proving ZIP extraction. Public package metadata/catalogue are the only
    # accepted JSON here; no installed data, credentials or model config.
    baseline_zip = subprocess.check_output(["git", "-C", str(ROOT), "archive", "--format=zip", BASELINE,
        "uri_core", "scripts", "requirements.txt", "uri_workspace/capabilities_registry.json"])
    base_members = []
    with zipfile.ZipFile(io.BytesIO(baseline_zip)) as base:
        for item in base.infolist():
            p = PurePosixPath(item.filename)
            if not item.is_dir() and (p.suffix in {".py", ".ps1"} or p.name == "requirements.txt"
                    or item.filename == "uri_workspace/capabilities_registry.json"
                    or p.parts[0] == "uri_core" and p.name in {"package.json", "package-lock.json"}):
                base_members.append((item.filename, base.read(item)))
    base_names = {n.casefold(): n for n, _ in base_members}
    if any(base_names.get(n.casefold(), n) != n for n, _ in members):
        raise ValueError("DUPLICATE_MEMBER")
    overlay = dict(members)
    if CATALOGUE in overlay:
        _catalogue_authority(overlay[CATALOGUE], dict(base_members)[CATALOGUE])
    # All validation completed before creating the fresh destination.
    destination.mkdir()
    sid = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True).strip().split(",")[-1].strip('"')
    acl = subprocess.run(["icacls", str(destination), "/inheritance:r", "/grant:r", "*"+sid+":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], capture_output=True)
    if acl.returncode:
        raise ValueError("ROLLBACK_ACL_FAILED")
    hashes = {}
    for name, data in base_members + members:
        out = destination / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        if hashlib.sha256(out.read_bytes()).hexdigest() != expected:
            raise ValueError("RESTORE_HASH")
        # Parse Python without importing application or creating caches.
        if out.suffix == ".py" and name in {n for n, _ in members}:
            compile(data, name, "exec")
        hashes[name] = expected
    # Re-read the finished tree: every recorded file holds its final bytes and nothing else exists.
    final = dict(base_members) | overlay
    on_disk = {q.relative_to(destination).as_posix() for q in destination.rglob("*") if q.is_file()}
    if on_disk != set(final) or any(hashlib.sha256((destination / n).read_bytes()).hexdigest()
                                    != hashlib.sha256(d).hexdigest() for n, d in final.items()):
        raise ValueError("RESTORE_HASH")
    evidence = {"schema_version": 1, "status": "OFFLINE_SOURCE_OVERLAY_RECOVERY_PASSED",
        "archive_sha256": actual, "source_files": len(members), "base_source_files": len(base_members),
        "base_checkpoint": BASELINE, "restored_files": len(hashes), "restored_digest":
        hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "checkpoint_metadata": {n: hashlib.sha256(d).hexdigest() for n, d in sorted(metadata.items())},
        "fresh_destination": True, "production_cutover": False, "private_data_restored": False,
        "application_started": False, "limitation": "Accepted runtime code plus source overlay, not full installation, dependencies or client state; private state needs separate journal/DPAPI recovery."}
    (destination / "rollback-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.archive, args.sha256)))
    except Exception:
        raise SystemExit("OFFLINE_ROLLBACK_REFUSED") from None
