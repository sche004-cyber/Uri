"""Deterministic crash injection for qualification. Inert unless URI_SUPERVISOR_CRASH_AT names a point.

`os._exit` runs no cleanup, no atexit, no finally blocks: for SQLite this is indistinguishable from the
process being killed at that instruction (committed WAL frames survive; uncommitted work does not).
It does NOT model power loss or OS-level write reordering; see docs for what was not exercised.
"""
import os


def hit(name: str):
    target = os.environ.get("URI_SUPERVISOR_CRASH_AT")
    if target and target == name:
        os._exit(137)
