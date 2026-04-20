# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Helpers for sanitized HTTP debug logging."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from requests import Response

log = logging.getLogger("wlc")

SENSITIVE_HEADERS = {"authorization", "proxy-authorization"}


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive headers before logging."""
    return {
        key: "<redacted>" if key.lower() in SENSITIVE_HEADERS else value
        for key, value in headers.items()
    }


def log_request_debug(
    method: str,
    path: str,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    json_data: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    files: dict[str, str] | None = None,
) -> None:
    """Emit a sanitized debug log for an outgoing HTTP request."""
    if not log.isEnabledFor(logging.DEBUG):
        return

    details: dict[str, Any] = {
        "method": method.upper(),
        "url": path,
        "headers": redact_headers(headers),
    }
    if params is not None:
        details["params"] = params
    if json_data is not None:
        details["json_keys"] = sorted(json_data)
    if data is not None:
        details["data_keys"] = sorted(data)
    if files is not None:
        details["file_fields"] = sorted(files)
    log.debug("HTTP request %s", json.dumps(details, sort_keys=True))


def log_response_debug(response: Response) -> None:
    """Emit a debug log for the received HTTP response."""
    if not log.isEnabledFor(logging.DEBUG):
        return

    log.debug(
        "HTTP response %s %s -> %s %s",
        response.request.method,
        response.url,
        response.status_code,
        response.reason,
    )


def log_failure_debug(method: str, path: str, error: Exception) -> None:
    """Emit a debug log for failed HTTP requests."""
    if not log.isEnabledFor(logging.DEBUG):
        return

    log.debug("HTTP failure %s %s -> %s", method.upper(), path, error)


def enable_debug_logging():
    """Install a temporary debug handler for sanitized HTTP logs."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    previous_level = log.level
    previous_propagate = log.propagate
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return handler, previous_level, previous_propagate


def disable_debug_logging(handler, previous_level, previous_propagate) -> None:
    """Remove the temporary debug handler."""
    log.removeHandler(handler)
    handler.close()
    log.setLevel(previous_level)
    log.propagate = previous_propagate
