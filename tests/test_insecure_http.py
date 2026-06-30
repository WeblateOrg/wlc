# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI tests for insecure HTTP token handling."""

from __future__ import annotations

import os
from unittest.mock import patch

import responses

from .test_main import CLITestBase


class TestInsecureHTTPCLI(CLITestBase):
    """Test CLI handling of API keys over non-local HTTP URLs."""

    def test_cli_key_rejects_non_local_http_url(self) -> None:
        """CLI should reject API keys over non-local HTTP by default."""
        with patch.dict(os.environ, {}, clear=True):
            output = self.execute(
                [
                    "--url",
                    "http://example.com/api/",
                    "--key",
                    "KEY",
                    "list-projects",
                ],
                expected=1,
            )

        self.assertIn("Refusing to use an API key over insecure HTTP", output)

    def test_env_key_rejects_non_local_http_url(self) -> None:
        """Environment config should reject API keys over non-local HTTP."""
        with patch.dict(
            os.environ,
            {
                "WLC_URL": "http://example.com/api/",
                "WLC_KEY": "KEY",
            },
            clear=True,
        ):
            output = self.execute(["list-projects"], expected=1)

        self.assertIn("Refusing to use an API key over insecure HTTP", output)

    def test_cli_allows_non_local_http_url_when_opted_in(self) -> None:
        """CLI flag can explicitly allow API keys over non-local HTTP."""
        responses.add(responses.GET, "http://example.com/api/projects/", json=[])

        with patch.dict(os.environ, {}, clear=True):
            output = self.execute(
                [
                    "--allow-insecure-http",
                    "--url",
                    "http://example.com/api/",
                    "--key",
                    "KEY",
                    "list-projects",
                ]
            )

        self.assertEqual("", output)

    def test_cli_reports_wrong_key_when_insecure_http_is_opted_in(self) -> None:
        """Wrong API keys should still report server rejection after opt-in."""
        output = self.execute(
            [
                "--allow-insecure-http",
                "--key",
                "x",
                "--url",
                "http://denied.example.com",
                "list-projects",
            ],
            expected=1,
        )

        self.assertIn("was rejected by server", output)
