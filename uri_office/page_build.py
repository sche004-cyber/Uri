"""Reproducible build of the Office sheet page for staging (never committed to git).

  python -m uri_office.page_build build    clean `npm ci` from the committed lockfile, `npm run build`, then verify
  python -m uri_office.page_build verify   hash the built bundle and refuse (exit 2) unless it equals BUNDLE_SHA256
  python -m uri_office.page_build hash     print the bundle hash only

The bundle hash is SHA-256 over the sorted list of (relative path, SHA-256 of file) for every file in
`uri_ui/assets/office/`, so it covers names, contents and the absence of extra files. The expected value is committed in
`uri_ui/office_web/BUNDLE_SHA256`; staging must refuse to ship any other bundle. Changing the page or its dependencies
means rebuilding twice from clean, confirming the hashes match, and committing the new value.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "uri_ui" / "office_web"
OUT = ROOT / "uri_ui" / "assets" / "office"
EXPECTED = WEB / "BUNDLE_SHA256"


class BundleRefused(Exception):
    pass


def bundle_hash(out: Path | None = None) -> str:
    out = OUT if out is None else Path(out)
    if not out.is_dir():
        raise BundleRefused(f"no built bundle at {out}")
    rows = []
    for f in sorted(p for p in out.rglob("*") if p.is_file()):
        rows.append([f.relative_to(out).as_posix(), hashlib.sha256(f.read_bytes()).hexdigest()])
    if not rows:
        raise BundleRefused("the built bundle is empty")
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def expected_hash() -> str:
    try:
        value = EXPECTED.read_text(encoding="utf-8").strip()
    except OSError:
        raise BundleRefused(f"no recorded bundle hash at {EXPECTED}") from None
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise BundleRefused("the recorded bundle hash is malformed")
    return value


def verify(out: Path | None = None) -> str:
    got, want = bundle_hash(out), expected_hash()
    if got != want:
        raise BundleRefused(f"bundle hash {got} does not match the recorded {want}; refusing to stage it")
    return got


def _npm(*args):
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise BundleRefused("npm is not installed")
    subprocess.run([npm, *args], cwd=WEB, check=True)


def build() -> str:
    shutil.rmtree(WEB / "node_modules", ignore_errors=True)
    shutil.rmtree(OUT, ignore_errors=True)
    _npm("ci", "--ignore-scripts", "--no-audit", "--no-fund")
    _npm("run", "build")
    return bundle_hash()


def main(argv=None):
    cmd = (argv or sys.argv[1:] or ["verify"])[0]
    try:
        if cmd == "build":
            got = build()
            print(json.dumps({"built": True, "bundle_sha256": got}))
            verify()
        elif cmd == "verify":
            print(json.dumps({"verified": True, "bundle_sha256": verify()}))
        elif cmd == "hash":
            print(bundle_hash())
        else:
            print("usage: python -m uri_office.page_build build|verify|hash", file=sys.stderr)
            return 64
    except BundleRefused as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
