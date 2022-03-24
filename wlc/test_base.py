#
# Copyright © 2012–2022 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate Client <https://github.com/WeblateOrg/wlc>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Test helpers."""
import cgi
import os
from hashlib import blake2b
from io import BytesIO
from unittest import TestCase

import responses
from requests.exceptions import RequestException

DATA_TEST_BASE = os.path.join(os.path.dirname(__file__), "test_data", "api")


class ResponseHandler:
    """responses response handler."""

    def __init__(self, body, filename, auth=False):
        """Construct response handler object."""
        self.body = body
        self.filename = filename
        self.auth = auth

    def __call__(self, request):
        """Call interface for responses."""
        if self.auth and request.headers.get("Authorization") != "Token KEY":
            return 403, {}, ""

        content = self.get_content(request)

        return 200, {}, content

    def get_content(self, request):
        """Return content for given request."""
        filename = self.get_filename(request)

        if filename is not None:
            try:
                with open(filename, "rb") as handle:
                    return handle.read()
            except FileNotFoundError as error:
                error.strerror = "Failed to find response mock"
                raise error

        return self.body

    @staticmethod
    def format_body(body):
        if not body:
            return ""
        body = body.decode()
        body = (
            body.replace(": ", "=")
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
        return body

    def get_filename(self, request):
        """Return filename for given request."""
        filename_parts = [self.filename, request.method]
        if request.method != "GET":
            content_type = request.headers.get("content-type", None)

            if content_type is not None and content_type.startswith(
                "multipart/form-data"
            ):
                filename_parts.append(
                    self.format_multipart_body(request.body, content_type)
                )
            else:
                filename_parts.append(self.format_body(request.body))
            return "--".join(filename_parts)
        if "?" in request.path_url:
            filename_parts.append(request.path_url.split("?", 1)[-1])
            return "--".join(filename_parts)
        return None

    @staticmethod
    def format_multipart_body(body, content_type):
        content_type, pdict = cgi.parse_header(content_type)
        if "boundary" in pdict:
            pdict["boundary"] = pdict["boundary"].encode()
        fileio = BytesIO(body)
        payload = []
        for name, values in cgi.parse_multipart(fileio, pdict).items():
            value = values[0]
            if isinstance(value, bytes):
                value = value.decode()
            payload.append((name, value))
        digest = blake2b(digest_size=4)
        digest.update(repr(sorted(payload)).encode())
        return digest.hexdigest()


def register_uri(path, domain="http://127.0.0.1:8000/api", auth=False):
    """Simplified URL registration."""
    filename = os.path.join(DATA_TEST_BASE, path.replace("/", "-"))
    url = "/".join((domain, path, ""))
    with open(filename, "rb") as handle:
        responses.add_callback(
            responses.GET,
            url,
            callback=ResponseHandler(handle.read(), filename, auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.POST,
            url,
            callback=ResponseHandler(handle.read(), filename, auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.DELETE,
            url,
            callback=ResponseHandler(handle.read(), filename, auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.PATCH,
            url,
            callback=ResponseHandler(handle.read(), filename, auth),
            content_type="application/json",
        )
        responses.add_callback(
            responses.PUT,
            url,
            callback=ResponseHandler(handle.read(), filename, auth),
            content_type="application/json",
        )


def raise_error(request):
    """Raise IOError."""
    if "/io" in request.path_url:
        raise RequestException("Some error")
    raise FileNotFoundError("Bug")


def register_error(
    path, code, domain="http://127.0.0.1:8000/api", method=responses.GET, **kwargs
):
    """Simplified URL error registration."""
    url = "/".join((domain, path, ""))
    if "callback" in kwargs:
        responses.add_callback(method, url, **kwargs)
    else:
        responses.add(method, url, status=code, **kwargs)


def register_uris():
    """Register URIs for responses."""
    paths = (
        "changes",
        "components",
        "components/hello/android",
        "components/hello/android/file",
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
    register_error("projects/throttled", 429)
    register_error("projects/error", 500)
    register_error("projects/io", 500, callback=raise_error)
    register_error("projects/bug", 500, callback=raise_error)
    register_error("projects", 401, domain="http://denied.example.com")


class APITest(TestCase):
    """Base class for API testing."""

    def setUp(self):
        """Enable responses and register urls."""
        responses.mock.start()
        register_uris()

    def tearDown(self):
        """Disable responses."""
        responses.mock.stop()
        responses.mock.reset()
