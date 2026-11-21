# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration parsing tests."""

import os
from configparser import Error as ConfigParserError
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from unittest import TestCase
from unittest.mock import patch

import wlc
from wlc.config import WeblateConfig, WLCConfigurationError

from .test_base import CONFIG_PARSE_ERRORS, CONFIG_PARSE_MARKER, load_discovered_config

TEST_DATA = Path(__file__).parent / "test_data"
TEST_CONFIG = TEST_DATA / "wlc"


class WeblateConfigTestCase(TestCase):
    """Weblate Client configuration parsing tests."""

    def test_find_config_windows(self) -> None:
        """Windows config discovery returns a Path and honors precedence."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            appdata = root / "appdata"
            localappdata = root / "localappdata"
            appdata.mkdir()
            localappdata.mkdir()
            local_config = localappdata / "weblate.ini"
            local_config.touch()
            with patch.dict(
                os.environ,
                {"APPDATA": str(appdata), "LOCALAPPDATA": str(localappdata)},
                clear=True,
            ):
                self.assertEqual(WeblateConfig.find_config(), local_config)
                app_config = appdata / "weblate.ini"
                app_config.touch()
                self.assertEqual(WeblateConfig.find_config(), app_config)

    def test_find_config_xdg(self) -> None:
        """XDG discovery wraps filenames in Path and preserves search order."""
        with (
            TemporaryDirectory() as tmpdirname,
            patch("xdg.BaseDirectory.xdg_config_dirs", [tmpdirname]),
            patch.dict(os.environ, {}, clear=True),
        ):
            root = Path(tmpdirname)
            self.assertIsNone(WeblateConfig.find_config())
            alternate = root / "weblate.ini"
            alternate.touch()
            self.assertEqual(WeblateConfig.find_config(), alternate)
            preferred = root / "weblate"
            preferred.touch()
            self.assertEqual(WeblateConfig.find_config(), preferred)

    def test_xdg_directory_allows_later_config(self) -> None:
        """Search remaining XDG locations when the first candidate is a directory."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            later = root / "system"
            later.mkdir()
            (root / "weblate").mkdir()
            with (
                patch("xdg.BaseDirectory.xdg_config_dirs", [str(root), str(later)]),
                patch.dict(os.environ, {}, clear=True),
            ):
                for filename in ("weblate.ini", "weblate"):
                    with self.subTest(filename=filename):
                        expected = later / filename
                        expected.touch()
                        self.assertEqual(WeblateConfig.find_config(), expected)

    def test_xdg_directory_cannot_hide_endpoint(self) -> None:
        """Use the alternate filename or fail before falling back to defaults."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            (root / "weblate").mkdir()
            with (
                patch("xdg.BaseDirectory.xdg_config_dirs", [str(root)]),
                patch.dict(os.environ, {}, clear=True),
                patch.object(WeblateConfig, "find_project_config", return_value=None),
            ):
                config = WeblateConfig()
                with self.assertRaisesRegex(WLCConfigurationError, "Could not read"):
                    config.load()
                alternate = root / "weblate.ini"
                alternate.write_text(
                    "[weblate]\nurl = https://example.org/api/\n", encoding="utf-8"
                )
                config.load()
                self.assertEqual(config.get_url_key(), ("https://example.org/api/", ""))
                with (
                    patch.object(config, "_read_config", return_value=[]),
                    self.assertRaisesRegex(WLCConfigurationError, "Could not read"),
                ):
                    config.load()

    def test_find_project_config_returns_path(self) -> None:
        """Project discovery returns the nearest matching Path."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "nested"
            nested.mkdir()
            expected = root / ".weblate"
            expected.touch()
            with patch("wlc.config.Path.cwd", return_value=nested):
                self.assertEqual(WeblateConfig.find_project_config(), expected)
                nearest = nested / "weblate.ini"
                nearest.touch()
                self.assertEqual(WeblateConfig.find_project_config(), nearest)

    def test_find_project_config_missing(self) -> None:
        """Project discovery terminates at the filesystem root."""
        with (
            patch("wlc.config.Path.cwd", return_value=Path(Path.cwd().anchor)),
            patch.object(WeblateConfig, "_project_stat", return_value=None),
        ):
            self.assertIsNone(WeblateConfig.find_project_config())

    def test_valid(self) -> None:
        """Valid configuration parsing."""
        config = WeblateConfig()
        config.load(TEST_CONFIG)

    def test_malformed_config_hides_contents(self) -> None:
        """Parser failures omit secrets even in formatted library tracebacks."""
        for content, detail in CONFIG_PARSE_ERRORS:
            with self.subTest(content=content), TemporaryDirectory() as tmpdirname:
                path = Path(tmpdirname) / "invalid.ini"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(WLCConfigurationError) as raised:
                    WeblateConfig().load(path)
                self.assertEqual(
                    str(raised.exception),
                    f"Invalid configuration file: {path} ({detail})",
                )
                self.assertNotIn(
                    CONFIG_PARSE_MARKER, "".join(format_exception(raised.exception))
                )

    def test_config_parser_error_without_line(self) -> None:
        """Parser errors without location metadata still omit their raw message."""
        with (
            patch(
                "wlc.config.RawConfigParser.read",
                side_effect=ConfigParserError("synthetic-config-secret"),
            ),
            self.assertRaises(WLCConfigurationError) as raised,
        ):
            WeblateConfig().load("invalid.ini")
        self.assertEqual(
            str(raised.exception), "Invalid configuration file: invalid.ini (Error)"
        )
        self.assertNotIn(
            "synthetic-config-secret", "".join(format_exception(raised.exception))
        )

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


