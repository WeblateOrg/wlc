# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test helpers."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import sys
from abc import ABC
from collections import UserDict
from email import message_from_string
from email.message import Message
from hashlib import blake2b
from io import BytesIO, StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn, TextIO, cast
from unittest import TestCase

import responses
from requests.exceptions import RequestException

from wlc.main import SettingsSource, main

if TYPE_CHECKING:
    from collections.abc import Callable

    from requests import PreparedRequest

    from wlc.main import BufferedStream

TEST_DATA = Path(__file__).parent / "test_data"
DATA_TEST_BASE = TEST_DATA / "api"
TEST_CONFIG = TEST_DATA / "wlc"
TEST_SECTION = TEST_DATA / "section"


class BufferedStringIO(StringIO):
    """StringIO with a writable binary buffer for CLI tests."""

    def __init__(self, *, tty: bool = False) -> None:
        super().__init__()
        self._buffer = BytesIO()
        self._tty = tty

    @property
    def buffer(self) -> BytesIO:
        """Expose a binary buffer like sys.stdout.buffer."""
        return self._buffer

    def isatty(self) -> bool:
        return self._tty


class TTYStringIO(BufferedStringIO):
    """Buffered StringIO behaving like a terminal."""

    def __init__(self) -> None:
        super().__init__(tty=True)


class AttributeDict(UserDict[str, object]):
    """Dictionary exposing keys as attributes."""

    def __getattr__(self, key: str) -> object:
        """Provide attribute-style access."""
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class ResponseHandler:
    """responses response handler."""

    def __init__(self, body: bytes, filename: Path, *, auth: bool = False) -> None:
        """Construct response handler object."""
        self.body = body
        self.filename = filename
        self.auth = auth

    def __call__(
        self, request: PreparedRequest
    ) -> tuple[int, dict[str, str], bytes | str]:
        """Call interface for responses."""
        if self.auth and request.headers.get("Authorization") != "Token KEY":
            return 403, {}, ""

        content = self.get_content(request)

        return 200, {}, content

    def get_content(self, request: PreparedRequest) -> bytes:
        """Return content for given request."""
        filename = self.get_filename(request)

        if filename is not None:
            try:
                with filename.open("rb") as handle:
                    return handle.read()
            except FileNotFoundError as error:
                error.strerror = "Failed to find response mock"
                raise error  # ruff: ignore[verbose-raise]

        return self.body

    @staticmethod
    def format_body(body: bytes | None) -> str:
        if not body:
            return ""
        decoded = body.decode()
        result = (
            decoded.replace(": ", "=")
            .replace("{", "")
            .replace("}", "")
            .replace('"', "")
            .replace(":", "-")
            .replace("/", "-")
            .replace(", ", "--")
            .replace(" ", "-")
            .replace("[", "-")
            .replace("]", "-")
            .replace("*", "-")
        )
        if len(result) < 100:
            return result
        digest = blake2b(digest_size=4)
        digest.update(result.encode())
        return digest.hexdigest()

    def get_filename(self, request: PreparedRequest) -> Path | None:
        """Return filename for given request."""
        filename_parts = [str(self.filename), cast("str", request.method)]
        if request.method != "GET":
            content_type = request.headers.get("content-type", None)

            if content_type is not None and content_type.startswith(
                "multipart/form-data"
            ):
                filename_parts.append(
                    self.format_multipart_body(
                        cast("bytes", request.body), content_type
                    )
                )
            else:
                filename_parts.append(
                    self.format_body(cast("bytes | None", request.body))
                )
            return Path("--".join(filename_parts))
        if "?" in request.path_url:
            filename_parts.append(request.path_url.split("?", 1)[-1])
            return Path("--".join(filename_parts))
        return None

    @staticmethod
    def format_multipart_body(body: bytes, content_type: str) -> str:
        message = message_from_string(
            f"Content-Type: {content_type}\n\n{body.decode()}"
        )
        payload = []
        for part in message.get_payload():
            if not isinstance(part, Message):
                msg = f"Unexpected test data: {part}"
                raise TypeError(msg)
            name = part.get_param("name", header="content-disposition")
            value = part.get_payload()
            if isinstance(value, bytes):
                value = value.decode()
            payload.append((name, value))
        digest = blake2b(digest_size=4)
        digest.update(repr(sorted(payload)).encode())
        return digest.hexdigest()


