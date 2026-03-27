"""
Abstract base class for platform adapters.

Each platform adapter must implement the methods defined here.
"""

import abc
from typing import Any, Dict


class PlatformAdapter(abc.ABC):
    """Abstract interface for OS-specific operations."""

    @abc.abstractmethod
    def is_process_alive(self, pid: int) -> bool:
        """Return True if the process with *pid* is still running."""

    @abc.abstractmethod
    def terminate_process(self, pid: int) -> None:
        """Ask the process to terminate gracefully.

        Should not raise if the process no longer exists.
        """

    @abc.abstractmethod
    def kill_process(self, pid: int) -> None:
        """Forcefully kill the process.

        Should not raise if the process no longer exists.
        """

    @abc.abstractmethod
    def get_subprocess_kwargs(self) -> Dict[str, Any]:
        """Return extra keyword arguments for :class:`subprocess.Popen`.

        These are platform-specific flags that ensure clean subprocess
        management (e.g. new process groups, close_fds behaviour).
        """