class WeblateTransportConfigTestCase(TestCase):
    """Test origin-scoped transport configuration."""

    def test_duplicate_transport_origins_are_rejected(self) -> None:
        """Each trusted transport exception must have an unambiguous value."""
        with TemporaryDirectory() as tmpdirname:
            path = Path(tmpdirname) / "user.ini"
            for section, scheme in (
                ("insecure_ssl", "https"),
                ("insecure_http", "http"),
            ):
                with self.subTest(section=section):
                    path.write_text(
                        f"[{section}]\n{scheme}://EXAMPLE.org/ = no\n"
                        f"{scheme}://example.org/ = yes\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        WLCConfigurationError, "Duplicate origin"
                    ):
                        WeblateConfig().load(path)

    def test_allow_insecure_http_defaults_to_false(self) -> None:
        """Non-local HTTP token transport is disabled by default."""
        config = WeblateConfig()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(config.get_allow_insecure_http())

    def test_allow_insecure_http_from_config(self) -> None:
        """Configuration can allow HTTP for the selected origin."""
        config = WeblateConfig()
        config.set("weblate", "url", "http://example.com/api/")
        config.set("insecure_http", "http://EXAMPLE.com:80/other/", "yes")
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(config.get_allow_insecure_http())

        config.set("weblate", "url", "http://example.com:8080/api/")
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(config.get_allow_insecure_http())

    def test_allow_insecure_ssl_from_config(self) -> None:
        """Configuration can disable TLS verification for one origin."""
        config = WeblateConfig()
        config.set("weblate", "url", "https://example.com/api/")
        config.set("insecure_ssl", "https://EXAMPLE.com:443/other/", "yes")
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(config.get_allow_insecure_ssl())
            self.assertTrue(wlc.Weblate(config=config).allow_insecure_ssl)

        config.set("weblate", "url", "https://other.example.com/api/")
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(config.get_allow_insecure_ssl())

    def test_insecure_origin_configuration_is_validated(self) -> None:
        """Invalid security-sensitive configuration should fail closed."""
        config = WeblateConfig()
        config.set("insecure_ssl", "http://example.com/", "yes")
        with self.assertRaisesRegex(WLCConfigurationError, "Invalid origin"):
            config.get_allow_insecure_ssl()

        config = WeblateConfig()
        config.set("insecure_http", "http://example.com/", "sometimes")
        with self.assertRaisesRegex(WLCConfigurationError, "Invalid boolean"):
            config.get_allow_insecure_http()

    def test_global_insecure_configuration_is_rejected(self) -> None:
        """Legacy global opt-ins should provide scoped migration guidance."""
        config = WeblateConfig()
        config.set("weblate", "allow_insecure_http", "yes")
        with self.assertRaisesRegex(WLCConfigurationError, r"\[insecure_http\]"):
            config.get_allow_insecure_http()

    def test_insecure_origin_does_not_inherit_from_default(self) -> None:
        """DEFAULT entries can not implicitly add trusted origins."""
        config = WeblateConfig()
        config.set("weblate", "url", "https://example.com/api/")
        config.set("DEFAULT", "https://example.com:443", "yes")

        self.assertFalse(config.get_allow_insecure_ssl())

    def test_allow_insecure_http_from_env(self) -> None:
        """Environment can explicitly allow non-local HTTP token transport."""
        config = WeblateConfig()
        with patch.dict(os.environ, {"WLC_ALLOW_INSECURE_HTTP": "1"}, clear=True):
            self.assertTrue(config.get_allow_insecure_http())

    def test_allow_insecure_http_from_cli(self) -> None:
        """CLI can explicitly allow non-local HTTP token transport."""
        config = WeblateConfig()
        config.cli_allow_insecure_http = True
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(config.get_allow_insecure_http())

    def test_allow_insecure_ssl_from_env_and_cli(self) -> None:
        """Transient trusted sources can explicitly disable TLS verification."""
        config = WeblateConfig()
        config.set("weblate", "url", "https://example.com/api/")
        with patch.dict(os.environ, {"WLC_ALLOW_INSECURE_SSL": "1"}, clear=True):
            self.assertTrue(config.get_allow_insecure_ssl())

        config.cli_allow_insecure_ssl = True
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(config.get_allow_insecure_ssl())


