# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Interpret responses from operations that Weblate can queue."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from .exceptions import WeblateException

if TYPE_CHECKING:
    from requests import Response

    from .client import JSONDict, JSONValue, Weblate


def response_json(response: Response) -> JSONValue:
    """Decode an API response."""
    try:
        return response.json()
    except ValueError as error:
        msg = "Server returned invalid JSON"
        raise WeblateException(msg) from error


def response_object(response: Response) -> JSONDict:
    """Read an operation response that must contain a JSON object."""
    data = response_json(response)
    if isinstance(data, dict):
        return data
    msg = "Invalid operation response."
    raise WeblateException(msg)


def task_result(client: Weblate, acceptance: JSONDict) -> JSONValue:
    """Follow the task identified in an accepted response."""
    url = acceptance.get("task_url")
    if not isinstance(url, str) or not url.strip():
        msg = "Queued operation has no valid task URL."
        raise WeblateException(msg)
    return client.wait_for_task(url)


def task_error(result: JSONValue) -> WeblateException:
    """Report the failure detail supplied by Weblate when available."""
    detail = result.get("detail") if isinstance(result, dict) else result
    return WeblateException(
        detail if isinstance(detail, str) and detail else "Unexpected task result."
    )


def delete_object(client: Weblate, url: str) -> None:
    """Wait for queued deletion, which returns null on success."""
    response = client.invoke_request("delete", url)
    if response.status_code == HTTPStatus.ACCEPTED:
        result = task_result(client, response_object(response))
        if result is not None:
            raise task_error(result)
