# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Weblate exceptions."""

from __future__ import annotations

from typing import cast


class WeblateException(Exception):
    """Generic error."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__doc__)


class WeblateThrottlingError(WeblateException):
    """Throttling on the server."""

    def __init__(self, limit: str, retry_after: str) -> None:
        self.limit = limit
        self.retry_after = retry_after
        message_segments = [
            cast("str", self.__doc__)
        ]  # workaround for https://github.com/python/mypy/issues/15825
        if limit:
            message_segments.append(f"Limit is {limit} requests.")
        if retry_after:
            message_segments.append(f"Retry after {retry_after} seconds.")
        super().__init__(" ".join(message_segments))


class WeblatePermissionError(WeblateException):
    """You don't have permission to access this object."""


class WeblateDeniedError(WeblateException):
    """Access denied, API key is wrong or missing."""
