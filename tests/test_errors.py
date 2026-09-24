# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the module."""

from __future__ import annotations

import os
from unittest.mock import patch

from requests.exceptions import InvalidHeader, RequestException

from wlc import (
    API_URL,
    Weblate,
    WeblateException,
)

from .test_base import APITest, CLITestBase


class CLIErrorTest(CLITestBase):
    """Testing CLI error handling."""

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
            WeblateException,
            "Throttling.*Limit is 100 requests. Retry after 81818 seconds.",
        ):
            Weblate().get_object("throttled")

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
        """Test that too-long object paths raise ValueError."""
        with self.assertRaises(ValueError):
            Weblate().get_object("a/b/c/d")

    def test_invalid_attribute(self) -> None:
        """Test attributes getting."""
        obj = Weblate().get_object("hello")
        self.assertEqual(obj.name, "Hello")
        with self.assertRaises(AttributeError):
            print(obj.invalid_attribute)
