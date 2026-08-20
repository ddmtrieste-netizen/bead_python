"""Formatted terminal messages used by beadtrack commands."""

import sys
from typing import Final, TextIO

__all__ = ["arduino_prompt", "bold", "error", "info", "result", "success", "warning"]

RESET: Final[str] = "\033[0m"
BLUE: Final[str] = "\033[34m"
GREEN: Final[str] = "\033[32m"
PURPLE: Final[str] = "\033[35m"
YELLOW: Final[str] = "\033[33m"
RED: Final[str] = "\033[31m"
BOLD: Final[str] = "\033[1m"


def _emit(
    level: str,
    text: object,
    *,
    color: str = "",
    stream: TextIO | None = None,
    end: str = "\n",
) -> None:
    """Write one tagged message to a terminal stream."""
    if stream is None:
        stream = sys.stderr if level in {"WARNING", "ERROR"} else sys.stdout

    print(f"{color}[{level}]{RESET} {text}", file=stream, flush=True, end=end)


def bold(text: object) -> str:
    """Return text formatted as bold with ANSI escape codes."""
    return f"{BOLD}{text}{RESET}"


def arduino_prompt(text: object = "Insert command > ") -> None:
    """Print an Arduino command prompt without a trailing newline."""
    _emit("ARDUINO", text, color=PURPLE, end="")


def info(text: object, *, end: str = "\n") -> None:
    """Print an informational message."""
    _emit("INFO", text, color=BLUE, end=end)


def success(text: object) -> None:
    """Print a successful-operation message."""
    _emit("OK", text, color=GREEN)


def result(text: object) -> None:
    """Print a computation result."""
    _emit("RESULT", text, color=PURPLE)


def warning(text: object) -> None:
    """Print a warning to standard error."""
    _emit("WARNING", text, color=YELLOW)


def error(text: object) -> None:
    """Print an error to standard error."""
    _emit("ERROR", text, color=RED)
