# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test command-line interface."""
# pylint: disable=missing-function-docstring

from __future__ import annotations

import errno
import os
import sys
from io import BytesIO, TextIOWrapper
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from unittest.mock import patch

import wlc
from wlc.config import WeblateConfig

from .test_base import (
    TEST_CONFIG,
    TEST_DATA,
    TEST_SECTION,
    CLITestBase,
)


class TestSettings(CLITestBase):
    """Test settings handling."""

    def test_commandline(self) -> None:
        """Configuration using command-line."""
        output = self.execute(["--url", "https://example.net/", "list-projects"])
        self.assertIn("Hello", output)

    def test_stdout(self) -> None:
        """Configuration using params."""
        output = self.execute(["list-projects"], stdout=True)
        self.assertIn("Hello", output)

    def test_debug(self) -> None:
        """Debug mode."""
        output = self.execute(["--debug", "list-projects"], stdout=True)
        self.assertIn("HTTP request", output)
        self.assertIn("api/projects", output)

    def test_debug_redacts_authorization(self) -> None:
        """Debug mode should not leak API tokens."""
        try:
            os.environ["WLC_KEY"] = "KEY"
            output = self.execute(["--debug", "show", "acl"], stdout=True)
            self.assertIn('"Authorization": "<redacted>"', output)
            self.assertNotIn("Token KEY", output)
        finally:
            del os.environ["WLC_KEY"]

    def test_settings(self) -> None:
        """Configuration using settings param."""
        output = self.execute(
            ["list-projects"], settings=(("weblate", "url", "https://example.net/"),)
        )
        self.assertIn("Hello", output)

    def test_config(self) -> None:
        """Configuration using custom config file."""
        output = self.execute(
            ["--config", str(TEST_CONFIG), "list-projects"], settings=False
        )
        self.assertIn("Hello", output)

    def test_explicit_config_is_authoritative(self) -> None:
        """Explicit config is not overridden by repo config in cwd."""
        current = Path.cwd()
        with TemporaryDirectory() as tmpdirname:
            explicit = Path(tmpdirname) / "explicit.ini"
            explicit.write_text(
                "[weblate]\nurl = http://127.0.0.1:8000/api/\n", encoding="utf-8"
            )

            repo = Path(tmpdirname) / "repo"
            nested = repo / "nested"
            nested.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/\n", encoding="utf-8"
            )

            try:
                os.environ["WLC_KEY"] = "KEY"
                os.chdir(nested)
                output = self.execute(
                    ["--config", str(explicit), "show", "acl"], settings=False
                )
            finally:
                os.chdir(current)
                if "WLC_KEY" in os.environ:
                    del os.environ["WLC_KEY"]

        self.assertIn("ACL", output)

    def test_missing_explicit_config_reports_error(self) -> None:
        """Missing explicit config path should be reported to the user."""
        with TemporaryDirectory() as tmpdirname:
            missing = Path(tmpdirname) / "missing.ini"
            output = self.execute(
                ["--config", str(missing), "list-projects"], settings=False, expected=1
            )

        self.assertIn("Error: Could not read configuration file:", output)
        self.assertIn("missing.ini", output)

    def test_config_section(self) -> None:
        """Configuration using custom config file section."""
        output = self.execute(
            [
                "--config",
                str(TEST_SECTION),
                "--config-section",
                "custom",
                "list-projects",
            ],
            settings=False,
        )
        self.assertIn("Hello", output)

    def test_config_key(self) -> None:
        """Configuration using custom config file section and key set is ignored."""
        output = self.execute(
            [
                "--config",
                str(TEST_CONFIG),
                "--config-section",
                "withkey",
                "show",
                "acl",
            ],
            settings=False,
            expected=1,
        )
        self.assertIn(
            "Error: Using 'key' in settings is insecure, use [keys] section instead",
            output,
        )

    def test_config_appdata(self) -> None:
        """Verify keys are loaded from the [keys] section in APPDATA-based config."""
        output = self.execute(["show", "acl"], settings=False, expected=1)
        self.assertIn("You don't have permission to access this object", output)
        try:
            os.environ["APPDATA"] = str(TEST_DATA)
            output = self.execute(["show", "acl"], settings=False)
            self.assertIn("ACL", output)
        finally:
            del os.environ["APPDATA"]

    def test_env_key(self) -> None:
        """Verify WLC_KEY environment variable provides API key."""
        try:
            os.environ["WLC_KEY"] = "KEY"
            output = self.execute(["show", "acl"], settings=False)
            self.assertIn("ACL", output)
        finally:
            del os.environ["WLC_KEY"]

    def test_env_url(self) -> None:
        """Verify WLC_URL environment variable provides API URL."""
        try:
            os.environ["WLC_URL"] = "https://example.net/"
            output = self.execute(["list-projects"], settings=False)
            self.assertIn("Hello", output)
        finally:
            del os.environ["WLC_URL"]

    def test_config_cwd(self) -> None:
        """Test loading settings from current dir."""
        current = Path.cwd()
        try:
            os.chdir(Path(__file__).parent / "test_data")
            output = self.execute(["show"], settings=False)
            self.assertIn("Weblate", output)
        finally:
            os.chdir(current)

    def test_default_config_values(self) -> None:
        """Test default parser values."""
        config = WeblateConfig()
        self.assertEqual(config.get("weblate", "retries"), "0")
        self.assertEqual(config.get("weblate", "timeout"), "300")
        self.assertEqual(
            config.get("weblate", "allowed_methods"),
            "HEAD\nDELETE\nOPTIONS\nPUT\nGET",
        )
        self.assertEqual(config.get("weblate", "backoff_factor"), "0")
        self.assertIsNone(config.get("weblate", "status_forcelist"))

    def test_parsing(self) -> None:
        """Test config file parsing."""
        config = WeblateConfig()
        self.assertEqual(config.get("weblate", "url"), wlc.API_URL)
        config.load()
        config.load(TEST_CONFIG)
        self.assertEqual(config.get("weblate", "url"), "https://example.net/")
        self.assertEqual(config.get("weblate", "retries"), "999")
        self.assertEqual(config.get("weblate", "allowed_methods"), "PUT,POST")
        self.assertEqual(config.get("weblate", "backoff_factor"), "0.2")
        self.assertEqual(
            config.get("weblate", "status_forcelist"), "429,500,502,503,504"
        )

    def test_get_request_options(self) -> None:
        """Test the get_request_options method when all options are in config."""
        config = WeblateConfig()
        config.load()
        config.load(TEST_CONFIG)
        (
            retries,
            status_forcelist,
            allowed_methods,
            backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(retries, 999)
        self.assertEqual(status_forcelist, [429, 500, 502, 503, 504])
        self.assertEqual(allowed_methods, ["PUT", "POST"])
        self.assertEqual(backoff_factor, 0.2)

    def test_default_request_options(self) -> None:
        """Test the get_request_options method with default config values."""
        config = WeblateConfig()
        (
            retries,
            status_forcelist,
            allowed_methods,
            backoff_factor,
            timeout,
        ) = config.get_request_options()
        self.assertEqual(retries, 0)
        self.assertIsNone(status_forcelist)
        self.assertEqual(
            allowed_methods,
            ["HEAD", "DELETE", "OPTIONS", "PUT", "GET"],
        )
        self.assertEqual(backoff_factor, 0.0)
        self.assertEqual(timeout, 300)

    def test_argv(self) -> None:
        """Test sys.argv processing."""
        backup = sys.argv
        try:
            sys.argv = ["wlc", "version"]
            output = self.execute(None)
            self.assertIn(f"version: {wlc.__version__}", output)
        finally:
            sys.argv = backup


class TestProjectSettings(CLITestBase):
    """Test project configuration credential precedence."""

    def test_project_config_with_env_key_reports_error(self) -> None:
        """WLC_KEY can not use a URL from discovered project config."""
        current = Path.cwd()
        with TemporaryDirectory() as tmpdirname:
            repo = Path(tmpdirname) / "repo"
            repo.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/api/\n", encoding="utf-8"
            )

            try:
                os.chdir(repo)
                with (
                    patch.object(WeblateConfig, "find_config", return_value=None),
                    patch.dict(os.environ, {"WLC_KEY": "KEY"}, clear=True),
                ):
                    output = self.execute(["show", "acl"], settings=False, expected=1)
            finally:
                os.chdir(current)

        self.assertIn(
            "Error: Using WLC_KEY with project configuration requires WLC_URL.",
            output,
        )

    def test_project_config_with_env_key_allows_env_url(self) -> None:
        """WLC_KEY can use WLC_URL even when project config is present."""
        current = Path.cwd()
        with TemporaryDirectory() as tmpdirname:
            repo = Path(tmpdirname) / "repo"
            repo.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/api/\n", encoding="utf-8"
            )

            try:
                os.chdir(repo)
                with (
                    patch.object(WeblateConfig, "find_config", return_value=None),
                    patch.dict(
                        os.environ,
                        {
                            "WLC_KEY": "KEY",
                            "WLC_URL": "http://127.0.0.1:8000/api/",
                        },
                        clear=True,
                    ),
                ):
                    output = self.execute(["show", "acl"], settings=False)
            finally:
                os.chdir(current)

        self.assertIn("ACL", output)

    def test_project_config_with_cli_key_reports_error(self) -> None:
        """--key can not use a URL from discovered project config."""
        current = Path.cwd()
        with TemporaryDirectory() as tmpdirname:
            repo = Path(tmpdirname) / "repo"
            repo.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/api/\n", encoding="utf-8"
            )

            try:
                os.chdir(repo)
                with (
                    patch.object(WeblateConfig, "find_config", return_value=None),
                    patch.dict(os.environ, {}, clear=True),
                ):
                    output = self.execute(
                        ["--key", "KEY", "show", "acl"],
                        settings=False,
                        expected=1,
                    )
            finally:
                os.chdir(current)

        self.assertIn(
            "Error: Using --key with project configuration requires --url.",
            output,
        )

    def test_project_config_with_cli_key_allows_cli_url(self) -> None:
        """--key can use --url even when project config is present."""
        current = Path.cwd()
        with TemporaryDirectory() as tmpdirname:
            repo = Path(tmpdirname) / "repo"
            repo.mkdir(parents=True)
            (repo / ".weblate").write_text(
                "[weblate]\nurl = http://denied.example.com/api/\n", encoding="utf-8"
            )

            try:
                os.chdir(repo)
                with (
                    patch.object(WeblateConfig, "find_config", return_value=None),
                    patch.dict(os.environ, {}, clear=True),
                ):
                    output = self.execute(
                        [
                            "--key",
                            "KEY",
                            "--url",
                            "http://127.0.0.1:8000/api/",
                            "show",
                            "acl",
                        ],
                        settings=False,
                    )
            finally:
                os.chdir(current)

        self.assertIn("ACL", output)


