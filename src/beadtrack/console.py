"""Stable, platform-neutral terminal messages for supported commands."""

import sys


def message(level, text, *, stream=None):
    """Print one tagged message."""
    if stream is None:
        stream = sys.stderr if level in {"WARN", "ERROR"} else sys.stdout
    print(f"[{level}] {text}", file=stream, flush=True)


def info(text):
    message("INFO", text)


def ok(text):
    message("OK", text)


def result(text):
    message("RESULT", text)


def warn(text):
    message("WARN", text)


def error(text):
    message("ERROR", text)
