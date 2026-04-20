# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Output helpers for the command-line interface."""

from __future__ import annotations

import json
from datetime import datetime

CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")
CSV_DANGEROUS_LEADING = " \t\r\n"
TERMINAL_CONTROL_REPLACEMENTS = {
    "\a": r"\a",
    "\b": r"\b",
    "\t": r"\t",
    "\n": r"\n",
    "\v": r"\v",
    "\f": r"\f",
    "\r": r"\r",
}


def sorted_items(value):
    """Sorted items iterator."""
    for key in sorted(value.keys()):
        yield key, value[key]


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder with datetime support."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return super().default(o)


def stream_isatty(stream) -> bool:
    """Check whether the given stream is an interactive terminal."""
    isatty = getattr(stream, "isatty", None)
    if callable(isatty):
        return isatty()
    return False


def escape_terminal_text(value: str) -> str:
    """Render terminal control characters visibly instead of executing them."""
    escaped: list[str] = []
    for char in value:
        if char in TERMINAL_CONTROL_REPLACEMENTS:
            escaped.append(TERMINAL_CONTROL_REPLACEMENTS[char])
            continue

        code = ord(char)
        if code == 0x7F or 0x00 <= code < 0x20 or 0x80 <= code < 0xA0:
            escaped.append(f"\\x{code:02x}")
            continue

        escaped.append(char)
    return "".join(escaped)


def format_for_stream(value, stream):
    """Format output for a stream, escaping control characters on terminals."""
    if isinstance(value, str) and stream_isatty(stream):
        return escape_terminal_text(value)
    return value
