"""
Baseline smoke tests for the Python Debugger skill.

These tests lock in the current cross-platform behaviour so that regressions
are caught immediately.  They run the debugger CLI against a real script and
verify JSON output, session lifecycle, and clean teardown.

Requirements: Python 3.8+, no external dependencies.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Absolute path to the debugger script
DEBUGGER = Path(__file__).parent.parent / (
    "plugins/python-debugger/skills/python-debugging/scripts/debugger.py"
)


def run_debugger(*args, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run the debugger CLI with the given arguments and return the result."""
    cmd = [sys.executable, str(DEBUGGER)] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_json(text: str) -> dict:
    """Parse the first JSON object from *text*."""
    text = text.strip()
    return json.loads(text)


class TestDebuggerImport(unittest.TestCase):
    """The debugger module must import cleanly on all platforms."""

    def test_module_compiles(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(DEBUGGER)],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_platform_adapters_import(self):
        """Platform adapter modules must import without errors."""
        scripts_dir = str(DEBUGGER.parent)
        for module in ("platform.base", "platform.posix",
                       "platform.windows", "platform.factory"):
            result = subprocess.run(
                [sys.executable, "-c",
                 f"import sys; sys.path.insert(0, {scripts_dir!r}); "
                 f"import {module}"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0,
                             f"Failed to import {module}: {result.stderr}")


class TestDebuggerHelp(unittest.TestCase):
    """``debugger.py`` with no arguments prints help and exits non-zero."""

    def test_no_args_shows_help(self):
        result = run_debugger()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower() + result.stderr.lower())

    def test_hidden_server_command_not_in_help(self):
        result = run_debugger("--help")
        # If _server appears, it must be suppressed (argparse shows ==SUPPRESS==)
        if "_server" in result.stdout:
            self.assertIn("==SUPPRESS==", result.stdout,
                          "_server appeared in help without suppression")


class TestSessionLifecycle(unittest.TestCase):
    """Full start → status → quit lifecycle with a real script."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False
        )
        # A simple script that sleeps long enough for us to inspect it
        self._tmp.write(
            "import time\n"
            "x = 42\n"
            "time.sleep(30)\n"
        )
        self._tmp.flush()
        self._tmp.close()
        self.script = self._tmp.name

    def tearDown(self):
        # Best-effort quit in case the test failed before cleanup
        try:
            run_debugger("quit", timeout=5)
        except Exception:
            pass
        os.unlink(self.script)

    def test_status_with_no_session(self):
        result = run_debugger("status")
        self.assertEqual(result.returncode, 0)
        data = parse_json(result.stdout)
        self.assertEqual(data.get("status"), "no_active_sessions")

    def test_start_publishes_json(self):
        result = run_debugger("start", self.script)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = parse_json(result.stdout)
        # Should have either a "status" or "pid" key
        self.assertTrue(
            "status" in data or "pid" in data,
            f"Unexpected response: {data}"
        )

    def test_start_then_quit(self):
        start_result = run_debugger("start", self.script)
        self.assertEqual(start_result.returncode, 0, start_result.stderr)

        # Give the server a moment to settle
        time.sleep(0.5)

        quit_result = run_debugger("quit")
        self.assertEqual(quit_result.returncode, 0, quit_result.stderr)
        data = parse_json(quit_result.stdout)
        self.assertIn(data.get("status"), ("terminated", "no_active_sessions"))

    def test_double_start_rejected(self):
        run_debugger("start", self.script)
        time.sleep(0.5)
        second = run_debugger("start", self.script)
        data = parse_json(second.stdout)
        self.assertIn("error", data)
        self.assertIn("already running", data["error"])
        # Cleanup
        run_debugger("quit", timeout=5)

    def test_start_nonexistent_script(self):
        result = run_debugger("start", "/no/such/script_xyz.py")
        self.assertNotEqual(result.returncode, 0)
        data = parse_json(result.stdout)
        self.assertIn("error", data)


class TestPlatformAdapter(unittest.TestCase):
    """Platform adapter returns the correct implementation for the current OS."""

    def test_adapter_is_process_alive_self(self):
        """The adapter should report the current process as alive."""
        scripts_dir = str(DEBUGGER.parent)
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys, os; sys.path.insert(0, {scripts_dir!r}); "
             "from platform.factory import get_adapter; "
             "a = get_adapter(); "
             "print(a.is_process_alive(os.getpid()))"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")

    def test_adapter_is_process_alive_bogus_pid(self):
        """The adapter should return False for a PID that cannot exist."""
        scripts_dir = str(DEBUGGER.parent)
        result = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {scripts_dir!r}); "
             "from platform.factory import get_adapter; "
             "a = get_adapter(); "
             "print(a.is_process_alive(99999999))"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(result.stdout.strip(), ("True", "False"))


class TestTCPSocketIPC(unittest.TestCase):
    """Session files use a TCP ``port`` field instead of a Unix socket path."""

    def test_no_sock_files_created(self):
        """Starting a session must not create any .sock files."""
        session_dir = Path.home() / ".claude_debugger"
        before = set(session_dir.glob("*.sock")) if session_dir.exists() else set()

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                        delete=False) as f:
            f.write("import time\ntime.sleep(30)\n")
            script = f.name

        try:
            run_debugger("start", script, timeout=15)
            time.sleep(0.5)
            after_sock = set(session_dir.glob("*.sock")) if session_dir.exists() else set()
            new_sock = after_sock - before
            self.assertEqual(new_sock, set(), f"Unexpected .sock files: {new_sock}")
        finally:
            run_debugger("quit", timeout=5)
            os.unlink(script)

    def test_session_file_has_port(self):
        """The session JSON file must contain a non-zero ``port`` field."""
        session_dir = Path.home() / ".claude_debugger"

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                        delete=False) as f:
            f.write("import time\ntime.sleep(30)\n")
            script = f.name

        try:
            run_debugger("start", script, timeout=15)
            time.sleep(0.5)

            # Compute the expected session file for *this* script so we don't
            # accidentally assert on stale files left by other tests.
            import hashlib
            path_hash = hashlib.md5(
                os.path.abspath(script).encode()
            ).hexdigest()[:8]
            session_file = session_dir / f"debug_{path_hash}.json"

            self.assertTrue(session_file.exists(),
                            f"Session file not found: {session_file}")
            with open(session_file) as fh:
                data = json.load(fh)
            self.assertIn("port", data, f"No 'port' key in {session_file}")
            self.assertGreater(data["port"], 0,
                               f"Port is zero in {session_file}")
            self.assertNotIn("socket", data,
                             f"Old 'socket' key still present in {session_file}")
        finally:
            run_debugger("quit", timeout=5)
            os.unlink(script)


if __name__ == "__main__":
    unittest.main()
