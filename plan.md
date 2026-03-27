# CI Fix Plan — `copilot/refactor-cross-platform-support`

## Current Failing Tests (latest CI run)

| Platform | Python | Test | Error |
|---|---|---|---|
| ubuntu-latest | 3.12 | `TestTCPSocketIPC::test_session_file_has_port` | `'port' not found in {'status': 'terminated'}` |
| windows-latest | 3.12 | `TestSessionLifecycle::test_start_then_quit` | `PermissionError: [WinError 32]` on `session_file.unlink()` |
| windows-latest | 3.10 | `TestSessionLifecycle::test_start_then_quit` | Same `PermissionError: [WinError 32]` |
| windows-latest | 3.8 | `TestPlatformAdapter::test_adapter_is_process_alive_self` | Subprocess hangs → `KeyboardInterrupt` |

All failures are in:
```
plugins/python-debugger/skills/python-debugging/scripts/debugger.py
```

---

## Bug 1 — `update_session` loses all fields on `IOError`/`JSONDecodeError` (Linux)

### Root cause
`update_session()` has an `except (json.JSONDecodeError, IOError)` branch that writes **only** the `**updates` kwarg dict to disk, discarding all previously-stored fields (pid, script, port, etc.).

On CI the parent `cmd_start` process polls the session file at the same moment the child server process is writing to it. This occasional write-collision corrupts the JSON, causing a `JSONDecodeError` on the next write (`update_session(status="terminated")`), which then overwrites the file with only `{'status': 'terminated'}` — stripping the `port` key that the test asserts must be present.

### Location
`debugger.py` lines 200–212, `SessionManager.update_session`:

```python
except (json.JSONDecodeError, IOError):
    # File might be empty or corrupted, create new
    with open(self.session_file, "w") as f:
        json.dump(updates, f, indent=2)   # ← drops port, pid, script …
```

### Fix
When the read fails, fall back to **merging the update into the already-known instance fields** so that `port`, `pid`, and `script` are never silently dropped:

```python
except (json.JSONDecodeError, IOError):
    # Read failed – reconstruct from known instance state so we never
    # silently drop fields like 'port' that were set before this call.
    fallback = {
        "script": self.script_path,
        "pid":    0,          # unknown if read failed; caller may not set it
        "port":   self.port,  # always carry the port through
    }
    fallback.update(updates)
    with open(self.session_file, "w") as f:
        json.dump(fallback, f, indent=2)
```

---

## Bug 2 — `delete_session()` raises `PermissionError` on Windows (Windows 3.10 / 3.12)

### Root cause
`cmd_quit` (line 1388) calls `session.delete_session()` immediately after sending the `quit` command to the server process. On Windows, the server subprocess still has the session file open at this moment (it holds it open through `update_session(status="terminated")`), so `Path.unlink()` raises `PermissionError: [WinError 32]`.

### Location
`debugger.py` lines 224–227, `SessionManager.delete_session`:

```python
def delete_session(self) -> None:
    if self.session_file.exists():
        self.session_file.unlink()   # ← crashes on Windows if file is locked
```

### Fix
Wrap `unlink()` in a retry loop with a short back-off so Windows has time to release the file handle after the server exits:

```python
def delete_session(self) -> None:
    if not self.session_file.exists():
        return
    deadline = time.time() + 3.0   # wait up to 3 s for Windows to release the lock
    while True:
        try:
            self.session_file.unlink()
            return
        except PermissionError:
            if time.time() >= deadline:
                return   # give up silently; the OS will clean it up eventually
            time.sleep(0.1)
        except FileNotFoundError:
            return   # already gone – that's fine
```

---

## Bug 3 — Subprocess hangs in `test_adapter_is_process_alive_self` on Windows 3.8

### Root cause
`test_adapter_is_process_alive_self` spawns a subprocess (`subprocess.run(...)`) that imports `platform.factory` and calls `os.kill(os.getpid(), 0)`.

On Windows Python 3.8, `os.kill(pid, 0)` with signal `0` sends an actual signal rather than just checking process liveness. Some combinations of Windows + Python 3.8 cause the subprocess to block waiting for the calling process, producing a `KeyboardInterrupt` timeout in pytest.

### Location
`debugger.py` lines 272–280, `SessionManager._is_process_alive`:

```python
@staticmethod
def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)     # ← problematic on Windows Python 3.8
        return True
    except (OSError, PermissionError, ProcessLookupError):
        return False
```

### Fix
Use the platform adapter's `is_process_alive()` method inside the `_is_process_alive` helper (which already uses `ctypes.OpenProcess` on Windows, the correct way), or add an explicit Windows branch:

```python
@staticmethod
def _is_process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) is unreliable on Windows; use the platform adapter
        return _get_platform_adapter().is_process_alive(pid)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError, ProcessLookupError):
        return False
```

---

## Checklist

- [ ] Fix `update_session()` except branch to preserve `port`/`pid`/`script` (Bug 1)
- [ ] Fix `delete_session()` to retry on `PermissionError` with timeout (Bug 2)
- [ ] Fix `_is_process_alive()` to use the Windows platform adapter on `win32` (Bug 3)
- [ ] Run local tests: `pip install pytest && python -m pytest tests/test_smoke.py -v`
- [ ] Push changes and verify CI passes on all four matrix cells

## Files to change

```
plugins/python-debugger/skills/python-debugging/scripts/debugger.py
```
