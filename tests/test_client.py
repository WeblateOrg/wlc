# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test HTTP client requests and resource creation."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import urlencode

import responses
from requests import Response
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

from wlc import (
    API_URL,
    Weblate,
    WeblateException,
)

from .test_base import APITest

if TYPE_CHECKING:
    from wlc.client import JSONValue


class WeblateTest(APITest):
    """Test Weblate requests and resource listing."""

    def test_low_level_json_values(self) -> None:
        """Low-level request methods should preserve every JSON value shape."""
        values: tuple[JSONValue, ...] = (
            None,
            True,
            42,
            1.5,
            "value",
            [None, False, 42, 1.5, "value"],
            {"nested": [None, {"value": True}]},
        )
        weblate = Weblate()
        for index, value in enumerate(values):
            path = f"json/{index}/"
            responses.add(
                responses.GET,
                f"http://127.0.0.1:8000/api/{path}",
                body=json.dumps(value),
                content_type="application/json",
            )
            for method in ("request", "get"):
                with self.subTest(value=value, method=method):
                    result = (
                        weblate.request("get", path)
                        if method == "request"
                        else weblate.get(path)
                    )
                    self.assertEqual(result, value)
                    self.assertIs(type(result), type(value))

    def test_adapter_uses_configured_retries(self) -> None:
        """HTTP adapter should use the resolved Retry configuration."""
        weblate = Weblate(retries=3, backoff_factor=0.5, allowed_methods=["GET"])
        self.assertEqual(weblate.retry_total, 3)
        self.assertIsInstance(weblate.adapter.max_retries, Retry)
        self.assertEqual(weblate.adapter.max_retries.total, 3)
        self.assertEqual(weblate.adapter.max_retries.backoff_factor, 0.5)
        allowed_methods = weblate.adapter.max_retries.allowed_methods
        self.assertIsNotNone(allowed_methods)
        self.assertEqual(
            frozenset(allowed_methods or ()),
            frozenset({"GET"}),
        )

    def test_adapter_is_mounted_for_both_schemes(self) -> None:
        """The configured adapter should be mounted during initialization."""
        weblate = Weblate()

        self.assertIs(weblate.session.get_adapter("http://"), weblate.adapter)
        self.assertIs(weblate.session.get_adapter("https://"), weblate.adapter)

    def test_languages(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_languages())), 47)

    def test_api_trailing_slash(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate(url=API_URL[:-1]).list_languages())), 47)

    def test_projects(self) -> None:
        """Test listing projects."""
        self.assertEqual(len(list(Weblate().list_projects())), 2)

    def test_components(self) -> None:
        """Test listing components."""
        self.assertEqual(len(list(Weblate().list_components())), 2)

    def test_translations(self) -> None:
        """Test listing translations."""
        self.assertEqual(len(list(Weblate().list_translations())), 50)

    def test_categories(self) -> None:
        """Test listing categories."""
        self.assertEqual(len(list(Weblate().list_categories())), 2)

    def test_request_environment_settings_are_preserved(self) -> None:
        """Proxy and CA bundle environment settings should remain enabled."""
        with TemporaryDirectory() as tmpdirname:
            ca_bundle = Path(tmpdirname) / "ca-bundle.pem"
            ca_bundle.touch()
            with patch.dict(
                os.environ,
                {
                    "HTTPS_PROXY": "http://proxy.example.com:8080",
                    "REQUESTS_CA_BUNDLE": str(ca_bundle),
                },
                clear=True,
            ):
                settings = Weblate().session.merge_environment_settings(
                    "https://example.com/api/",
                    proxies={},
                    stream=False,
                    verify=True,
                    cert=None,
                )

        self.assertEqual(settings["proxies"]["https"], "http://proxy.example.com:8080")
        self.assertEqual(settings["verify"], str(ca_bundle))

    def test_insecure_warning_is_not_suppressed(self) -> None:
        response = Response()
        response.status_code = 200
        weblate = Weblate(url="https://localhost/api/", allow_insecure_ssl=True)

        def request(*_args: object, **_kwargs: object) -> Response:
            warnings.warn("insecure", InsecureRequestWarning, stacklevel=2)
            warnings.warn("unrelated", UserWarning, stacklevel=2)
            return response

        with (
            patch.object(weblate.session, "request", side_effect=request),
            warnings.catch_warnings(record=True) as caught,
        ):
            warnings.simplefilter("always")
            weblate.invoke_request("GET", weblate.url)
            warnings.warn("insecure afterward", InsecureRequestWarning, stacklevel=1)

        self.assertEqual(
            [(warning.category, str(warning.message)) for warning in caught],
            [
                (InsecureRequestWarning, "insecure"),
                (UserWarning, "unrelated"),
                (InsecureRequestWarning, "insecure afterward"),
            ],
        )

    def test_paginated_listing_uses_params_only_for_first_request(self) -> None:
        """The API-provided next URL already includes query parameters."""
        query = "language:en AND state:<translated"
        page1 = "http://127.0.0.1:8000/api/filtered-units/"
        page2 = f"{page1}?{urlencode({'page': 2, 'q': query})}"
        pages = (
            ({"q": query}, page2, 1),
            ({"page": "2", "q": query}, None, 2),
        )
        for params, next_url, unit_id in pages:
            responses.add(
                responses.GET,
                page1,
                json={
                    "next": next_url,
                    "results": [
                        {
                            "id": unit_id,
                            "url": f"http://127.0.0.1:8000/api/units/{unit_id}/",
                        }
                    ],
                },
                match=[responses.matchers.query_param_matcher(params)],
            )

        units = list(Weblate().list_units("filtered-units/", params={"q": query}))

        self.assertEqual([1, 2], [unit.id for unit in units])


