"""Serial communication helpers."""

import time
from typing import Protocol

from . import messages

__all__ = ["log_serial_messages"]


class ReadableSerial(Protocol):
    """Minimal serial-port interface required by ``log_serial_messages``."""

    @property
    def is_open(self) -> bool: ...

    @property
    def in_waiting(self) -> int: ...

    def readline(self) -> bytes: ...


def log_serial_messages(
    serial_port: ReadableSerial,
    *,
    poll_interval: float = 0.01,
) -> None:
    """Read serial lines until the port closes or an I/O error occurs."""
    if poll_interval < 0:
        raise ValueError("poll_interval cannot be negative")

    while serial_port.is_open:
        try:
            if serial_port.in_waiting <= 0:
                time.sleep(poll_interval)
                continue

            text = serial_port.readline().decode("utf-8", errors="replace").strip()
            if text:
                messages.info(text)
        except (OSError, UnicodeError) as exc:
            messages.error(exc)
            break
