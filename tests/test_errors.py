# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the module."""

from __future__ import annotations

from requests.exceptions import RequestException

from wlc import (
    Weblate,
    WeblateException,
)

from .test_base import APITest


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

    def test_bug(self) -> None:
        """Test handling of a FileNotFoundError when listing projects."""
        with self.assertRaises(FileNotFoundError):
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
