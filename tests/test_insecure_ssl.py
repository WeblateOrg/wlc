# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI tests for explicit TLS certificate verification policy."""

from __future__ import annotations

import os
from io import BytesIO
from unittest.mock import patch

from requests import Response

from wlc import Weblate

from .test_main import CLITestBase


class TestInsecureSSLCLI(CLITestBase):
    """Test CLI handling of TLS certificate verification."""

    @staticmethod
    def get_response() -> Response:
        """Return a successful empty API listing response."""
        response = Response()
        response.status_code = 200
        response.raw = BytesIO(b"[]")
        return response

    def test_ssl_verification_is_explicit(self) -> None:
        """TLS verification is enabled unless explicitly disabled."""
        response = Response()
        response.status_code = 200

        for allow_insecure_ssl, expected_verify in ((False, True), (True, False)):
            with self.subTest(allow_insecure_ssl=allow_insecure_ssl):
                weblate = Weblate(
                    url="https://localhost/api/",
                    allow_insecure_ssl=allow_insecure_ssl,
                )
                with patch.object(
                    weblate.session, "request", return_value=response
                ) as request:
                    weblate.invoke_request("GET", weblate.url)

                self.assertIs(request.call_args.kwargs["verify"], expected_verify)

    def test_tls_verification_defaults_to_enabled(self) -> None:
        """Loopback HTTPS should no longer disable verification automatically."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "wlc.client.requests.Session.request",
                return_value=self.get_response(),
            ) as request,
        ):
            output = self.execute(["--url", "https://localhost/api/", "list-projects"])

        self.assertEqual(output, "")
        self.assertIs(request.call_args.kwargs["verify"], True)

    def test_cli_can_explicitly_disable_tls_verification(self) -> None:
        """The command-line opt-in should disable verification for this run."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "wlc.client.requests.Session.request",
                return_value=self.get_response(),
            ) as request,
        ):
            output = self.execute(
                [
                    "--allow-insecure-ssl",
                    "--url",
                    "https://example.com/api/",
                    "list-projects",
                ]
            )

        self.assertEqual(output, "")
        self.assertIs(request.call_args.kwargs["verify"], False)

    def test_environment_can_explicitly_disable_tls_verification(self) -> None:
        """The environment opt-in should disable verification for its pinned URL."""
        with (
            patch.dict(
                os.environ,
                {
                    "WLC_URL": "https://example.com/api/",
                    "WLC_ALLOW_INSECURE_SSL": "1",
                },
                clear=True,
            ),
            patch(
                "wlc.client.requests.Session.request",
                return_value=self.get_response(),
            ) as request,
        ):
            output = self.execute(["list-projects"])

        self.assertEqual(output, "")
        self.assertIs(request.call_args.kwargs["verify"], False)
