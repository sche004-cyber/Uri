"""Boundary and isolation tests for dynamic planning (G8).

Ensures:
1. uri_v1/execution/planning/ never imports uri_core;
2. uri_v1/execution/planning/ never imports experimental/;
3. Zero tracked repository files were modified (strict Slice 1 zero-edit invariant).
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess


_IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_.]+)")


def test_no_uri_core_import_in_planning():
    """uri_v1/execution/planning must NEVER import uri_core (generation boundary)."""
    planning_dir = Path("uri_v1/execution/planning")
    assert planning_dir.exists()

    violations = []
    for py_file in planning_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            match = _IMPORT_PATTERN.match(line)
            if match:
                mod = match.group(1)
                if mod == "uri_core" or mod.startswith("uri_core."):
                    violations.append(f"{py_file}:{line_num}: imports {mod}")

    assert not violations, f"Boundary violation: uri_core imported in planning:\n" + "\n".join(violations)


def test_no_experimental_import_in_planning():
    """uri_v1/execution/planning must NEVER import experimental code."""
    planning_dir = Path("uri_v1/execution/planning")
    assert planning_dir.exists()

    violations = []
    for py_file in planning_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            match = _IMPORT_PATTERN.match(line)
            if match:
                mod = match.group(1)
                if mod == "experimental" or mod.startswith("experimental."):
                    violations.append(f"{py_file}:{line_num}: imports {mod}")

    assert not violations, f"Boundary violation: experimental imported in planning:\n" + "\n".join(violations)


def test_zero_tracked_modifications():
    """Slice 1 requires zero modifications to existing tracked files."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    diff_files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    assert not diff_files, f"Tracked files were modified in violation of zero-edit invariant: {diff_files}"
