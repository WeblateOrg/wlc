# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the module."""

from __future__ import annotations

import os
from unittest.mock import patch

import responses
from requests.exceptions import InvalidHeader, RequestException

from wlc import (
    API_URL,
    Weblate,
    WeblateException,
)
from wlc.exceptions import WeblateThrottlingError

from .test_base import APITest, CLITestBase, register_error


class CLIErrorTest(CLITestBase):
    """Testing CLI error handling."""

    API_KEY = "reflected-api-key"

    def assert_api_key_redacted(self, args: list[str], expected_message: str) -> None:
        """Verify that a CLI error does not disclose the configured API key."""
        output = self.execute(["--key", self.API_KEY, *args], expected=1)

        self.assertIn(expected_message, output)
        self.assertIn("<redacted>", output)
        self.assertNotIn(self.API_KEY, output)

    def test_rejects_api_keys_with_line_breaks(self) -> None:
        """CLI and environment keys with line breaks should not be disclosed."""
        for source in ("environment", "command-line"):
            for line_break in ("\r", "\n"):
                for debug in (False, True):
                    with self.subTest(
                        source=source,
                        line_break=repr(line_break),
                        debug=debug,
                    ):
                        key = f"invalid-secret{line_break}continuation"
                        args = ["--debug"] if debug else []
                        environment = {}
                        if source == "environment":
                            environment = {"WLC_KEY": key}
                        else:
                            args.extend(["--key", key])
                        args.append("list-projects")

                        with patch.dict(os.environ, environment, clear=True):
                            output = self.execute(args, expected=1)

                        self.assertIn("must not contain", output)
                        self.assertNotIn("invalid-secret", output)
                        self.assertNotIn("continuation", output)

    def test_request_error_redacts_authorization(self) -> None:
        """Request errors should not disclose configured API tokens."""
        key = "request-error-secret"
        with patch(
            "wlc.main.ListProjects.run",
            side_effect=RequestException(f"Invalid Authorization: 'Token {key}'"),
        ):
            output = self.execute(
                ["--key", key, "list-projects"],
                expected=10,
            )

        self.assertIn("Request failed: Invalid Authorization: <redacted>", output)
        self.assertNotIn(key, output)

    def test_permission_error_redacts_reflected_api_key(self) -> None:
        """Permission error details should mask a reflected API key."""
        register_error(
            "projects/reflected-permission",
            403,
            json={"detail": f"Authentication failed for {self.API_KEY}"},
        )

        self.assert_api_key_redacted(
            ["show", "reflected-permission"], "Authentication failed"
        )

    def test_server_error_redacts_reflected_api_key(self) -> None:
        """Generic HTTP response bodies should mask a reflected API key."""
        register_error(
            "projects/reflected-server-error",
            500,
            json={"detail": f"token={self.API_KEY}"},
        )

        self.assert_api_key_redacted(
            ["show", "reflected-server-error"], "HTTP error 500"
        )

    def test_throttling_error_redacts_reflected_api_key(self) -> None:
        """Throttling response headers should mask a reflected API key."""
        register_error(
            "projects/reflected-throttling",
            429,
            headers={
                "X-RateLimit-Limit": f"{self.API_KEY}-via-header",
                "Retry-After": "60",
            },
        )

        self.assert_api_key_redacted(
            ["show", "reflected-throttling"], "Throttling on the server"
        )

    def test_command_error_redacts_reflected_api_key(self) -> None:
        """Unsuccessful command details should mask a reflected API key."""
        project_url = "http://127.0.0.1:8000/api/projects/reflected-command/"
        repository_url = f"{project_url}repository/"
        register_error(
            "projects/reflected-command",
            200,
            json={
                "url": project_url,
                "web_url": "http://127.0.0.1:8000/projects/reflected-command/",
                "name": "Reflected command",
                "slug": "reflected-command",
                "web": "",
                "repository_url": repository_url,
            },
        )
        register_error(
            "projects/reflected-command/repository",
            200,
            method=responses.POST,
            json={
                "result": False,
                "detail": f"Retry with token {self.API_KEY}",
            },
        )

        self.assert_api_key_redacted(
            ["commit", "reflected-command"], "Failed to commit changes"
        )


