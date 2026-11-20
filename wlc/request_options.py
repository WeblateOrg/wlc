# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared validation of HTTP request options."""

from __future__ import annotations

from http import HTTPStatus
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

REQUEST_OPTION_ERRORS = {
    "retries": "retries must be a nonnegative integer.",
    "timeout": "timeout must be finite and greater than zero.",
    "backoff_factor": "backoff_factor must be finite and nonnegative.",
    "status_forcelist": "status_forcelist must contain integer HTTP status codes from 400 to 599.",
}
MAX_HTTP_ERROR_STATUS = 599


def validate_task_timeout(value: int) -> int:
    """Validate a whole number of seconds, with zero indicating an unlimited wait."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        msg = "task_timeout must be a nonnegative integer."
        raise ValueError(msg)
    return value


def validate_request_options(
    retries: int,
    status_forcelist: Collection[int] | None,
    backoff_factor: float,
    timeout: int,
) -> None:
    """Reject invalid retry and timeout values without disclosing their contents."""
    if not isinstance(retries, int) or retries < 0:
        raise ValueError(REQUEST_OPTION_ERRORS["retries"])
    try:
        valid_timeout = isfinite(timeout) and timeout > 0
    except (TypeError, OverflowError):
        valid_timeout = False
    if not valid_timeout:
        raise ValueError(REQUEST_OPTION_ERRORS["timeout"])
    try:
        valid_backoff_factor = isfinite(backoff_factor) and backoff_factor >= 0
    except (TypeError, OverflowError):
        valid_backoff_factor = False
    if not valid_backoff_factor:
        raise ValueError(REQUEST_OPTION_ERRORS["backoff_factor"])
    if status_forcelist is not None and any(
        not isinstance(status, int)
        or not HTTPStatus.BAD_REQUEST <= status <= MAX_HTTP_ERROR_STATUS
        for status in status_forcelist
    ):
        raise ValueError(REQUEST_OPTION_ERRORS["status_forcelist"])
