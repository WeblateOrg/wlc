# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Project Configuration parsing tests."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import wlc
from wlc.config import WeblateConfig, WLCConfigurationError

from .test_base import load_discovered_config


class WeblateProjectConfigTestCase(TestCase):
    """Test project configuration trust boundaries."""

    def test_project_keys_only_apply_to_own_url(self) -> None:
        """A project key cannot replace a user key for an unrelated URL."""
        company_url = "https://company.example.com/api/"
        project_url = "https://repo.example.com/api/"
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            user_config = root / "user.ini"
            user_config.write_text(
                f"[weblate]\nurl = {company_url}\n[keys]\n{company_url} = user-key\n",
                encoding="utf-8",
            )
            project_config = root / ".weblate"
            project_config.write_text(
                f"[weblate]\nurl = {project_url}\n"
                f"[keys]\n{company_url} = attacker-key\n"
                f"{project_url} = project-key\n",
                encoding="utf-8",
            )
            config = WeblateConfig()
            with (
                patch.object(WeblateConfig, "find_config", return_value=user_config),
                patch.object(
                    WeblateConfig, "find_project_config", return_value=project_config
                ),
                patch.dict(os.environ, {}, clear=True),
            ):
                config.load()
                self.assertEqual(config.get_url_key(), (project_url, "project-key"))
                config.cli_url = company_url
                self.assertEqual(config.get_url_key(), (company_url, "user-key"))
                config.cli_url = None
                with patch.dict(os.environ, {"WLC_URL": company_url}, clear=True):
                    self.assertEqual(config.get_url_key(), (company_url, "user-key"))

    def test_scoped_key_preserves_path_case(self) -> None:
        """A project can only select a user key for the matching path."""
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            user = root / "user.ini"
            user.write_text(
                "[keys]\nhttps://EXAMPLE.org:443/API/ = upper\n", encoding="utf-8"
            )
            project = root / ".weblate"
            project.write_text(
                "[weblate]\nURL = https://example.org/api/\n", encoding="utf-8"
            )
            config = WeblateConfig()
            with (
                patch.object(WeblateConfig, "find_config", return_value=user),
                patch.dict(os.environ, {}, clear=True),
            ):
                config.load(project_path=project)
                self.assertEqual(config.get_url_key(), ("https://example.org/api/", ""))
                config.cli_url = "https://example.org/API/"
                self.assertEqual(config.get_url_key(), (config.cli_url, "upper"))

    def test_project_keys_require_project_url(self) -> None:
        """A project without a URL cannot replace user keys."""
        company_url = "https://company.example.com/api/"
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            user_config = root / "user.ini"
            user_config.write_text(
                f"[weblate]\nurl = {company_url}\n[keys]\n{company_url} = user-key\n",
                encoding="utf-8",
            )
            project_config = root / ".weblate"
            project_config.write_text(
                f"[keys]\n{company_url} = attacker-key\n", encoding="utf-8"
            )
            config = WeblateConfig()
            with (
                patch.object(WeblateConfig, "find_config", return_value=user_config),
                patch.object(
                    WeblateConfig, "find_project_config", return_value=project_config
                ),
                patch.dict(os.environ, {}, clear=True),
            ):
                config.load()
                self.assertEqual(config.get_url_key(), (company_url, "user-key"))

    def test_project_default_entries_are_not_api_keys(self) -> None:
        """Project DEFAULT entries cannot supply inherited API keys."""
        company_url = "https://company.example.com/api/"
        with TemporaryDirectory() as tmpdirname:
            root = Path(tmpdirname)
            project_config = root / ".weblate"
            project_config.write_text(
                f"[DEFAULT]\n{company_url} = attacker-key\n"
                "[weblate]\nurl = https://repo.example.com/api/\n"
                "[keys]\n",
                encoding="utf-8",
            )
            config = WeblateConfig()
            with (
                patch.object(WeblateConfig, "find_config", return_value=None),
                patch.object(
                    WeblateConfig, "find_project_config", return_value=project_config
                ),
                patch.dict(os.environ, {}, clear=True),
            ):
                config.load()
                config.cli_url = company_url
                self.assertEqual(config.get_url_key(), (company_url, ""))

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
            config = load_discovered_config(nested, global_config)

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
            config = load_discovered_config(nested, user_config)

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
            for attribute, option in (
                ("cli_allow_insecure_http", "--allow-insecure-http"),
                ("cli_allow_insecure_ssl", "--allow-insecure-ssl"),
            ):
                with self.subTest(option=option):
                    config = load_discovered_config(root)
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
                    config = load_discovered_config(root)
                    with (
                        patch.dict(os.environ, {variable: "1"}, clear=True),
                        self.assertRaisesRegex(
                            WLCConfigurationError, "requires WLC_URL"
                        ),
                    ):
                        config.validate_url_key()

            config = load_discovered_config(root)
            config.cli_url = "https://cli.example.com/api/"
            config.cli_allow_insecure_ssl = True
            config.validate_url_key()
            self.assertTrue(config.get_allow_insecure_ssl())

            config = load_discovered_config(root)
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
            config = load_discovered_config(nested, global_config)

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
            config = load_discovered_config(nested, global_config)

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
            config = load_discovered_config(nested, global_config, section="custom")

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
            config = load_discovered_config(nested)
            with (
                patch.dict(os.environ, {"WLC_KEY": "env-api-key"}, clear=True),
                self.assertRaisesRegex(
                    WLCConfigurationError,
                    "Using WLC_KEY with project configuration requires WLC_URL",
                ),
            ):
                config.get_url_key()

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
            config = load_discovered_config(nested)
            with patch.dict(
                os.environ,
                {
                    "WLC_KEY": "env-api-key",
                    "WLC_URL": "https://env.example.com/api/",
                },
                clear=True,
            ):
                url, key = config.get_url_key()

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
            config = load_discovered_config(nested)
            config.cli_key = "cli-api-key"

            with self.assertRaisesRegex(
                WLCConfigurationError,
                "Using --key with project configuration requires --url",
            ):
                config.get_url_key()

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
            config = load_discovered_config(nested)
            config.cli_key = "cli-api-key"
            config.cli_url = "https://cli.example.com/api/"
            url, key = config.get_url_key()

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
            config = load_discovered_config(nested)
            url, key = config.get_url_key()

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
