"""Windows process identity and named Job Object containment for executor attempts.

Extends (does not modify) the frozen Phase-1 `uri_core.client_runtime.process_tree` design:
  * one NAMED job per attempt (name embeds ledger id + fence) so a restarted supervisor can find
    or prove the absence of the attempt's process tree without trusting a PID;
  * JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway flags: if the supervisor dies, the OS kills
    the executor tree (named jobs vanish when the last handle closes);
  * process identity = (pid, process creation FILETIME). A PID whose creation time differs is a
    DIFFERENT process (PID reuse) and is never signalled.

Disclosed limits: a process launched on the executor's behalf by a separate system service (Task
Scheduler, WMI, COM out-of-process server) is not a job member. Nested-job behaviour relies on
Windows 8+ nested jobs. Non-Windows hosts are unsupported for spawn (raises).
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass

IS_WINDOWS = os.name == "nt"


class ContainmentError(RuntimeError):
    pass


if IS_WINDOWS:  # pragma: no cover - exercised on Windows only
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")
    CREATE_SUSPENDED = 0x4
    _KILL_ON_CLOSE = 0x2000
    _EXT_LIMIT, _BASIC_ACCT = 9, 1
    _PROCESS_QUERY_LIMITED = 0x1000
    _SYNCHRONIZE = 0x100000
    _JOB_QUERY, _JOB_TERMINATE, _JOB_SET = 0x4, 0x8, 0x2
    _STILL_ACTIVE = 259
    _ERROR_INVALID_PARAMETER, _ERROR_ACCESS_DENIED, _ERROR_FILE_NOT_FOUND = 87, 5, 2

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f")]

    class _BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _EXT(ctypes.Structure):
        _fields_ = [("Basic", _BASIC), ("Io", _IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class _ACCT(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                    ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]

    _k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR); _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.OpenJobObjectW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR); _k32.OpenJobObjectW.restype = wintypes.HANDLE
    _k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID)
    _k32.QueryInformationJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE); _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT); _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,); _k32.CloseHandle.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD); _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT); _k32.TerminateProcess.restype = wintypes.BOOL
    _k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)); _k32.GetExitCodeProcess.restype = wintypes.BOOL
    _k32.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME))
    _k32.GetProcessTimes.restype = wintypes.BOOL
    _ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,); _ntdll.NtResumeProcess.restype = ctypes.c_long

    def _err(what):
        return ContainmentError(f"{what} failed (winerror {ctypes.get_last_error()})")


def _need_windows():
    if not IS_WINDOWS:
        raise ContainmentError("WINDOWS_REQUIRED")


def _ft(f):
    return (f.dwHighDateTime << 32) | f.dwLowDateTime


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    create_time: int          # FILETIME (100ns since 1601) of process creation
    job_name: str


def process_create_time(pid: int):
    """FILETIME creation time of a LIVE process, or None if no such process / not queryable."""
    _need_windows()
    h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        return None
    try:
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return None
        return _ft(c)
    finally:
        _k32.CloseHandle(h)


def identity_state(pid: int | None, create_time: int | None) -> str:
    """ALIVE_MATCH | DEAD | PID_REUSED | UNKNOWN. Never signals anything."""
    _need_windows()
    if pid is None or create_time is None:
        return "UNKNOWN"
    h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED, False, pid)
    if not h:
        code = ctypes.get_last_error()
        if code == _ERROR_INVALID_PARAMETER:
            return "DEAD"                 # no process with that PID now
        return "UNKNOWN"                  # exists but not inspectable
    try:
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return "UNKNOWN"
        if _ft(c) != create_time:
            return "PID_REUSED"
        code = wintypes.DWORD()
        if not _k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return "UNKNOWN"
        return "ALIVE_MATCH" if code.value == _STILL_ACTIVE else "DEAD"
    finally:
        _k32.CloseHandle(h)


def job_name_for(ledger_id: str, fence: int) -> str:
    return f"Local\\uri-sup-{ledger_id[:12]}-{fence}"


def job_state(name: str):
    """(exists, active_process_count). A named job exists only while some handle to it is open."""
    _need_windows()
    h = _k32.OpenJobObjectW(_JOB_QUERY, False, name)
    if not h:
        return (False, 0)
    try:
        acct = _ACCT()
        if not _k32.QueryInformationJobObject(h, _BASIC_ACCT, ctypes.byref(acct), ctypes.sizeof(acct), None):
            raise _err("QueryInformationJobObject")
        return (True, int(acct.ActiveProcesses))
    finally:
        _k32.CloseHandle(h)


def terminate_named_job(name: str, settle_s: float = 5.0) -> bool:
    """Terminate every process in the named job. True only when the job is gone or empty."""
    _need_windows()
    h = _k32.OpenJobObjectW(_JOB_QUERY | _JOB_TERMINATE, False, name)
    if not h:
        return True  # no such job: nothing of ours is alive under it
    try:
        _k32.TerminateJobObject(h, 1)
        deadline = time.monotonic() + settle_s
        while time.monotonic() < deadline:
            acct = _ACCT()
            if _k32.QueryInformationJobObject(h, _BASIC_ACCT, ctypes.byref(acct), ctypes.sizeof(acct), None) \
                    and acct.ActiveProcesses == 0:
                return True
            time.sleep(0.02)
        return False
    finally:
        _k32.CloseHandle(h)


def terminate_identity(pid: int, create_time: int, settle_s: float = 5.0) -> bool:
    """Terminate `pid` ONLY if its creation time still equals `create_time`. True when confirmed gone."""
    _need_windows()
    if identity_state(pid, create_time) != "ALIVE_MATCH":
        return identity_state(pid, create_time) in ("DEAD", "PID_REUSED")
    h = _k32.OpenProcess(0x1 | _SYNCHRONIZE | _PROCESS_QUERY_LIMITED, False, pid)   # PROCESS_TERMINATE
    if not h:
        return False
    try:
        if process_create_time(pid) != create_time:   # re-check on the handle's PID just before signalling
            return True
        _k32.TerminateProcess(h, 1)
        deadline = time.monotonic() + settle_s
        while time.monotonic() < deadline:
            if identity_state(pid, create_time) in ("DEAD", "PID_REUSED"):
                return True
            time.sleep(0.02)
        return False
    finally:
        _k32.CloseHandle(h)


class ContainedProcess:
    """A Popen whose whole tree lives in one named, kill-on-close job owned by this supervisor."""

    def __init__(self, proc: subprocess.Popen, job_handle, name: str, identity: ProcessIdentity):
        self.proc, self._job, self.name, self.identity = proc, job_handle, name, identity

    def active(self) -> int:
        if not self._job:
            return 0
        acct = _ACCT()
        if not _k32.QueryInformationJobObject(self._job, _BASIC_ACCT, ctypes.byref(acct), ctypes.sizeof(acct), None):
            raise _err("QueryInformationJobObject")
        return int(acct.ActiveProcesses)

    def kill(self, settle_s: float = 5.0) -> bool:
        """True only once the job is confirmed empty."""
        if not self._job:
            return False
        _k32.TerminateJobObject(self._job, 1)
        deadline = time.monotonic() + settle_s
        while True:
            try:
                if self.active() == 0:
                    return True
            except ContainmentError:
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)

    def close(self):
        h, self._job = self._job, None
        if h:
            _k32.CloseHandle(h)  # kill-on-close: survivors die here


_SELF_JOB = None
_SELF_CONTAINMENT = None


def contain_current_process() -> str:
    """SUP-1 (Phase 2 operational qualification, 2026-10-08): put THIS process (the one that hosts the supervisor) into
    an unnamed job with KILL_ON_JOB_CLOSE whose only handle this process holds for its whole life.

    Why: `spawn_contained` creates the executor suspended and only then assigns it to the attempt's job. A supervisor
    killed inside that window (during CreateProcess, or before AssignProcessToJobObject) used to leave a suspended,
    never-running orphan. A child created by a job member is a member of that job FROM CREATION (no breakaway flags are
    used anywhere), so once this process is contained, its death closes the job and the OS kills every descendant,
    including one that never reached its own attempt job. The attempt job then nests under it (Windows 8+); nothing about
    the attempt job, the ledger or recovery changes, and no authority is added (the job only kills, at this process's
    death, what this process itself started).

    Idempotent; never raises. Returns "CONTAINED", "ALREADY_CONTAINED" or "UNAVAILABLE:<reason>" (for example when the
    host placed this process in a job that forbids nesting); UNAVAILABLE leaves the earlier, recorded window."""
    global _SELF_JOB, _SELF_CONTAINMENT
    if _SELF_CONTAINMENT is not None:
        return "ALREADY_CONTAINED" if _SELF_CONTAINMENT == "CONTAINED" else _SELF_CONTAINMENT
    if not IS_WINDOWS:
        _SELF_CONTAINMENT = "UNAVAILABLE:NOT_WINDOWS"
        return _SELF_CONTAINMENT
    job = _k32.CreateJobObjectW(None, None)
    if not job:
        _SELF_CONTAINMENT = "UNAVAILABLE:CreateJobObjectW:%d" % ctypes.get_last_error()
        return _SELF_CONTAINMENT
    info = _EXT()
    info.Basic.LimitFlags = _KILL_ON_CLOSE
    if not _k32.SetInformationJobObject(job, _EXT_LIMIT, ctypes.byref(info), ctypes.sizeof(info)):
        _SELF_CONTAINMENT = "UNAVAILABLE:SetInformationJobObject:%d" % ctypes.get_last_error()
        _k32.CloseHandle(job)
        return _SELF_CONTAINMENT
    _k32.GetCurrentProcess.restype = wintypes.HANDLE
    if not _k32.AssignProcessToJobObject(job, _k32.GetCurrentProcess()):
        _SELF_CONTAINMENT = "UNAVAILABLE:AssignProcessToJobObject:%d" % ctypes.get_last_error()
        _k32.CloseHandle(job)
        return _SELF_CONTAINMENT
    _SELF_JOB = job                      # deliberately never closed: it closes when this process ends
    _SELF_CONTAINMENT = "CONTAINED"
    return _SELF_CONTAINMENT


def spawn_contained(argv, name: str, before_resume=None, **popen_kwargs) -> ContainedProcess:
    """Start `argv` suspended, bind it to a fresh named job, hand its identity to `before_resume`
    (which must make it durable), and only then resume. The executor cannot run a single instruction
    before its identity is in the ledger; if `before_resume` raises, the suspended process is killed."""
    _need_windows()
    if popen_kwargs.get("shell") or "creationflags" in popen_kwargs:
        raise ContainmentError("CONTAINMENT_OPTIONS_RESERVED")
    job = _k32.CreateJobObjectW(None, name)
    if not job:
        raise _err("CreateJobObjectW")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: someone else's job under our name
        _k32.CloseHandle(job)
        raise ContainmentError("JOB_NAME_COLLISION")
    info = _EXT()
    info.Basic.LimitFlags = _KILL_ON_CLOSE  # deliberately no BREAKAWAY_OK / SILENT_BREAKAWAY_OK
    if not _k32.SetInformationJobObject(job, _EXT_LIMIT, ctypes.byref(info), ctypes.sizeof(info)):
        err = _err("SetInformationJobObject"); _k32.CloseHandle(job); raise err
    try:
        proc = subprocess.Popen(argv, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                                | CREATE_SUSPENDED, **popen_kwargs)
    except BaseException:
        _k32.CloseHandle(job); raise
    try:
        if not _k32.AssignProcessToJobObject(job, int(proc._handle)):
            raise _err("AssignProcessToJobObject")
        ct = process_create_time(proc.pid)
        if ct is None:
            raise ContainmentError("CREATE_TIME_UNAVAILABLE")
        ident = ProcessIdentity(proc.pid, ct, name)
        if before_resume is not None:
            before_resume(ident)
        if _ntdll.NtResumeProcess(int(proc._handle)) != 0:
            raise ContainmentError("NtResumeProcess failed")
    except BaseException:
        _k32.TerminateProcess(int(proc._handle), 1)
        proc.wait()
        _k32.CloseHandle(job)
        raise
    return ContainedProcess(proc, job, name, ident)
