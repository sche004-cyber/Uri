"""Process-tree containment and liveness that hold on both POSIX and Windows.

POSIX: the child starts in its own session/process group and the whole group is
killed with `killpg` (unchanged from M37 R-5 / M38 H-2; a child that calls
`setsid()` itself leaves the group and stays a disclosed gap there).

Windows: `taskkill /T` after the parent has exited walks a PID tree that no longer
exists, so orphaned descendants survive it. Instead every child is started
*suspended*, assigned to a fresh Job Object configured with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and no breakaway permission, and only then
resumed. Every process it (or any descendant) creates is therefore born inside the
job, including ones started with `CREATE_NEW_PROCESS_GROUP`/`DETACHED_PROCESS`, and
`CREATE_BREAKAWAY_FROM_JOB` is refused by the OS. Killing the tree is
`TerminateJobObject`, which does not depend on the parent still being alive; and
because the job handle is owned only by URI, the OS kills the whole tree if URI
itself dies before cleanup. Disclosed limit: a process started on the child's
behalf by a separate system service (Task Scheduler, WMI, a COM out-of-process
server) is not a descendant and is not in the job.

If the job cannot be created or the child cannot be assigned to it, the child is
terminated and `ContainmentError` is raised: URI never runs a Windows child it
cannot contain.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


class ContainmentError(RuntimeError):
    """A child process could not be placed under process-tree containment."""


if os.name == "nt":  # pragma: no cover - exercised on Windows only
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")

    CREATE_SUSPENDED = 0x00000004
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
    JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
    _JobObjectBasicAccountingInformation = 1
    _JobObjectExtendedLimitInformation = 9
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _SYNCHRONIZE = 0x00100000
    _WAIT_TIMEOUT = 0x00000102
    _ERROR_ACCESS_DENIED = 5

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                      "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BASIC_LIMIT(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BASIC_LIMIT), ("IoInfo", _IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class _BASIC_ACCOUNTING(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                    ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]

    _k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR); _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID)
    _k32.QueryInformationJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE); _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT); _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,); _k32.CloseHandle.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD); _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD); _k32.WaitForSingleObject.restype = wintypes.DWORD
    _k32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT); _k32.TerminateProcess.restype = wintypes.BOOL
    _ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,); _ntdll.NtResumeProcess.restype = ctypes.c_long

    def _winerr(what: str) -> ContainmentError:
        return ContainmentError(f"{what} failed (winerror {ctypes.get_last_error()})")


class JobTree:
    """A Windows Job Object owning one child and all of its descendants."""

    def __init__(self):  # pragma: no cover - Windows only
        handle = _k32.CreateJobObjectW(None, None)
        if not handle: raise _winerr("CreateJobObjectW")
        self._handle = handle
        info = _EXTENDED_LIMIT()
        # Kill-on-close, and deliberately no BREAKAWAY_OK / SILENT_BREAKAWAY_OK: a descendant
        # asking for CREATE_BREAKAWAY_FROM_JOB is refused by the OS.
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _k32.SetInformationJobObject(handle, _JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
            err = _winerr("SetInformationJobObject"); self.close(); raise err

    def limit_flags(self) -> int:  # pragma: no cover - Windows only
        info = _EXTENDED_LIMIT()
        if not _k32.QueryInformationJobObject(self._handle, _JobObjectExtendedLimitInformation, ctypes.byref(info),
                                              ctypes.sizeof(info), None):
            raise _winerr("QueryInformationJobObject")
        return int(info.BasicLimitInformation.LimitFlags)

    def active_processes(self) -> int:  # pragma: no cover - Windows only
        if self._handle is None: return 0
        acct = _BASIC_ACCOUNTING()
        if not _k32.QueryInformationJobObject(self._handle, _JobObjectBasicAccountingInformation, ctypes.byref(acct),
                                              ctypes.sizeof(acct), None):
            raise _winerr("QueryInformationJobObject")
        return int(acct.ActiveProcesses)

    def assign(self, proc: subprocess.Popen) -> None:  # pragma: no cover - Windows only
        if not _k32.AssignProcessToJobObject(self._handle, int(proc._handle)): raise _winerr("AssignProcessToJobObject")

    def kill(self, settle_s: float = 5.0) -> bool:  # pragma: no cover - Windows only
        """True only once the job is confirmed empty; a failed terminate is reported, not ignored."""
        if self._handle is None: return False
        terminated = bool(_k32.TerminateJobObject(self._handle, 1))
        deadline = time.monotonic() + settle_s
        while True:
            try: active = self.active_processes()
            except ContainmentError: return False
            if active == 0: return True
            if time.monotonic() >= deadline: return False
            if not terminated: terminated = bool(_k32.TerminateJobObject(self._handle, 1))
            time.sleep(0.02)

    def close(self) -> None:  # pragma: no cover - Windows only
        handle, self._handle = getattr(self, "_handle", None), None
        if handle: _k32.CloseHandle(handle)  # kill-on-close: anything still in the job dies here

    __del__ = close


def spawn(argv, **popen_kwargs) -> subprocess.Popen:
    """`subprocess.Popen` whose entire process tree `kill_tree` can later reach.

    Callers must not pass `creationflags` or `start_new_session`; containment owns them.
    """
    if os.name != "nt":
        return subprocess.Popen(argv, start_new_session=True, **popen_kwargs)
    job = JobTree()  # pragma: no cover - Windows only below
    try:
        proc = subprocess.Popen(argv, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED, **popen_kwargs)
    except BaseException:
        job.close(); raise
    try:
        job.assign(proc)
        if _ntdll.NtResumeProcess(int(proc._handle)) != 0: raise ContainmentError("NtResumeProcess failed")
    except BaseException:
        _k32.TerminateProcess(int(proc._handle), 1); proc.wait(); job.close(); raise
    proc._uri_job = job
    return proc


def kill_tree(proc: subprocess.Popen) -> bool:
    """Kill `proc` and every descendant, whether or not `proc` has already exited.

    Returns True only when the tree is confirmed gone. A kill that fails (a refused
    `TerminateJobObject`, a job that will not empty, a `killpg` refused with EPERM) is
    returned as False, never swallowed (Codex audit of 3cd3557): callers must treat
    the run as unsettled rather than verify a workspace a live process can still touch.
    """
    job = getattr(proc, "_uri_job", None)
    try:
        if job is not None: contained = job.kill()  # pragma: no cover - Windows only
        elif os.name == "nt":  # pragma: no cover - uncontained Windows child: cannot confirm its tree
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            contained = False
        else:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass  # the whole group is already gone
            contained = True
    except OSError:
        contained = False
    proc.wait()
    return contained


def release(proc: subprocess.Popen) -> None:
    """Drop URI's hold on the containment (on Windows, closing the job kills any survivor)."""
    job = getattr(proc, "_uri_job", None)
    if job is not None: job.close()  # pragma: no cover - Windows only


def process_alive(pid: int) -> bool:
    """True while `pid` names a running (not exited, not zombie) process.

    Replaces `os.kill(pid, 0)`, which on Windows is not a probe at all: signal 0 is
    `CTRL_C_EVENT` there and is sent to the process group. PID reuse can make a
    long-dead PID look alive again on either platform; callers use this for short
    after-kill checks only.
    """
    if os.name == "nt":  # pragma: no cover - Windows only
        h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
        if not h: return ctypes.get_last_error() == _ERROR_ACCESS_DENIED  # exists, but not ours to open
        try:
            return _k32.WaitForSingleObject(h, 0) == _WAIT_TIMEOUT
        finally:
            _k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True  # no /proc (e.g. macOS): signal probe already said it exists
