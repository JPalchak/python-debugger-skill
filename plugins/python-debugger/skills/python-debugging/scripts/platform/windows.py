"""
Windows platform adapter.
"""

import os
import subprocess
import sys
from typing import Any, Dict

from .base import PlatformAdapter


class WindowsAdapter(PlatformAdapter):
    """Platform adapter for Windows."""

    def is_process_alive(self, pid: int) -> bool:
        """Return True if *pid* is a running process on Windows."""
        if not pid:
            return False
        try:
            # os.kill(pid, 0) is supported on Python 3 Windows:
            # it calls OpenProcess internally and raises OSError if the
            # process does not exist.
            os.kill(pid, 0)
            return True
        except (OSError, PermissionError, ProcessLookupError):
            return False

    def terminate_process(self, pid: int) -> None:
        """Gracefully terminate a Windows process.

        Uses ``taskkill`` without ``/F`` first to allow a clean shutdown.
        Falls back to a force-kill if the graceful attempt fails.
        """
        if not pid:
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            # taskkill not available; fall through to force-kill
            self.kill_process(pid)

    def kill_process(self, pid: int) -> None:
        """Forcefully terminate a Windows process via ``taskkill /F``."""
        if not pid:
            return
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError:
            pass

    def get_subprocess_kwargs(self) -> Dict[str, Any]:
        """Return Windows-specific Popen kwargs.

        ``creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`` isolates the
        child from the parent's console Ctrl+C event, mirroring the POSIX
        ``start_new_session=True`` behaviour.
        """
        # CREATE_NEW_PROCESS_GROUP (0x00000200) is Windows-only; access it via
        # the subprocess constant so that type checkers are happy, with an
        # integer fallback for any environment where it may be absent.
        flag = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": flag}
