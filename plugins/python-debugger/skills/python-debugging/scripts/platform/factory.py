"""
Factory that returns the correct platform adapter for the current OS.
"""

import sys

from .base import PlatformAdapter


def get_adapter() -> PlatformAdapter:
    """Return the platform adapter appropriate for the current OS.

    Returns a :class:`~platform.windows.WindowsAdapter` on Windows and a
    :class:`~platform.posix.PosixAdapter` on all other platforms (Linux,
    macOS).
    """
    if sys.platform == "win32":
        from .windows import WindowsAdapter
        return WindowsAdapter()
    else:
        from .posix import PosixAdapter
        return PosixAdapter()