class WeblateRequestConfigTestCase(TestCase):
    """Test request option parsing."""

    def test_default_allowed_methods_splits_newlines(self) -> None:
        """Default allowed methods parse newline-separated methods."""
        config = WeblateConfig()
        (
            _retries,
            _status_forcelist,
            allowed_methods,
            _backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(
            allowed_methods,
            ["HEAD", "DELETE", "OPTIONS", "PUT", "GET"],
        )

    def test_allowed_methods_strip_comma_separated_values(self) -> None:
        """Allowed methods strip surrounding whitespace for comma-separated values."""
        config = WeblateConfig()
        config.set("weblate", "allowed_methods", " PUT , POST,GET ")
        (
            _retries,
            _status_forcelist,
            allowed_methods,
            _backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(allowed_methods, ["PUT", "POST", "GET"])


class WeblateConfigLoadingTestCase(TestCase):
    """Test explicit and discovered configuration loading."""

    def test_explicit_path_ignores_project_config(self) -> None:
        """Explicit config does not load project config from cwd or parents."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            explicit = root / "explicit.ini"
            explicit.write_text(
                "[weblate]\nurl = https://explicit.example.com/api/\n"
                "\n"
                "[insecure_ssl]\nhttps://explicit.example.com:443 = yes\n",
                encoding="utf-8",
            )
            repo = root / "repo"
            nested = repo / "nested"
            nested.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/\n",
                encoding="utf-8",
            )
            (root / ".weblate").write_text(
                "[weblate]\nurl = http://ancestor.example.com/\n",
                encoding="utf-8",
            )
            with patch.object(Path, "cwd", return_value=nested):
                config = WeblateConfig()
                config.load(explicit)

        self.assertEqual(
            config.get("weblate", "url"), "https://explicit.example.com/api/"
        )
        self.assertTrue(config.get_allow_insecure_ssl())

    def test_explicit_path_must_be_read(self) -> None:
        """Explicit config path should fail fast when the file is missing."""
        with TemporaryDirectory() as tmpdirname:
            missing = Path(tmpdirname) / "missing.ini"
            config = WeblateConfig()

            with self.assertRaisesRegex(
                WLCConfigurationError,
                rf"Could not read configuration file: .*{missing.name}",
            ):
                config.load(missing)

    def test_empty_explicit_path_does_not_discover_config(self) -> None:
        """An empty explicit path fails without loading discovered configuration."""
        with (
            patch.object(
                WeblateConfig,
                "find_config",
                side_effect=AssertionError("User configuration discovery must not run"),
            ) as user,
            patch.object(
                WeblateConfig,
                "find_project_config",
                side_effect=AssertionError(
                    "Project configuration discovery must not run"
                ),
            ) as project,
            self.assertRaisesRegex(
                WLCConfigurationError, "Could not read configuration file:"
            ),
        ):
            WeblateConfig().load("")

        user.assert_not_called()
        project.assert_not_called()

    def test_default_load_uses_nearest_project_config(self) -> None:
        """Default discovery loads global config and the nearest project config."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[weblate]\nurl = https://global.example.com/api/\ntimeout = 45\n",
                encoding="utf-8",
            )
            repo = root / "repo"
            nested = repo / "nested"
            nested.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://127.0.0.1:8000/api/\n",
                encoding="utf-8",
            )
            config = load_discovered_config(nested, global_config)

        self.assertEqual(config.get("weblate", "url"), "http://127.0.0.1:8000/api/")
        self.assertEqual(config.get("weblate", "timeout"), "45")

    def test_default_load_stops_after_nearest_project_config(self) -> None:
        """Default discovery does not merge project configs from farther parents."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[weblate]\ntimeout = 45\n",
                encoding="utf-8",
            )
            repo = root / "repo"
            nested = repo / "nested"
            deep = nested / "deep"
            deep.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nretries = 99\n",
                encoding="utf-8",
            )
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://nearest.example.com/api/\n",
                encoding="utf-8",
            )
            config = load_discovered_config(deep, global_config)

        self.assertEqual(
            config.get("weblate", "url"), "https://nearest.example.com/api/"
        )
        self.assertEqual(config.get("weblate", "timeout"), "45")
        self.assertEqual(config.get("weblate", "retries"), "0")

    def test_default_load_skips_project_config_directories(self) -> None:
        """Discovery ignores directory names that only look like config files."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            repo = root / "repo"
            nested = repo / "nested"
            deep = nested / "deep"
            deep.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = https://parent.example.com/api/\n",
                encoding="utf-8",
            )
            (nested / ".weblate").mkdir()
            config = load_discovered_config(deep)

        self.assertEqual(
            config.get("weblate", "url"), "https://parent.example.com/api/"
        )