class WeblateAuthenticationTest(APITest):
    """Test API credentials and netrc isolation."""

    def test_authentication(self) -> None:
        """Test authentication against server."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            Weblate().get_object("acl")
        obj = Weblate(key="KEY").get_object("acl")
        self.assertEqual(obj.name, "ACL")

    def test_api_key_rejects_line_breaks(self) -> None:
        """API keys with line breaks should be rejected without disclosure."""
        for line_break in ("\r", "\n"):
            with self.subTest(line_break=repr(line_break)):
                key = f"invalid-secret{line_break}continuation"
                with self.assertRaises(WeblateException) as raised:
                    Weblate(key=key)

                message = str(raised.exception)
                self.assertIn("must not contain", message)
                self.assertNotIn("invalid-secret", message)
                self.assertNotIn("continuation", message)

    def assert_netrc_authentication_is_ignored(self) -> None:
        """Assert netrc credentials are not added or used over an API token."""
        for key, expected in (("", None), ("KEY", "Token KEY")):
            with self.subTest(key=key):
                Weblate(key=key).get_object("hello")

                self.assertEqual(
                    responses.calls[-1].request.headers.get("Authorization"),
                    expected,
                )

    def test_netrc_environment_authentication_is_ignored(self) -> None:
        """Credentials from the NETRC environment file should be ignored."""
        with TemporaryDirectory() as tmpdirname:
            netrc_path = Path(tmpdirname) / "credentials"
            netrc_path.write_text(
                "machine 127.0.0.1 login NETRC password SECRET\n",  # kingfisher:ignore
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"NETRC": str(netrc_path)}, clear=True):
                self.assert_netrc_authentication_is_ignored()

    def test_user_netrc_authentication_is_ignored(self) -> None:
        """Credentials from the user's default netrc file should be ignored."""
        with TemporaryDirectory() as tmpdirname:
            netrc_path = Path(tmpdirname) / ".netrc"
            netrc_path.write_text(
                "machine 127.0.0.1 login NETRC password SECRET\n",  # kingfisher:ignore
                encoding="utf-8",
            )
            netrc_path.chmod(0o600)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "requests.utils.os.path.expanduser", return_value=str(netrc_path)
                ),
            ):
                self.assert_netrc_authentication_is_ignored()