class TestCommands(CLITestBase):
    """Individual command tests."""

    def test_version_bare(self) -> None:
        """Test version printing."""
        output = self.execute(["version", "--bare"])
        self.assertEqual(f"{wlc.__version__}\n", output)

    def test_ls(self) -> None:
        """Project listing."""
        output = self.execute(["ls"])
        self.assertIn("Hello", output)
        output = self.execute(["ls", "hello"])
        self.assertIn("Weblate", output)
        output = self.execute(["ls", "empty"])
        self.assertEqual("", output)

    def test_list_languages(self) -> None:
        """Language listing."""
        output = self.execute(["list-languages"])
        self.assertIn("Turkish", output)

    def test_list_projects(self) -> None:
        """Project listing."""
        output = self.execute(["list-projects"])
        self.assertIn("Hello", output)

    def test_list_components(self) -> None:
        """Components listing."""
        output = self.execute(["list-components"])
        self.assertIn("/hello/weblate", output)

        output = self.execute(["list-components", "hello"])
        self.assertIn("/hello/weblate", output)

        output = self.execute(["list-components", "hello/weblate"], expected=1)
        self.assertIn("This command is supported only at project level", output)

    def test_list_translations(self) -> None:
        """Translations listing."""
        output = self.execute(["list-translations"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(["list-translations", "hello/weblate"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(["list-translations", "hello/weblate"])
        self.assertIn("/hello/weblate/cs/", output)

        output = self.execute(
            ["--format", "json", "list-translations", "hello/weblate"]
        )
        self.assertIn("/hello/weblate/cs/", output)

    def test_show(self) -> None:
        """Project show."""
        output = self.execute(["show", "hello"])
        self.assertIn("Hello", output)

        output = self.execute(["show", "hello/weblate"])
        self.assertIn("Weblate", output)

        output = self.execute(["show", "hello/weblate/cs"])
        self.assertIn("/hello/weblate/cs/", output)

    def test_show_error(self) -> None:
        self.execute(["show", "io"], expected=10)
        with self.assertRaises(RuntimeError):
            self.execute(["show", "bug"])

    def test_delete(self) -> None:
        """Project delete."""
        output = self.execute(["delete", "hello"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate/cs"])
        self.assertEqual("", output)


class TestRepositoryCommands(CLITestBase):
    """Test repository management commands."""

    def test_commit(self) -> None:
        """Project commit."""
        output = self.execute(["commit", "hello"])
        self.assertEqual("", output)

        output = self.execute(["commit", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["commit", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_push(self) -> None:
        """Project push."""
        msg = "Error: Failed to push changes!\nPush is disabled for Hello/Weblate.\n"
        output = self.execute(["push", "hello"], expected=1)
        self.assertEqual(msg, output)

        output = self.execute(["push", "hello/weblate"], expected=1)
        self.assertEqual(msg, output)

        output = self.execute(["push", "hello/weblate/cs"], expected=1)
        self.assertEqual(msg, output)

    def test_pull(self) -> None:
        """Project pull."""
        output = self.execute(["pull", "hello"])
        self.assertEqual("", output)

        output = self.execute(["pull", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["pull", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_reset(self) -> None:
        """Project reset."""
        output = self.execute(["reset", "hello"])
        self.assertEqual("", output)

        output = self.execute(["reset", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["reset", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_cleanup(self) -> None:
        """Project cleanup."""
        output = self.execute(["cleanup", "hello"])
        self.assertEqual("", output)

        output = self.execute(["cleanup", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["cleanup", "hello/weblate/cs"])
        self.assertEqual("", output)

    def test_repo(self) -> None:
        """Project repo."""
        output = self.execute(["repo", "hello"])
        self.assertIn("needs_commit", output)

        output = self.execute(["repo", "hello/weblate"])
        self.assertIn("needs_commit", output)

        output = self.execute(["repo", "hello/weblate/cs"])
        self.assertIn("needs_commit", output)

    def test_stats(self) -> None:
        """Project stats."""
        output = self.execute(["stats", "hello"])
        self.assertIn("translated_percent", output)

        output = self.execute(["stats", "hello/weblate"])
        self.assertIn("failing_percent", output)

        output = self.execute(["stats", "hello/weblate/cs"])
        self.assertIn("failing_percent", output)

    def test_locks(self) -> None:
        """Project locks."""
        output = self.execute(["lock-status", "hello"], expected=1)
        self.assertIn("This command is supported only at component level", output)

        output = self.execute(["lock-status", "hello/weblate"])
        self.assertIn("locked", output)
        output = self.execute(["lock", "hello/weblate"])
        self.assertEqual("", output)
        output = self.execute(["unlock", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["lock-status", "hello/weblate/cs"], expected=1)
        self.assertIn("This command is supported only at component level", output)

    def test_changes(self) -> None:
        """Project changes."""
        output = self.execute(["changes", "hello"])
        self.assertIn("action_name", output)

        output = self.execute(["changes", "hello/weblate"])
        self.assertIn("action_name", output)

        output = self.execute(["changes", "hello/weblate/cs"])
        self.assertIn("action_name", output)


class TestFileCommands(CLITestBase):
    """Test translation file transfer commands."""

    def test_download(self) -> None:
        """Translation file downloads."""
        output = self.execute(["download"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "--output", tmpdirname])

        output = self.execute(["download", "hello/weblate/cs"])
        self.assertIn(b"Plural-Forms:", output)

        output = self.execute(
            ["download", "hello/weblate/cs"], stdout=True, expected=1, tty=True
        )
        self.assertIn("Refusing to write downloaded file to terminal", output)

        output = self.execute(["download", "hello/weblate/cs", "--convert", "csv"])
        self.assertIn(b'"location"', output)

        with NamedTemporaryFile() as handle:
            handle.close()
            self.execute(["download", "hello/weblate/cs", "-o", handle.name])
            output = Path(handle.name).read_bytes()
            self.assertIn(b"Plural-Forms:", output)

        output = self.execute(["download", "hello/weblate"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "hello/weblate", "--output", tmpdirname])

        output = self.execute(["download", "hello"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "hello", "--no-glossary", "--output", tmpdirname])
            # The hello-android should not be present as it is flagged as a glossary
            self.assertEqual(
                [path.name for path in Path(tmpdirname).iterdir()],
                ["hello-weblate.zip"],
            )

        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "download",
                    "hello",
                    "--convert",
                    "zip",
                    "--output",
                    str(Path(tmpdirname) / "output"),
                ]
            )
            self.assertEqual(
                [path.name for path in Path(tmpdirname).iterdir()], ["output"]
            )

    def test_download_config(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    str(TEST_CONFIG),
                    "--config-section",
                    "withcomponent",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(
                [path.name for path in Path(tmpdirname).iterdir()],
                ["hello-weblate.zip"],
            )
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    str(TEST_CONFIG),
                    "--config-section",
                    "withproject",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(
                {path.name for path in Path(tmpdirname).iterdir()},
                {"hello-weblate.zip", "hello-android.zip"},
            )

    def test_upload(self) -> None:
        """Translation file uploads."""
        msg = "Error: Failed to upload translations!\nNot found.\n"

        output = self.execute(["upload", "hello/weblate"], expected=1)
        self.assertEqual(
            "Error: This command is supported only at translation level\n", output
        )

        with self.get_text_io_wrapper("test upload data") as stdin:
            output = self.execute(["upload", "hello/weblate/cs"], stdin=stdin)
            self.assertEqual("", output)

        with self.get_text_io_wrapper("wrong upload data") as stdin:
            output = self.execute(
                ["upload", "hello/weblate/cs"], stdin=stdin, expected=1
            )
            self.assertEqual(msg, output)

        with NamedTemporaryFile(delete=False) as handle:
            handle.write(b"test upload overwrite")
            handle.close()
            output = self.execute(
                ["upload", "hello/weblate/cs", "-i", handle.name, "--overwrite"]
            )
            self.assertEqual("", output)

        with TemporaryDirectory() as tmpdirname:
            missing = Path(tmpdirname) / "missing.po"
            output = self.execute(
                ["upload", "hello/weblate/cs", "-i", str(missing)], expected=1
            )
            missing_error = FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), str(missing)
            )
            self.assertEqual(f"Error: {missing_error}\n", output)

    @staticmethod
    def get_text_io_wrapper(string: str) -> TextIOWrapper[BytesIO]:
        """Create a text io wrapper from a string."""
        return TextIOWrapper(BytesIO(string.encode()), "utf8")


class TestUnitCommands(CLITestBase):
    """Test unit management commands."""

    def test_list_units(self) -> None:
        """Unit listing."""
        output = self.execute(["list-units", "hello/weblate/cs"])
        self.assertIn("id", output)

        output = self.execute(
            ["list-units", "hello/weblate/cs", "--query", 'source:="mr"']
        )
        self.assertIn("117", output)

        output = self.execute(["list-units", "hello/weblate"], expected=1)
        self.assertIn("This command is supported only at translation level", output)

    def test_show_unit(self) -> None:
        """Unit show."""
        output = self.execute(["show", "123"])
        self.assertIn("123", output)
        self.assertIn("source", output)

    def test_delete_unit(self) -> None:
        """Unit delete."""
        output = self.execute(["delete", "123"])
        self.assertEqual("", output)

    def test_edit_unit(self) -> None:
        """Unit edit."""
        output = self.execute(["edit-unit", "123", "--target", "foo", "--state", "30"])
        self.assertEqual("", output)

        output = self.execute(["edit-unit", "hello/weblate/cs"], expected=1)
        self.assertIn("This command is supported only at unit level", output)

        output = self.execute(["edit-unit", "123"], expected=1)
        self.assertIn("No changes specified", output)


class TestErrors(CLITestBase):
    """Error handling tests."""

    def test_commandline_missing_key(self) -> None:
        """Configuration using command-line."""
        output = self.execute(
            ["--url", "http://denied.example.com", "list-projects"], expected=1
        )
        self.assertIn("Missing API key", output)