def register_uri(
    path: str, *, domain: str = "http://127.0.0.1:8000/api", auth: bool = False
) -> None:
    """Simplified URL registration."""
    filename = DATA_TEST_BASE / path.replace("/", "-")
    url = f"{domain}/{path}/"
    with filename.open("rb") as handle:
        responses.add_callback(
            responses.GET,
            url,
            callback=ResponseHandler(handle.read(), filename, auth=auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.POST,
            url,
            callback=ResponseHandler(handle.read(), filename, auth=auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.DELETE,
            url,
            callback=ResponseHandler(handle.read(), filename, auth=auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.PATCH,
            url,
            callback=ResponseHandler(handle.read(), filename, auth=auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.PUT,
            url,
            callback=ResponseHandler(handle.read(), filename, auth=auth),
            content_type="application/json",
        )


def raise_error(request: PreparedRequest) -> NoReturn:
    """Raise an expected request error or an unexpected programming error."""
    if "/io" in request.path_url:
        msg = "Some error"
        raise RequestException(msg)
    msg = "Bug"
    raise RuntimeError(msg)


# pylint: disable-next=too-many-arguments
def register_error(
    path: str,
    code: int,
    domain: str = "http://127.0.0.1:8000/api",
    method: str = responses.GET,
    *,
    callback: Callable[[PreparedRequest], NoReturn] | None = None,
    json: object = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Simplified URL error registration."""
    url = f"{domain}/{path}/"
    if callback is not None:
        responses.add_callback(method, url, callback=callback)
    else:
        responses.add(method, url, status=code, json=json, headers=headers)


def register_uris() -> None:
    """Register URIs for responses."""
    paths = (
        "categories",
        "categories/1",
        "changes",
        "components",
        "components/hello/android",
        "components/hello/android/file",
        "components/hello/olderweblate",
        "components/hello/weblate",
        "components/hello/weblate/file",
        "components/hello/weblate/changes",
        "components/hello/weblate/lock",
        "components/hello/weblate/repository",
        "components/hello/weblate/statistics",
        "components/hello/weblate/translations",
        "languages",
        "projects",
        "projects/empty",
        "projects/empty/components",
        "projects/hello",
        "projects/hello/categories",
        "projects/hello/changes",
        "projects/hello/components",
        "projects/hello/languages",
        "projects/hello/repository",
        "projects/hello/statistics",
        "projects/invalid",
        "translations",
        "translations/hello/weblate/cs",
        "translations/hello/weblate/cs/changes",
        "translations/hello/weblate/cs/file",
        "translations/hello/weblate/cs/repository",
        "translations/hello/weblate/cs/statistics",
        "translations/hello/weblate/cs/units",
        "translations/hello/android/en/units",
        "units",
        "units/123",
    )
    for path in paths:
        register_uri(path)

    register_uri("projects/acl", auth=True)

    register_uri("projects", domain="https://example.net")
    register_error("projects/nonexisting", 404)
    register_error("projects/denied", 403)
    register_error(
        "projects/denied_json/components",
        403,
        method=responses.POST,
        json={"detail": "Can not create components"},
    )
    register_error(
        "projects/denied_json_510/components",
        403,
        method=responses.POST,
        json={
            "type": "validation_error",
            "errors": [
                {
                    "code": "required",
                    "detail": "This is a required error.",
                }
            ],
        },
    )
    register_error(
        "projects/throttled",
        429,
        headers={"X-RateLimit-Limit": "100", "Retry-After": "81818"},
    )
    register_error("projects/error", 500)
    register_error("projects/io", 500, callback=raise_error)
    register_error("projects/bug", 500, callback=raise_error)
    register_error("projects", 401, domain="http://denied.example.com")


class APITest(TestCase, ABC):
    """Base class for API testing."""

    def setUp(self) -> None:
        """Enable responses and register urls."""
        responses.mock.start()
        register_uris()

    def tearDown(self) -> None:
        """Disable responses."""
        responses.mock.stop()
        responses.mock.reset()


class CLITestBase(APITest, ABC):
    """Base class for CLI testing."""

    # pylint: disable-next=too-many-arguments
    def execute(
        self,
        args: list[str] | None,
        *,
        settings: SettingsSource | Literal[False] | None = None,
        stdout: Literal[True] | None = None,
        stdin: BufferedStream | TextIO | None = None,
        expected: int = 0,
        tty: bool = False,
    ) -> bytes | str:
        """Execute command and return output."""
        if settings is None:
            settings = ()
        elif not settings:
            settings = None
        output = TTYStringIO() if tty else BufferedStringIO()
        backup = sys.stdout
        backup_err = sys.stderr
        try:
            sys.stdout = output
            sys.stderr = output
            result = main(
                args=args,
                settings=settings,
                stdout=output if stdout else None,
                stdin=stdin,
            )
            self.assertEqual(result, expected)
        finally:
            sys.stdout = backup
            sys.stderr = backup_err
        result = output.buffer.getvalue()
        if result:
            return result
        return output.getvalue()
