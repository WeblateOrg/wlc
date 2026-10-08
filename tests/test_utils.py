# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utils tests."""

from unittest import TestCase

from wlc.utils import sanitize_slug


class UtilsTestCase(TestCase):
    """Utils tests."""

    def test_sanitize_slug(self) -> None:
        self.assertEqual(sanitize_slug("slug"), "slug")

    def test_sanitize_slug_dangerous(self) -> None:
        self.assertEqual(sanitize_slug("../\\slug"), "----slug")
        self.assertEqual(sanitize_slug("slug/other"), "slug-other")
        self.assertEqual(sanitize_slug("slug/"), "slug-")

    def test_sanitize_slug_empty(self) -> None:
        self.assertEqual(sanitize_slug(""), "")

    def test_sanitize_slug_only_invalid(self) -> None:
        self.assertEqual(sanitize_slug("../\\"), "----")

    def test_sanitize_slug_very_long(self) -> None:
        long_slug = "a" * 300 + "/b\\c"
        expected = "a" * 300 + "-b-c"
        self.assertEqual(sanitize_slug(long_slug), expected)
