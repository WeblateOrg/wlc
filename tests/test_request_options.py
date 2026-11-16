# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Validation of request options from configuration and Python callers."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest import TestCase
from unittest.mock import patch

from wlc import Weblate, WeblateException
from wlc.config import WeblateConfig, WLCConfigurationError

from .test_base import CLITestBase


class RequestOptionsTest(TestCase):
    """Invalid options fail before making HTTP requests."""

    def test_invalid_configuration(self) -> None:
        """Malformed and out-of-range configuration values are rejected."""
        for option, values in (
            ("retries", ("-1", "1.5", "secret-value", "nan", "inf")),
            ("timeout", ("0", "-1", "1.5", "nan", "inf", "-inf", "secret-value")),
            ("backoff_factor", ("-1", "nan", "inf", "-inf", "secret-value")),
            (
                "status_forcelist",
                ("200", "399", "600", "500,200", "500,", "secret-value"),
            ),
        ):
            for value in values:
                with self.subTest(option=option, value=value):
                    config = WeblateConfig()
                    config.set("weblate", option, value)
                    with self.assertRaises(WLCConfigurationError) as caught:
                        config.get_request_options()
                    self.assertTrue(str(caught.exception).startswith(option))
                    self.assertNotIn("secret-value", str(caught.exception))

    def test_missing_numeric_configuration(self) -> None:
        """Missing numeric values produce a configuration error."""
        config = WeblateConfig()
        config.set("weblate", "timeout", None)
        with self.assertRaisesRegex(WLCConfigurationError, "^timeout must"):
            config.get_request_options()

    def test_invalid_python_arguments(self) -> None:
        """Direct client arguments receive the same validation."""
        with patch("requests.Session.request") as request:
            for retries in (-1, cast("int", 1.5)):
                with (
                    self.subTest(retries=retries),
                    self.assertRaisesRegex(WeblateException, "^retries must"),
                ):
                    Weblate(retries=retries)
            for timeout in (0, -1, float("nan"), float("inf"), -float("inf")):
                with (
                    self.subTest(timeout=timeout),
                    self.assertRaisesRegex(WeblateException, "^timeout must"),
                ):
                    Weblate(timeout=cast("int", timeout))
            for backoff in (-1, float("nan"), float("inf"), -float("inf")):
                with (
                    self.subTest(backoff=backoff),
                    self.assertRaisesRegex(WeblateException, "^backoff_factor must"),
                ):
                    Weblate(backoff_factor=backoff)
            for statuses in ([200], [399], [600], [500, 200], [cast("int", 500.5)]):
                with (
                    self.subTest(statuses=statuses),
                    self.assertRaisesRegex(WeblateException, "^status_forcelist must"),
                ):
                    Weblate(status_forcelist=statuses)
            request.assert_not_called()

    def test_unrepresentable_python_arguments(self) -> None:
        """Wrong types and oversized integers receive option-specific errors."""
        with patch("requests.Session.request") as request:
            for value in (None, "secret-value", 10**1000):
                with (
                    self.subTest(option="timeout", value=value),
                    self.assertRaisesRegex(
                        WeblateException,
                        r"^timeout must be finite and greater than zero\.$",
                    ),
                ):
                    Weblate(timeout=cast("int", value))
                with (
                    self.subTest(option="backoff_factor", value=value),
                    self.assertRaisesRegex(
                        WeblateException,
                        r"^backoff_factor must be finite and nonnegative\.$",
                    ),
                ):
                    Weblate(backoff_factor=cast("float", value))
            request.assert_not_called()

    def test_oversized_configuration_timeout(self) -> None:
        """An integer too large for the transport produces a configuration error."""
        config = WeblateConfig()
        config.set("weblate", "timeout", str(10**1000))
        with self.assertRaisesRegex(WLCConfigurationError, "^timeout must"):
            config.get_request_options()

    def test_valid_options(self) -> None:
        """Boundary values and large valid settings retain their behavior."""
        for retries, backoff, timeout in ((0, 0.0, 1), (999, 10.0, 600)):
            for statuses in (None, [], [400, 429, 500, 599]):
                with self.subTest(retries=retries, statuses=statuses):
                    client = Weblate(
                        retries=retries,
                        backoff_factor=backoff,
                        timeout=timeout,
                        status_forcelist=statuses,
                        allowed_methods=["POST"],
                    )
                    self.assertEqual(client.adapter.max_retries.total, retries)
                    self.assertEqual(client.allowed_methods, ["POST"])
                    config = WeblateConfig()
                    config.set("weblate", "retries", str(retries))
                    config.set("weblate", "timeout", str(timeout))
                    config.set("weblate", "backoff_factor", str(backoff))
                    config.set("weblate", "allowed_methods", "POST")
                    config.set(
                        "weblate",
                        "status_forcelist",
                        None if statuses is None else ",".join(map(str, statuses)),
                    )
                    self.assertEqual(
                        config.get_request_options(),
                        (retries, statuses, ["POST"], backoff, timeout),
                    )
                    configured = Weblate(config=config)
                    self.assertEqual(configured.retry_total, retries)
                    client.session.close()
                    configured.session.close()


class RequestOptionsCLITest(CLITestBase):
    """Request option errors are handled by the command-line interface."""

    def test_invalid_request_configuration(self) -> None:
        """Explicit and discovered request options produce handled errors."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            (root / ".git").mkdir()
            config = root / ".weblate"
            for option, value in (
                ("retries", "-1"),
                ("timeout", "secret-value"),
                ("timeout", str(10**1000)),
                ("backoff_factor", "nan"),
                ("status_forcelist", "200"),
            ):
                config.write_text(f"[weblate]\n{option} = {value}\n", encoding="utf-8")
                for explicit in (True, False):
                    args = ["--config", str(config)] if explicit else []
                    with (
                        self.subTest(option=option, explicit=explicit),
                        patch("wlc.config.Path.cwd", return_value=root),
                        patch.object(WeblateConfig, "find_config", return_value=None),
                        patch("requests.Session.request") as request,
                    ):
                        output = self.execute(
                            [*args, "list-projects"], settings=False, expected=1
                        )
                    self.assertIn(f"Error: {option} must", output)
                    self.assertNotIn("secret-value", output)
                    self.assertNotIn("Traceback", output)
                    request.assert_not_called()
