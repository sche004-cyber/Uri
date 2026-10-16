"""Windows Job Objects through ctypes (plan §5 `render.py`, spike S3). No pywin32.

A job is created with KILL_ON_JOB_CLOSE (closing the handle, or the service process ending, kills every process in
it) and an optional per-process memory limit. Children started by an assigned process join the job automatically.
On other platforms `Job` is a no-op holder, so the pure parts of the service stay testable there; the engine layer
refuses to start engines outside Windows.
"""
from __future__ import annotations

import ctypes
import os
import threading

KILL_ON_JOB_CLOSE = 0x2000
LIMIT_PROCESS_MEMORY = 0x100
LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x400      # no Windows Error Reporting dialog or dump for a crashing child
_EXTENDED_LIMIT_INFORMATION = 9
_STILL_ACTIVE = 259

if os.name == "nt":
    import ctypes.wintypes as W

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.restype = W.HANDLE
    _k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, W.LPCWSTR)
    _k32.OpenProcess.restype = W.HANDLE
    _k32.OpenProcess.argtypes = (W.DWORD, W.BOOL, W.DWORD)
    _k32.SetInformationJobObject.argtypes = (W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD)
    _k32.QueryInformationJobObject.argtypes = (W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD, ctypes.c_void_p)
    _k32.AssignProcessToJobObject.argtypes = (W.HANDLE, W.HANDLE)
    _k32.CloseHandle.argtypes = (W.HANDLE,)
    _k32.GetExitCodeProcess.argtypes = (W.HANDLE, ctypes.POINTER(W.DWORD))
    _k32.TerminateJobObject.argtypes = (W.HANDLE, ctypes.c_uint)

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class _BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", W.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]

    class _EXT(ctypes.Structure):
        _fields_ = [("Basic", _BASIC), ("Io", _IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]


class JobError(OSError):
    pass


class Job:
    """One Windows Job Object. `close()` (or garbage collection, or the service exiting) kills its processes."""

    def __init__(self, memory_limit: int | None = None):
        self._lock = threading.Lock()
        self.handle = None
        if os.name != "nt":
            return
        h = _k32.CreateJobObjectW(None, None)
        if not h:
            raise JobError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = _EXT()
        info.Basic.LimitFlags = KILL_ON_JOB_CLOSE | LIMIT_DIE_ON_UNHANDLED_EXCEPTION | (
            LIMIT_PROCESS_MEMORY if memory_limit else 0)
        if memory_limit:
            info.ProcessMemoryLimit = memory_limit
        if not _k32.SetInformationJobObject(h, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            _k32.CloseHandle(h)
            raise JobError(err, "SetInformationJobObject failed")
        self.handle = h

    def assign(self, pid: int) -> None:
        if os.name != "nt":
            return
        ph = _k32.OpenProcess(0x1F0FFF, False, pid)
        if not ph:
            raise JobError(ctypes.get_last_error(), "OpenProcess failed")
        try:
            if not _k32.AssignProcessToJobObject(self.handle, ph):
                raise JobError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
        finally:
            _k32.CloseHandle(ph)

    def peak_process_memory(self) -> int | None:
        if os.name != "nt" or not self.handle:
            return None
        info = _EXT()
        if not _k32.QueryInformationJobObject(self.handle, _EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                              ctypes.sizeof(info), None):
            return None
        return int(info.PeakProcessMemoryUsed)

    def close(self) -> None:
        with self._lock:
            h, self.handle = self.handle, None
        if h and os.name == "nt":
            _k32.TerminateJobObject(h, 1)
            _k32.CloseHandle(h)

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter shutdown
            pass


CREATE_SUSPENDED = 0x4
CREATE_NO_WINDOW = 0x08000000


def spawn(args, job: Job, **popen_kw):
    """Start `args` suspended, put it in `job`, then let it run, so not even its first child can start outside the
    job. Returns the Popen. If assignment fails the process is killed and JobError is raised."""
    import subprocess
    if os.name != "nt":
        return subprocess.Popen(args, **popen_kw)
    flags = popen_kw.pop("creationflags", 0) | CREATE_SUSPENDED | CREATE_NO_WINDOW
    p = subprocess.Popen(args, creationflags=flags, **popen_kw)
    try:
        job.assign(p.pid)
    except BaseException:
        p.kill()
        p.wait(10)
        raise
    ph = _k32.OpenProcess(0x0800, False, p.pid)       # PROCESS_SUSPEND_RESUME
    try:
        if not ph or ctypes.WinDLL("ntdll").NtResumeProcess(W.HANDLE(ph)) != 0:
            p.kill()
            raise JobError(0, "could not resume the engine process")
    finally:
        if ph:
            _k32.CloseHandle(ph)
    return p


def alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    h = _k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = W.DWORD()
    try:
        _k32.GetExitCodeProcess(h, ctypes.byref(code))
    finally:
        _k32.CloseHandle(h)
    return code.value == _STILL_ACTIVE
