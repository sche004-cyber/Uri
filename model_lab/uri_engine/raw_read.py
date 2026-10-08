"""Unbuffered sequential read throughput of a file (FILE_FLAG_NO_BUFFERING), i.e. the cold-disk lower
bound for loading a GGUF from that drive, independent of the OS file cache.

  python model_lab/uri_engine/raw_read.py <path> [chunk_mib]
"""
import ctypes
import ctypes.wintypes as w
import json
import sys
import time

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000

k32 = ctypes.windll.kernel32
k32.CreateFileW.restype = w.HANDLE
k32.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
k32.ReadFile.argtypes = [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]


def main():
    path = sys.argv[1]
    chunk = int(sys.argv[2]) * 2**20 if len(sys.argv) > 2 else 16 * 2**20
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
                        FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN, None)
    if h == w.HANDLE(-1).value or h is None:
        raise SystemExit(f"CreateFileW failed: {ctypes.GetLastError()}")
    buf = (ctypes.c_char * chunk)()
    # NO_BUFFERING needs sector-aligned buffers; ctypes arrays are page-aligned in practice for large sizes
    n = w.DWORD(0)
    total = 0
    t0 = time.perf_counter()
    while True:
        ok = k32.ReadFile(h, buf, chunk, ctypes.byref(n), None)
        if not ok:
            err = ctypes.GetLastError()
            if err == 38:  # ERROR_HANDLE_EOF
                break
            raise SystemExit(f"ReadFile failed: {err} after {total} bytes")
        if n.value == 0:
            break
        total += n.value
    t1 = time.perf_counter()
    k32.CloseHandle(h)
    res = {"path": path, "bytes": total, "seconds": round(t1 - t0, 2), "MB_per_s": round(total / (t1 - t0) / 1e6, 1)}
    print(json.dumps(res))


if __name__ == "__main__":
    main()
