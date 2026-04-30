"""Suppress benign ConnectionResetError noise from asyncio's Proactor loop on Windows.

On Windows, uvicorn uses the Proactor event loop. When a client forcibly closes a
(TLS) connection, ``_ProactorBasePipeTransport._call_connection_lost`` calls
``socket.shutdown()`` on an already-dead socket, which raises
``ConnectionResetError [WinError 10054]``. The error is harmless but is logged via the
loop's default exception handler and floods the console. This module wraps that method
so only that specific error is swallowed, leaving all other behavior intact.

See https://github.com/python/cpython/issues/83413 (bpo-39010).
"""

import sys


def silence_proactor_connection_reset() -> None:
    """Monkey-patch the Proactor transport to ignore benign connection-reset errors.

    This is a no-op on non-Windows platforms, where the Proactor loop is not used.
    It is also idempotent: applying it more than once has no additional effect.
    """
    if sys.platform != "win32":
        return

    from asyncio.proactor_events import _ProactorBasePipeTransport

    original = _ProactorBasePipeTransport._call_connection_lost

    # Avoid wrapping the method twice if this is called more than once.
    if getattr(original, "_reset_silenced", False):
        return

    def _call_connection_lost(self, exc):
        try:
            original(self, exc)
        except ConnectionResetError:
            # WinError 10054: the peer already reset the connection, so the
            # socket.shutdown() in the original cleanup has nothing to do.
            pass

    _call_connection_lost._reset_silenced = True
    _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost
