# Platform Audit: OS-Specific Assumptions in python-debugger-skill

**Date:** 2026-03-27  
**Repository:** `JPalchak/python-debugger-skill`  
**Scope:** `plugins/python-debugger/skills/python-debugging/scripts/`

---

## Summary

The debugger currently contains six categories of OS-specific assumptions that
prevent it from running on Windows.  All findings are in `debugger.py`; 
`inspector.py` has no OS-coupling and requires no changes.

---

## Findings Table

| file | lines | dependency\_type | current\_behavior | portability\_issue | target\_abstraction | planned\_pr | risk |
|---|---:|---|---|---|---|---|---|
| `debugger.py` | 290, 400 | Unix domain socket (`AF_UNIX`) | IPC between server subprocess and CLI client over a `.sock` file | `AF_UNIX` is unavailable on Windows < Python 3.9 and unreliable across Windows security models | Replace with TCP loopback socket (`AF_INET`, `127.0.0.1:0`) | PR 3 | **High** |
| `debugger.py` | 1073–1085 | `os.fork()` | Spawns debugger server as a forked child process | `os.fork()` is POSIX-only; raises `AttributeError` on Windows | Replace with `subprocess.Popen` and a hidden `_server` subcommand | PR 3 | **High** |
| `debugger.py` | 900–929 | `signal.SIGALRM` / `signal.alarm()` | Timeouts eval/exec calls in the debugger server | `SIGALRM` and `signal.alarm()` are POSIX-only | Replace with `threading.Event` + daemon thread timeout | PR 3 | **High** |
| `debugger.py` | 481 | `signal.SIGTERM` | Graceful shutdown handler in the server process | `SIGTERM` is not deliverable the same way on Windows | Guard with `sys.platform != 'win32'`; Windows shutdown via `SIGINT` only | PR 4 | **Medium** |
| `debugger.py` | 265 | `os.kill(pid, 0)` | Checks if a PID is alive | Raises `AttributeError` on very old Python builds; behavior on Windows checked | `os.kill(pid, 0)` is available on Python 3 Windows; wrap in try/except covering `PermissionError` | PR 2 | **Low** |
| `debugger.py` | 167, 183, 219–220, 252–254, 287–288, 380–384 | `.sock` file paths | Unix socket file stored alongside session JSON | Socket files are Unix-only artefacts; not applicable to TCP | Remove `.sock` file management; store TCP port in session JSON instead | PR 3 | **Medium** |

---

## Detailed Analysis

### 1. Unix Domain Sockets — `socket.AF_UNIX` (High Risk)

**Location:** `debugger.py` lines 290, 400  
**Current code:**
```python
self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
self.server_socket.bind(str(self.socket_path))
...
self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
self.socket.connect(str(self.socket_path))
```

**Why non-portable:**  
`socket.AF_UNIX` requires the kernel to support Unix domain sockets.  On
Windows this support was added experimentally in Python 3.9 with the Insider
Preview build of Windows 10, but it is not universally available and not
reliable across Windows security contexts (e.g., different user sessions).

**Replacement strategy:**  
Use a TCP loopback socket (`socket.AF_INET`, `127.0.0.1`, port 0).  The OS
assigns a random available port when binding to port 0; the chosen port is
recorded in the session JSON file so the CLI client can connect without a
filesystem socket path.  This approach works identically on all three target
platforms with no additional dependencies.

---

### 2. `os.fork()` (High Risk)

**Location:** `debugger.py` lines 1072–1085  
**Current code:**
```python
pid = os.fork()
if pid == 0:
    # Child: run debugger
    ...
else:
    # Parent: record PID
    session.create_session(pid)
```

**Why non-portable:**  
`os.fork()` is a POSIX syscall.  It does not exist on Windows at all; calling
it raises `AttributeError`.

**Replacement strategy:**  
Introduce a hidden CLI subcommand `_server` that, when invoked, runs the
debugger server in-process.  `cmd_start` spawns the subprocess with
`subprocess.Popen([sys.executable, __file__, '_server', script_path, ...])`.
`Popen` is fully cross-platform and provides a `.pid` attribute.  The
subprocess writes its own PID and TCP port to the session JSON file once the
server is bound; the parent polls the file until a non-zero port appears.

---

### 3. `signal.SIGALRM` / `signal.alarm()` (High Risk)

**Location:** `debugger.py` lines 896–929  
**Current code:**
```python
old_handler = signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(EVAL_TIMEOUT)
try:
    result = eval(expr, ...)
finally:
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old_handler)
```

**Why non-portable:**  
`signal.SIGALRM` and `signal.alarm()` are POSIX-only.  On Windows they do not
exist.

**Replacement strategy:**  
Run the eval/exec in a daemon thread.  The calling thread waits on a
`threading.Event` with a timeout.  If the event is not set within
`EVAL_TIMEOUT` seconds, return a timeout error.  The daemon thread continues
in the background but cannot block the server.  This approach is
cross-platform and requires no additional imports beyond `threading` (already
imported).

