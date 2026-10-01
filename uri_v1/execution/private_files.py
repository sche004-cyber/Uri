"""Owner-only secret files on both POSIX and Windows.

POSIX: created exclusively with mode 0o600 (owner read/write, nothing for group or
other). Windows ignores POSIX mode bits beyond the read-only flag, so a `0o600`
request there leaves the file readable under whatever the parent directory's
inherited ACL grants. There the file is instead created exclusively with a
*protected* DACL (no inherited entries) holding exactly one entry: full control for
the current user's SID. `is_private` checks the platform's own form of the same
requirement, so tests assert the guarantee rather than a POSIX-only mode number.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

if os.name == "nt":  # pragma: no cover - exercised on Windows only
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _adv = ctypes.WinDLL("advapi32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _TOKEN_QUERY = 0x0008
    _TokenUser = 1
    _SDDL_REVISION_1 = 1
    _SE_FILE_OBJECT = 1
    _DACL_SECURITY_INFORMATION = 0x00000004
    _GENERIC_WRITE = 0x40000000
    _CREATE_NEW = 1
    _FILE_ATTRIBUTE_NORMAL = 0x80
    _INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    class _SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID), ("bInheritHandle", wintypes.BOOL)]

    _adv.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    _adv.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    _adv.ConvertSidToStringSidW.argtypes = (wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR))
    _adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.ULONG))
    _adv.GetNamedSecurityInfoW.argtypes = (wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
                                           wintypes.LPVOID, wintypes.LPVOID, ctypes.POINTER(wintypes.LPVOID))
    _adv.GetNamedSecurityInfoW.restype = wintypes.DWORD
    _adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = (
        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.ULONG))
    _k32.GetCurrentProcess.restype = wintypes.HANDLE
    _k32.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_SECURITY_ATTRIBUTES),
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.LocalFree.argtypes = (wintypes.HLOCAL,)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def _err(what: str) -> OSError:
        return ctypes.WinError(ctypes.get_last_error(), what)

    def current_user_sid() -> str:
        token = wintypes.HANDLE()
        if not _adv.OpenProcessToken(_k32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)): raise _err("OpenProcessToken")
        try:
            size = wintypes.DWORD()
            _adv.GetTokenInformation(token, _TokenUser, None, 0, ctypes.byref(size))
            buf = ctypes.create_string_buffer(size.value)
            if not _adv.GetTokenInformation(token, _TokenUser, buf, size, ctypes.byref(size)): raise _err("GetTokenInformation")
            psid = ctypes.cast(buf, ctypes.POINTER(wintypes.LPVOID))[0]  # TOKEN_USER.User.Sid
            text = wintypes.LPWSTR()
            if not _adv.ConvertSidToStringSidW(psid, ctypes.byref(text)): raise _err("ConvertSidToStringSidW")
            try:
                return text.value
            finally:
                _k32.LocalFree(ctypes.cast(text, wintypes.HLOCAL))
        finally:
            _k32.CloseHandle(token)

    def _dacl_sddl(path: Path) -> str:
        psd = wintypes.LPVOID()
        rc = _adv.GetNamedSecurityInfoW(str(path), _SE_FILE_OBJECT, _DACL_SECURITY_INFORMATION, None, None, None, None,
                                        ctypes.byref(psd))
        if rc: raise ctypes.WinError(rc)
        try:
            text = wintypes.LPWSTR()
            if not _adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(psd, _SDDL_REVISION_1, _DACL_SECURITY_INFORMATION,
                                                                            ctypes.byref(text), None):
                raise _err("ConvertSecurityDescriptorToStringSecurityDescriptorW")
            try:
                return text.value
            finally:
                _k32.LocalFree(ctypes.cast(text, wintypes.HLOCAL))
        finally:
            _k32.LocalFree(ctypes.cast(psd, wintypes.HLOCAL))


def owner_only_sddl(sid: str) -> str:
    """Protected DACL (`P`: nothing inherited) with one full-control entry for `sid`."""
    return f"D:P(A;;FA;;;{sid})"


def sddl_is_owner_only(sddl: str, sid: str) -> bool:
    """True iff `sddl`'s DACL is protected and every entry allows only `sid`.

    No entries at all (`D:P`) also counts: nobody, not even another user, has access.
    A NULL DACL (`D:NO_ACCESS_CONTROL`) or any inherited/foreign/deny-less entry fails.
    """
    m = re.fullmatch(r"D:([A-Z_]*)((?:\([^)]*\))*)", sddl.strip())
    if not m or "P" not in m.group(1) or "NO_ACCESS_CONTROL" in m.group(1): return False
    for ace in re.findall(r"\(([^)]*)\)", m.group(2)):
        parts = ace.split(";")
        if len(parts) < 6 or parts[0] != "A" or "ID" in parts[1] or parts[5].upper() != sid.upper(): return False
    return True


def write_private(path: Path, data: bytes) -> None:
    """Create `path` exclusively, readable and writable by the current user only."""
    if os.name != "nt":
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f: f.write(data)
        return
    psd = wintypes.LPVOID()  # pragma: no cover - Windows only below
    if not _adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(owner_only_sddl(current_user_sid()), _SDDL_REVISION_1,
                                                                     ctypes.byref(psd), None):
        raise _err("ConvertStringSecurityDescriptorToSecurityDescriptorW")
    try:
        sa = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), psd, False)
        h = _k32.CreateFileW(str(path), _GENERIC_WRITE, 0, ctypes.byref(sa), _CREATE_NEW, _FILE_ATTRIBUTE_NORMAL, None)
        if h == _INVALID_HANDLE_VALUE or not h: raise _err("CreateFileW")
    finally:
        _k32.LocalFree(ctypes.cast(psd, wintypes.HLOCAL))
    fd = msvcrt.open_osfhandle(h, os.O_WRONLY | os.O_BINARY)
    with os.fdopen(fd, "wb") as f: f.write(data)


def is_private(path: Path) -> bool:
    """True iff only the current user can access `path` (platform-appropriate check)."""
    if os.name != "nt":
        st = os.stat(path)
        return st.st_uid == os.geteuid() and st.st_mode & 0o077 == 0
    return sddl_is_owner_only(_dacl_sddl(Path(path)), current_user_sid())  # pragma: no cover - Windows only
