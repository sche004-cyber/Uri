"""Platform-gated tests (DEV-LIFECYCLE-2): a test marked ``windows_only`` runs only on Windows. On any other platform
it is reported BY NAME as platform-gated in the summary, never skipped silently: it is NOT VERIFIED there."""
import sys

import pytest

_GATED = []


def pytest_configure(config):
    config.addinivalue_line("markers", "windows_only: needs Windows (job objects); platform-gated elsewhere")


def pytest_collection_modifyitems(config, items):
    if sys.platform == "win32":
        return
    for item in items:
        if item.get_closest_marker("windows_only"):
            _GATED.append(item.nodeid)
            item.add_marker(pytest.mark.skip(reason=f"PLATFORM-GATED: Windows only; NOT VERIFIED on {sys.platform}"))


def pytest_terminal_summary(terminalreporter):
    if _GATED:
        terminalreporter.write_sep("=", f"PLATFORM-GATED: {len(_GATED)} Windows-only test(s) NOT VERIFIED on "
                                        f"{sys.platform}")
        for n in _GATED:
            terminalreporter.write_line(f"PLATFORM-GATED {n}")