---

### 4. `signal.SIGTERM` Handler (Medium Risk)

**Location:** `debugger.py` line 481  
**Current code:**
```python
signal.signal(signal.SIGTERM, self._signal_handler)
signal.signal(signal.SIGINT, self._signal_handler)
```

**Why non-portable:**  
On Windows, `signal.SIGTERM` exists in the `signal` module (it equals 15) but
the Windows runtime does not actually deliver it from external sources the same
way POSIX does.  Calling `signal.signal(signal.SIGTERM, ...)` succeeds on
Windows but the handler will never fire from `taskkill /F` or similar.

**Replacement strategy:**  
Guard the `SIGTERM` registration with `if sys.platform != 'win32'`.  On
Windows, `SIGINT` (Ctrl+C / `GenerateConsoleCtrlEvent`) is the only reliable
external termination signal.

---

### 5. `os.kill(pid, 0)` (Low Risk)

**Location:** `debugger.py` line 265  
**Current code:**
```python
os.kill(pid, 0)
```

**Why this matters:**  
`os.kill` is documented as "Availability: Unix, Windows" since Python 3.  On
Windows, sending signal 0 uses `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`
internally and raises `OSError` if the process does not exist.  This works
correctly.  The only edge case is `PermissionError` which can be raised for
system processes (PID not found vs. access denied confusion).

**Replacement strategy:**  
No change needed beyond catching `PermissionError` in addition to `OSError` in
the `_is_process_alive` helper.  We also guard against PID=0 which has
special POSIX semantics (process group signal).

---

### 6. `.sock` File Artefacts (Medium Risk)

**Location:** `debugger.py` lines 167, 183, 219–220, 252–254, 287–288, 380–384  

**Why this matters:**  
The session manager and server both create and clean up `.sock` files.  These
files only make sense with Unix domain sockets.  After switching to TCP the
`.sock` artefacts must be removed; otherwise the code will attempt to create
and delete files it no longer uses, which is confusing and wastes I/O.

**Replacement strategy:**  
Remove all `.sock` file creation/deletion.  Store the TCP `port` (integer) in
the session JSON file instead of a `socket` file path.

---

## Platform Adapter Design

The platform adapter module (`scripts/platform/`) provides a thin abstraction
that routes OS-specific behaviour through a common interface:

```
scripts/platform/
    __init__.py      # re-exports get_adapter()
    base.py          # PlatformAdapter abstract base class
    posix.py         # POSIX (Linux/macOS) implementation
    windows.py       # Windows implementation
    factory.py       # get_adapter() factory function
```

### Adapter contract (`base.py`)

| Method | Purpose |
|---|---|
| `is_process_alive(pid)` | Check if a PID is still running |
| `terminate_process(pid)` | Gracefully terminate a process |
| `kill_process(pid)` | Forcefully kill a process |
| `get_subprocess_kwargs()` | Platform-specific `Popen` keyword arguments |

Core `debugger.py` code accesses OS behaviour only through these methods;
no raw `os.kill`, `signal.SIGTERM`, or other platform calls appear outside
`posix.py` / `windows.py`.

---

## Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| TCP loopback blocked by firewall/security software | Medium | Use `127.0.0.1` (loopback, not routable); document in troubleshooting |
| Port collision on busy systems | Low | OS port 0 allocation avoids collision; only one session per script |
| Eval timeout thread cannot be cancelled | Low | Daemon thread exits when server process exits; no resource leak |
| Windows subprocess startup latency | Medium | Parent polls for up to 10 s with 100 ms sleep; tunable via `START_TIMEOUT` |
| Stale session file race on fast restart | Low | Parent deletes stale session before spawning; subprocess creates new file |

---

## Behavior Contract

### Session lifecycle

1. **Start:** CLI calls `cmd_start` → spawns `_server` subprocess → subprocess
   binds TCP port, writes session JSON → CLI reads port, connects, returns
   status.
2. **Commands:** CLI reconnects per command (stateless client) → sends JSON
   command → receives JSON response → prints to stdout.
3. **Teardown:** CLI sends `quit` command → server sets `should_quit` → server
   cleanup → session JSON deleted.  If server crashes, `_is_process_alive`
   returns False and the stale session is removed on next access.

### IPC protocol

- Length-prefixed JSON: 4-byte big-endian length followed by UTF-8 JSON body.
- Server accepts one client connection at a time.
- Client reconnects for each command (no persistent connection required).

### Supported platforms (post-refactor)

| Platform | Status |
|---|---|
| Linux (ubuntu-latest) | ✅ Fully supported |
| macOS (macos-latest) | ✅ Fully supported |
| Windows (windows-latest) | ✅ Fully supported |

### Known limitations on Windows

- Attach-mode debugging (if implemented in a future PR) may differ due to
  Windows security model for cross-process debugging.
- `SIGTERM` cannot be delivered externally; only `SIGINT` (Ctrl+C) is
  intercepted.
