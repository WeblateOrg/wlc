# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration parsing tests."""

import os
from pathlib import Path
from unittest import TestCase

import wlc
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

    def test_env_key(self) -> None:
        """Environment variable WLC_KEY is used for API key."""
        config = WeblateConfig()
        try:
            os.environ["WLC_KEY"] = "env-api-key"
            url, key = config.get_url_key()
            self.assertEqual(key, "env-api-key")
            self.assertEqual(url, wlc.API_URL)
        finally:
            del os.environ["WLC_KEY"]

    def test_env_url(self) -> None:
        """Environment variable WLC_URL is used for API URL."""
        config = WeblateConfig()
        try:
            os.environ["WLC_URL"] = "https://env.example.com/api/"
            url, key = config.get_url_key()
            self.assertEqual(url, "https://env.example.com/api/")
            self.assertEqual(key, "")
        finally:
            del os.environ["WLC_URL"]

    def test_env_precedence_over_config(self) -> None:
        """Environment variables take precedence over config file values."""
        config = WeblateConfig()
        config.load(TEST_CONFIG)
        try:
            os.environ["WLC_URL"] = "https://env.example.com/api/"
            os.environ["WLC_KEY"] = "env-key"
            url, key = config.get_url_key()
            self.assertEqual(url, "https://env.example.com/api/")
            self.assertEqual(key, "env-key")
        finally:
            del os.environ["WLC_URL"]
            del os.environ["WLC_KEY"]

    def test_cli_precedence_over_env(self) -> None:
        """CLI arguments take precedence over environment variables."""
        config = WeblateConfig()
        config.cli_url = "https://cli.example.com/api/"
        config.cli_key = "cli-key"
        try:
            os.environ["WLC_URL"] = "https://env.example.com/api/"
            os.environ["WLC_KEY"] = "env-key"
            url, key = config.get_url_key()
            self.assertEqual(url, "https://cli.example.com/api/")
            self.assertEqual(key, "cli-key")
        finally:
            del os.environ["WLC_URL"]
            del os.environ["WLC_KEY"]

    def test_default_method_whitelist_splits_newlines(self) -> None:
        """Default method whitelist parses newline-separated methods."""
        config = WeblateConfig()
        (
            _retries,
            _status_forcelist,
            method_whitelist,
            _backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(
            method_whitelist,
            ["HEAD", "TRACE", "DELETE", "OPTIONS", "PUT", "GET"],
        )

    def test_method_whitelist_strips_comma_separated_values(self) -> None:
        """Method whitelist strips surrounding whitespace for comma-separated values."""
        config = WeblateConfig()
        config.set("weblate", "method_whitelist", " PUT , POST,GET ")
        (
            _retries,
            _status_forcelist,
            method_whitelist,
            _backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(method_whitelist, ["PUT", "POST", "GET"])