class WeblateErrorTest(APITest):
    """Testing error handling."""

    def test_nonexisting(self) -> None:
        """Test error handling for non-existing objects."""
        with self.assertRaisesRegex(WeblateException, "not found"):
            Weblate().get_object("nonexisting")

    def test_denied(self) -> None:
        """Test permission denied error handling."""
        with self.assertRaisesRegex(WeblateException, "permission"):
            Weblate().get_object("denied")

    def test_denied_json(self) -> None:
        """Test permission denied when posting components."""
        with self.assertRaisesRegex(WeblateException, "Can not create"):
            Weblate().create_component(
                project="denied_json",
                slug="component1",
                name="component1",
                file_format="po",
                filemask="/something",
                repo="a_repo",
            )

    def test_denied_json_510(self) -> None:
        """Test permission denied when posting components."""
        with self.assertRaisesRegex(WeblateException, "This is a required error"):
            Weblate().create_component(
                project="denied_json_510",
                slug="component1",
                name="component1",
                file_format="po",
                filemask="/something",
                repo="a_repo",
            )

    def test_throttled(self) -> None:
        """Test handling of throttling error when listing projects."""
        with self.assertRaisesRegex(
            WeblateThrottlingError,
            "Throttling.*Limit is 100 requests. Retry after 81818 seconds.",
        ) as error:
            Weblate().get_object("throttled")
        self.assertEqual(error.exception.limit, "100")
        self.assertEqual(error.exception.retry_after, "81818")

    def test_error(self) -> None:
        """Test general server error (HTTP 500) handling."""
        with self.assertRaisesRegex(WeblateException, "500"):
            Weblate().get_object("error")

    def test_oserror(self) -> None:
        """Test handling of OS/request-level errors when listing projects."""
        with self.assertRaises(RequestException):
            Weblate().get_object("io")

    def test_debug_failure_redacts_invalid_authorization(self) -> None:
        """Invalid authorization headers should not leak into debug logs."""
        key = "debug-secret"
        error = InvalidHeader(
            f"Invalid leading whitespace in header value: {f'Token {key}'!r}"
        )
        weblate = Weblate(key=key)
        with (
            self.assertLogs("wlc", level="DEBUG") as captured,
            self.assertRaises(InvalidHeader),
            patch.object(weblate.session, "request", side_effect=error),
        ):
            weblate.invoke_request("GET", API_URL)

        output = "\n".join(captured.output)
        self.assertIn("HTTP failure", output)
        self.assertIn("<redacted>", output)
        self.assertIn("Invalid leading whitespace", output)
        self.assertNotIn("debug-secret", output)

    def test_bug(self) -> None:
        """Test handling of an unexpected error when listing projects."""
        with self.assertRaises(RuntimeError):
            Weblate().get_object("bug")

    def test_invalid(self) -> None:
        """Test handling of invalid JSON responses."""
        with self.assertRaisesRegex(WeblateException, "invalid JSON"):
            Weblate().get_object("invalid")

    def test_too_long(self) -> None:
        """Unsupported object paths raise a handled error without echoing input."""
        for path in (
            "a/b/c/d",
            "a/b/c/d/e",
            "a/b/c/d\x1b]0;title\x07",
            "a/b/c/d/e\x1b]52;c;cHJlZmVyZW5jZQ==\x07",
            "a/b/c/d\x1b[2J",
        ):
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(WeblateException, r"^Invalid object path\.$"),
            ):
                Weblate().get_object(path)

            self.assertFalse(responses.calls)

    def test_invalid_attribute(self) -> None:
        """Test attributes getting."""
        obj = Weblate().get_object("hello")
        self.assertEqual(obj.name, "Hello")
        with self.assertRaises(AttributeError):
            print(obj.invalid_attribute)  # ruff: ignore[print]
