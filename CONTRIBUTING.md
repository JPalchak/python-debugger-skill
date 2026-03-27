# Contributing

Thank you for contributing to the Python Debugger skill!

## Prerequisites

- Python 3.8 or later
- Git

No external runtime dependencies are required; the debugger uses only the
Python standard library.

## Running Tests

### All platforms (Windows, macOS, Linux)

```bash
# From the repository root
python -m pytest tests/ -v
```

### Single file

```bash
python -m pytest tests/test_smoke.py -v
```

### Without pytest (stdlib only)

```bash
python -m unittest discover tests
```

## Multi-OS Testing

The CI matrix runs on `ubuntu-latest`, `macos-latest`, and `windows-latest`
with Python 3.8, 3.10, and 3.12.

To replicate locally:

```bash
# Test on the current platform
python -m pytest tests/ -v

# Verify syntax only (fast cross-check)
python -m py_compile plugins/python-debugger/skills/python-debugging/scripts/debugger.py
```

## Windows Notes

- Use `python` (not `python3`) in commands on Windows.
- The debugger uses TCP loopback sockets (`127.0.0.1`) for IPC.  If a local
  firewall blocks loopback connections, the session will fail to start.
- `SIGTERM` is not sent on Windows; the server responds to `SIGINT` (Ctrl+C)
  and the `quit` command.

## Code Style

- Follow existing code style (no external formatter enforced yet).
- Keep all new OS-specific logic inside `scripts/platform/posix.py` or
  `scripts/platform/windows.py`.
- Core `debugger.py` must not contain raw `signal.SIGTERM`, `os.fork()`,
  `socket.AF_UNIX`, or `signal.alarm()` calls.

## Submitting Changes

1. Fork the repository.
2. Create a feature branch (`git checkout -b my-feature`).
3. Make changes and add tests.
4. Run the full test suite (`python -m pytest tests/ -v`).
5. Open a pull request.
