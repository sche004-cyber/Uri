"""Repairs for review URI-OFFICE-M1-c findings (2026-10-12)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# R1-06: shared files that other milestones also edit keep their canonical LF line endings, so the Office changes
# stay small additive diffs instead of whole-file rewrites.
SHARED_LF = [
    "uri_ui/analysis_options.yaml",
    "uri_ui/lib/living/living_scope.dart",
    "uri_ui/lib/living/presentation/presentation_controller.dart",
    "uri_ui/lib/living/screens/workspace_mode_view.dart",
    "uri_ui/lib/main.dart",
    "uri_ui/pubspec.yaml",
]


def test_shared_files_keep_lf_line_endings():
    crlf = [p for p in SHARED_LF if b"\r\n" in (ROOT / p).read_bytes()]
    assert crlf == [], crlf
