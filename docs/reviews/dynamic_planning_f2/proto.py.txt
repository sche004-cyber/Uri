"""F2 research prototypes (scratch only; not repository code).

M1 pin(adapter): adapter identity must match a pinned (module, qualname, module-file sha256)
   and the function object/code captured when this module was imported.
M2 guard(root): a process-wide audit hook, active only while one adapter runs, that refuses
   mutating filesystem calls outside `root`, process creation, sockets, ctypes loading and
   introspection used to reach the guard's own state.
"""
import hashlib, inspect, os, sys, threading
from pathlib import Path

# ---- M1 -------------------------------------------------------------------------------
from uri_v1.execution.planning import actions as _actions

def _file_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()

PINS = {  # what the qualification record would carry per (action_id, version)
    (_actions.INSPECT, "1"): ("uri_v1.execution.planning.actions", "inspect_structure"),
    (_actions.SELECT, "1"): ("uri_v1.execution.planning.actions", "select"),
    (_actions.COMPARE, "1"): ("uri_v1.execution.planning.actions", "compare"),
    (_actions.WRITE, "1"): ("uri_v1.execution.planning.actions", "write_report"),
}
PINNED_FILE_SHA = _file_sha(_actions.__file__)
_CAPTURED = {k: getattr(_actions, q) for k, (_, q) in PINS.items()}
_CAPTURED_CODE = {k: f.__code__ for k, f in _CAPTURED.items()}

def pin_check(key, adapter):
    pin = PINS.get(key)
    if pin is None: return "UNPINNED"
    module, qualname = pin
    if adapter is not _CAPTURED[key] or adapter.__code__ is not _CAPTURED_CODE[key]: return "IDENTITY"
    if getattr(sys.modules.get(module), qualname, None) is not adapter: return "MODULE_ATTR"
    if _file_sha(sys.modules[module].__file__) != PINNED_FILE_SHA: return "SOURCE"
    return None

# ---- M2 -------------------------------------------------------------------------------
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_PATH_EVENTS = {"os.remove": 0, "os.rename": (0, 1), "os.rmdir": 0, "os.mkdir": 0, "os.chmod": 0, "os.chown": 0,
                "os.truncate": 0, "os.link": (0, 1), "os.symlink": (0, 1), "os.utime": 0, "os.setxattr": 0,
                "os.removexattr": 0, "shutil.rmtree": 0, "shutil.copyfile": (1,), "shutil.copytree": (1,),
                "shutil.move": (0, 1), "shutil.make_archive": 0, "shutil.unpack_archive": (1,)}
_DENY = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "os.kill",
         "os.killpg", "os.startfile", "pty.spawn", "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg",
         "ctypes.dlopen", "ctypes.dlsym", "ctypes.cdata", "ctypes.call_function", "ctypes.addressof", "ctypes.string_at",
         "ctypes.wstring_at", "ctypes.PyObj_FromPtr", "sys.addaudithook", "sys.settrace", "sys.setprofile", "sys._getframe",
         "sys._current_frames", "gc.get_referrers", "gc.get_referents", "gc.get_objects", "mmap.__new__", "os.chdir",
         "os.fchmod", "os.fchown", "os.ftruncate", "os.putenv", "os.unsetenv", "webbrowser.open", "urllib.Request",
         "code.__new__", "function.__new__", "object.__setattr__", "object.__delattr__")

class Violation(PermissionError):
    pass

def _install():
    state = {"root": None, "token": None, "violations": []}
    def inside(p):
        if isinstance(p, int): return False          # an fd: unknown target, refuse writes
        try:
            p = os.fsdecode(p)
            return os.path.realpath(p).startswith(state["root"] + os.sep)
        except Exception:
            return False
    def hook(event, args):
        root = state["root"]
        if root is None: return
        if event == "open":
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (mode is None and flags & _WRITE_FLAGS)
            if writing and not inside(path):
                state["violations"].append((event, str(path)[:120])); raise Violation(event)
            return
        if event in _PATH_EVENTS:
            idx = _PATH_EVENTS[event]
            for i in (idx if isinstance(idx, tuple) else (idx,)):
                if i < len(args) and not inside(args[i]):
                    state["violations"].append((event, str(args[i])[:120])); raise Violation(event)
            return
        if event.startswith(_DENY):
            state["violations"].append((event, "")); raise Violation(event)
    sys.addaudithook(hook)
    def enter(root):
        token = object()
        state.update(root=os.path.realpath(root), token=token, violations=[])
        return token
    def leave(token):
        if token is not state["token"]: raise Violation("GUARD_TOKEN")
        v = state["violations"]; state.update(root=None, token=None, violations=[])
        return v
    return enter, leave

_enter, _leave = _install()

def guarded(root, fn, *args):
    """Run fn under the guard. Returns (result, exception, violations, new_threads)."""
    before = set(threading.enumerate())
    token = _enter(root)
    result = exc = None
    try:
        result = fn(*args)
    except BaseException as e:
        exc = e
    violations = _leave(token)
    new_threads = [t for t in threading.enumerate() if t not in before and t.is_alive()]
    return result, exc, violations, new_threads
