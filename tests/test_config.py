# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration parsing tests."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

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
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                config.load(explicit)
            finally:
                os.chdir(current)

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
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

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
            current = os.getcwd()
            try:
                os.chdir(deep)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

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
            current = os.getcwd()
            try:
                os.chdir(deep)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
            finally:
                os.chdir(current)

        self.assertEqual(
            config.get("weblate", "url"), "https://parent.example.com/api/"
        )

    def test_project_config_cannot_allow_insecure_http(self) -> None:
        """Project config can not opt users into insecure transport."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[keys]\nhttp://repo.example.com/api/ = scoped-api-key\n",
                encoding="utf-8",
            )
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[DEFAULT]\n"
                "allow_insecure_http = yes\n"
                "allow_insecure_ssl = yes\n"
                "\n"
                "[weblate]\n"
                "url = http://repo.example.com/api/\n"
                "allow_insecure_http = yes\n"
                "allow_insecure_ssl = yes\n"
                "\n"
                "[insecure_http]\n"
                "http://repo.example.com:80 = yes\n"
                "\n"
                "[insecure_ssl]\n"
                "https://repo.example.com:443 = yes\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

        self.assertFalse(config.get_allow_insecure_http())
        self.assertEqual(config.get_url_key()[1], "scoped-api-key")
        with self.assertRaisesRegex(wlc.WeblateException, "insecure HTTP"):
            wlc.Weblate(config=config)
        config.cli_url = "https://repo.example.com/api/"
        self.assertFalse(config.get_allow_insecure_ssl())

    def test_project_config_cannot_supply_url_credentials(self) -> None:
        """A discovered project URL can not enable implicit authentication."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            user_config = root / "global.ini"
            user_config.write_text(
                "[insecure_http]\nhttp://repo.example.com:80 = yes\n",
                encoding="utf-8",
            )
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = http://user:password@repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(user_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

        self.assertTrue(config.get_allow_insecure_http())
        with self.assertRaisesRegex(wlc.WeblateException, "embedded in URLs"):
            wlc.Weblate(config=config)

    def test_project_url_requires_transient_insecure_option_url_pairing(self) -> None:
        """Unscoped insecure overrides can not target a project-selected URL."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            project_config = root / ".weblate"
            project_config.write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(root)
                for attribute, option in (
                    ("cli_allow_insecure_http", "--allow-insecure-http"),
                    ("cli_allow_insecure_ssl", "--allow-insecure-ssl"),
                ):
                    with self.subTest(option=option):
                        config = WeblateConfig()
                        with patch.object(
                            WeblateConfig, "find_config", return_value=None
                        ):
                            config.load()
                        setattr(config, attribute, True)
                        with self.assertRaisesRegex(
                            WLCConfigurationError, "requires --url"
                        ):
                            config.validate_url_key()

                for variable in (
                    "WLC_ALLOW_INSECURE_HTTP",
                    "WLC_ALLOW_INSECURE_SSL",
                ):
                    with self.subTest(variable=variable):
                        config = WeblateConfig()
                        with patch.object(
                            WeblateConfig, "find_config", return_value=None
                        ):
                            config.load()
                        with (
                            patch.dict(os.environ, {variable: "1"}, clear=True),
                            self.assertRaisesRegex(
                                WLCConfigurationError, "requires WLC_URL"
                            ),
                        ):
                            config.validate_url_key()

                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                config.cli_url = "https://cli.example.com/api/"
                config.cli_allow_insecure_ssl = True
                config.validate_url_key()
                self.assertTrue(config.get_allow_insecure_ssl())

                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                with patch.dict(
                    os.environ,
                    {
                        "WLC_URL": "https://env.example.com/api/",
                        "WLC_ALLOW_INSECURE_SSL": "1",
                    },
                    clear=True,
                ):
                    config.validate_url_key()
                    self.assertTrue(config.get_allow_insecure_ssl())
            finally:
                os.chdir(current)

    def test_user_config_can_allow_insecure_http_with_project_url(self) -> None:
        """User config can opt into insecure transport for project URLs."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[insecure_http]\nhttp://repo.example.com:80 = yes\n"
                "\n"
                "[keys]\nhttp://repo.example.com/api/ = scoped-api-key\n",
                encoding="utf-8",
            )
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = http://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

        self.assertTrue(config.get_allow_insecure_http())
        client = wlc.Weblate(config=config)
        self.assertTrue(client.allow_insecure_http)

    def test_user_config_can_allow_insecure_ssl_with_project_url(self) -> None:
        """A trusted origin entry can approve a project-selected HTTPS server."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[insecure_ssl]\nhttps://repo.example.com:443 = yes\n",
                encoding="utf-8",
            )
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

        self.assertTrue(config.get_allow_insecure_ssl())
        self.assertTrue(wlc.Weblate(config=config).allow_insecure_ssl)

    def test_project_config_without_selected_section_is_harmless(self) -> None:
        """Project config without selected section should not crash loading."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            global_config = root / "global.ini"
            global_config.write_text(
                "[custom]\nurl = https://custom.example.com/api/\n",
                encoding="utf-8",
            )
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\n"
                "url = http://repo.example.com/api/\n"
                "allow_insecure_http = yes\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig(section="custom")
                with patch.object(
                    WeblateConfig, "find_config", return_value=str(global_config)
                ):
                    config.load()
            finally:
                os.chdir(current)

        self.assertEqual(config.get("custom", "url"), "https://custom.example.com/api/")
        self.assertFalse(config.get_allow_insecure_http())

    def test_project_config_with_env_key_requires_env_url(self) -> None:
        """Project config URL can not be paired with unscoped WLC_KEY."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                with (
                    patch.dict(os.environ, {"WLC_KEY": "env-api-key"}, clear=True),
                    self.assertRaisesRegex(
                        WLCConfigurationError,
                        "Using WLC_KEY with project configuration requires WLC_URL",
                    ),
                ):
                    config.get_url_key()
            finally:
                os.chdir(current)

    def test_project_config_with_env_key_allows_env_url(self) -> None:
        """WLC_KEY can be used when WLC_URL pins the destination."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                with patch.dict(
                    os.environ,
                    {
                        "WLC_KEY": "env-api-key",
                        "WLC_URL": "https://env.example.com/api/",
                    },
                    clear=True,
                ):
                    url, key = config.get_url_key()
            finally:
                os.chdir(current)

        self.assertEqual(url, "https://env.example.com/api/")
        self.assertEqual(key, "env-api-key")

    def test_project_config_with_cli_key_requires_cli_url(self) -> None:
        """Project config URL can not be paired with unscoped --key."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                config.cli_key = "cli-api-key"

                with self.assertRaisesRegex(
                    WLCConfigurationError,
                    "Using --key with project configuration requires --url",
                ):
                    config.get_url_key()
            finally:
                os.chdir(current)

    def test_project_config_with_cli_key_allows_cli_url(self) -> None:
        """--key can be used when --url pins the destination."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                config.cli_key = "cli-api-key"
                config.cli_url = "https://cli.example.com/api/"
                url, key = config.get_url_key()
            finally:
                os.chdir(current)

        self.assertEqual(url, "https://cli.example.com/api/")
        self.assertEqual(key, "cli-api-key")

    def test_project_config_allows_scoped_keys(self) -> None:
        """Project config URL can use matching URL-scoped keys."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            nested = root / "repo"
            nested.mkdir()
            (nested / ".weblate").write_text(
                "[weblate]\nurl = https://repo.example.com/api/\n"
                "\n"
                "[keys]\nhttps://repo.example.com/api/ = scoped-api-key\n",
                encoding="utf-8",
            )
            current = os.getcwd()
            try:
                os.chdir(nested)
                config = WeblateConfig()
                with patch.object(WeblateConfig, "find_config", return_value=None):
                    config.load()
                url, key = config.get_url_key()
            finally:
                os.chdir(current)

        self.assertEqual(url, "https://repo.example.com/api/")
        self.assertEqual(key, "scoped-api-key")

    def test_explicit_config_with_env_key_remains_supported(self) -> None:
        """Explicit config URL can still be paired with WLC_KEY."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            explicit = root / "explicit.ini"
            explicit.write_text(
                "[weblate]\nurl = https://explicit.example.com/api/\n",
                encoding="utf-8",
            )
            config = WeblateConfig()
            config.load(explicit)

            with patch.dict(os.environ, {"WLC_KEY": "env-api-key"}, clear=True):
                url, key = config.get_url_key()

        self.assertEqual(url, "https://explicit.example.com/api/")
        self.assertEqual(key, "env-api-key")
