"""PA-11 preparation: build the GUEST bundle for the throwaway power-loss VM (operational qualification, 2026-10-08).

The guest needs only stock Python 3.13 and: `uri_supervisor/` (the code under test), the power-loss harness, the fake
NDJSON executor, and a Task Scheduler installer that is run INSIDE the VM. The bundle keeps the tree layout, so the
harness finds its executor exactly as in this worktree. Every file is listed with its SHA-256 in `MANIFEST.json`, so the
VM's copy can be compared with the tree the campaign claims to qualify.

This script only reads the tree and writes one zip (default `<evidence>/phase2oq/powerloss_guest_bundle.zip`). It never
creates a VM, never schedules anything on this PC and never powers anything off. The installer it embeds refuses to
run unless called with `-IAmInsideTheThrowawayVM`.

Usage: .venv/Scripts/python.exe -I scripts/phase2oq_powerloss_bundle.py [--out <zip>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted([*(p.relative_to(ROOT).as_posix() for p in (ROOT / "uri_supervisor").glob("*.py")),
                "scripts/phase2close_powerloss_harness.py", "tests/phase2a/helpers/fake_executor.py"])

INSTALLER = r'''# URI power-loss GUEST installer. Run INSIDE the throwaway VM only, as the auto-logon user, in an elevated PowerShell.
param(
    [switch]$IAmInsideTheThrowawayVM,
    [string]$Python = "C:\Python313\python.exe",
    [string]$Ledger = "D:\pl\ledger.db",
    [string]$HostAddress = "10.0.2.2",
    [int]$Port = 47710,
    [ValidateSet("FULL", "NORMAL")][string]$Synchronous = "FULL"
)
if (-not $IAmInsideTheThrowawayVM) { throw "Refused: pass -IAmInsideTheThrowawayVM. Never install this on a real PC." }
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$harness = Join-Path $root "scripts\phase2close_powerloss_harness.py"
$arguments = "-I -B `"$harness`" guest --ledger `"$Ledger`" --host $HostAddress --port $Port --synchronous $Synchronous"
$action = New-ScheduledTaskAction -Execute $Python -Argument $arguments -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName "URI-PowerLoss-Guest" -Action $action -Trigger $trigger -RunLevel Limited -Force | Out-Null
Write-Output "Installed: URI-PowerLoss-Guest ($Synchronous) -> $HostAddress`:$Port, ledger $Ledger"
'''


def build(out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "uri.phase2oq.powerloss_guest_bundle.v1", "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "source_root": str(ROOT), "files": {}}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in FILES:
            data = (ROOT / rel).read_bytes()
            manifest["files"][rel] = hashlib.sha256(data).hexdigest()
            z.writestr(rel, data)
        z.writestr("guest/install_guest_task.ps1", INSTALLER)
        manifest["files"]["guest/install_guest_task.ps1"] = hashlib.sha256(INSTALLER.encode()).hexdigest()
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=1, sort_keys=True))
    manifest["zip"] = str(out)
    manifest["zip_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "evidence" / "phase2oq" / "powerloss_guest_bundle.zip"))
    m = build(Path(ap.parse_args().out))
    print(json.dumps({k: m[k] for k in ("zip", "zip_sha256")} | {"files": len(m["files"])}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
