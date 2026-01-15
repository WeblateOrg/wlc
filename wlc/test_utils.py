# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utils tests."""

from unittest import TestCase

from .utils import sanitize_slug


class UtilsTestCase(TestCase):
    """Utils tests."""

    def test_sanitize_slug(self):
        self.assertEqual(sanitize_slug("slug"), "slug")

    def test_sanitize_slug_dangerous(self):
        self.assertEqual(sanitize_slug("../\\slug"), "----slug")
        self.assertEqual(sanitize_slug("slug/other"), "slug-other")
        self.assertEqual(sanitize_slug("slug/"), "slug-")
