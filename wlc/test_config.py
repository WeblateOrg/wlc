# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration parsing tests."""

from pathlib import Path
from unittest import TestCase

from wlc.config import WeblateConfig, WLCConfigurationError

TEST_DATA = Path(__file__).parent / "test_data"
TEST_CONFIG = TEST_DATA / "wlc"


class WeblateConfigTestCase(TestCase):
    """Weblate Client configuration parsing tests."""

    def test_valid(self) -> None:
        """Valid configuration parsing."""
        config = WeblateConfig()
        config.load(TEST_CONFIG)

    def test_deprecated_raises_error(self) -> None:
        """Deprecated configuration parsing raises error."""
        config = WeblateConfig(section="withkey")
        with self.assertRaises(WLCConfigurationError):
            config.load(TEST_CONFIG)
