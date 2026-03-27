"""
POSIX (Linux / macOS) platform adapter.
"""

import os
import signal
from typing import Any, Dict

from .base import PlatformAdapter


class PosixAdapter(PlatformAdapter):
    """Platform adapter for POSIX systems (Linux and macOS)."""

    def is_process_alive(self, pid: int) -> bool:
        """Return True if *pid* is a running process."""
        if not pid:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def terminate_process(self, pid: int) -> None:
        """Send SIGTERM to *pid*, ignoring errors if the process is gone."""
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

    def kill_process(self, pid: int) -> None:
        """Send SIGKILL to *pid*, ignoring errors if the process is gone."""
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

    def get_subprocess_kwargs(self) -> Dict[str, Any]:
        """Return POSIX-specific Popen kwargs.

        ``start_new_session=True`` detaches the child from the parent's
        process group so that Ctrl+C in the CLI does not kill the server.
        """
        return {"start_new_session": True}
