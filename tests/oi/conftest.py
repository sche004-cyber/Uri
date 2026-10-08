import pytest


@pytest.fixture(autouse=True)
def _release_ledger_owners():
    """Ledger ownership is process-wide; release it after every test so tmp ledgers are independent."""
    yield
    from uri_operational_intelligence import task_ledger
    import msvcrt
    import os
    with task_ledger._OWNERS_LOCK:
        fds = list(task_ledger._OWNERS.values())
        task_ledger._OWNERS.clear()
    for fd in fds:
        try:
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        os.close(fd)
