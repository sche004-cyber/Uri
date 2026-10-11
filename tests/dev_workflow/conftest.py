"""Platform-gated tests (DEV-LIFECYCLE-2): a test marked ``windows_only`` runs only on Windows, one marked ``linux_only``
only on Linux (setsid / child-subreaper mechanisms). On any other platform it is reported BY NAME as platform-gated in
the summary, never skipped silently: it is NOT VERIFIED there."""
import sys

import pytest

_GATED = []
_ONLY = {"windows_only": ("Windows", sys.platform == "win32"),
         "linux_only": ("Linux", sys.platform.startswith("linux"))}


def pytest_configure(config):
    config.addinivalue_line("markers", "windows_only: needs Windows (job objects); platform-gated elsewhere")
    config.addinivalue_line("markers", "linux_only: needs Linux (setsid, child subreaper); platform-gated elsewhere")


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker, (os_name, here) in _ONLY.items():
            if item.get_closest_marker(marker) and not here:
                _GATED.append((os_name, item.nodeid))
                item.add_marker(pytest.mark.skip(
                    reason=f"PLATFORM-GATED: {os_name} only; NOT VERIFIED on {sys.platform}"))


def pytest_terminal_summary(terminalreporter):
    if _GATED:
        terminalreporter.write_sep("=", f"PLATFORM-GATED: {len(_GATED)} test(s) NOT VERIFIED on {sys.platform}")
        for os_name, n in _GATED:
            terminalreporter.write_line(f"PLATFORM-GATED ({os_name} only) {n}")
