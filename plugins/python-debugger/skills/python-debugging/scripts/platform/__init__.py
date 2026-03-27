"""
Platform abstraction layer for the Python Debugger.

Usage::

    from .platform import get_adapter
    adapter = get_adapter()
    alive = adapter.is_process_alive(pid)
"""

from .factory import get_adapter

__all__ = ["get_adapter"]
