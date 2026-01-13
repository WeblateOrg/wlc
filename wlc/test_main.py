# Copyright © Michal Čihař <michal@weblate.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test command-line interface."""

from __future__ import annotations

import json
import os
import sys
from abc import ABC
from io import BytesIO, StringIO, TextIOWrapper
from tempfile import NamedTemporaryFile, TemporaryDirectory

import wlc
from wlc.config import WeblateConfig
from wlc.main import Version, main

from .test_base import APITest

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")
TEST_CONFIG = os.path.join(TEST_DATA, "wlc")
TEST_SECTION = os.path.join(TEST_DATA, "section")


class CLITestBase(APITest, ABC):
    """Base class for CLI testing."""

    def execute(self, args, settings=None, stdout=None, stdin=None, expected=0):
        """Execute command and return output."""
        if settings is None:
            settings = ()
        elif not settings:
            settings = None
        output = StringIO()
        output.buffer = BytesIO()  # ty:ignore[invalid-assignment]
        backup = sys.stdout
        backup_err = sys.stderr
        try:
            sys.stdout = output
            sys.stderr = output
            if stdout:
                stdout = output
            result = main(args=args, settings=settings, stdout=stdout, stdin=stdin)
            self.assertEqual(result, expected)
        finally:
            sys.stdout = backup
            sys.stderr = backup_err
        result = output.buffer.getvalue()  # ty:ignore[unresolved-attribute]
        if result:
            return result
        return output.getvalue()


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
        self.assertIn("api/projects", output)

    def test_settings(self) -> None:
        """Configuration using settings param."""
        output = self.execute(
            ["list-projects"], settings=(("weblate", "url", "https://example.net/"),)
        )
        self.assertIn("Hello", output)

    def test_config(self) -> None:
        """Configuration using custom config file."""
        output = self.execute(
            ["--config", TEST_CONFIG, "list-projects"], settings=False
        )
        self.assertIn("Hello", output)

    def test_config_section(self) -> None:
        """Configuration using custom config file section."""
        output = self.execute(
            ["--config", TEST_SECTION, "--config-section", "custom", "list-projects"],
            settings=False,
        )
        self.assertIn("Hello", output)

    def test_config_key(self) -> None:
        """Configuration using custom config file section and key set is ignored."""
        output = self.execute(
            ["--config", TEST_CONFIG, "--config-section", "withkey", "show", "acl"],
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
            os.environ["APPDATA"] = TEST_DATA
            output = self.execute(["show", "acl"], settings=False)
            self.assertIn("ACL", output)
        finally:
            del os.environ["APPDATA"]

    def test_config_cwd(self) -> None:
        """Test loading settings from current dir."""
        current = os.path.abspath(".")
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), "test_data"))
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
            config.get("weblate", "method_whitelist"),
            "HEAD\nTRACE\nDELETE\nOPTIONS\nPUT\nGET",
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
        self.assertEqual(config.get("weblate", "method_whitelist"), "PUT,POST")
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
            method_whitelist,
            backoff_factor,
            _timeout,
        ) = config.get_request_options()
        self.assertEqual(retries, 999)
        self.assertEqual(status_forcelist, [429, 500, 502, 503, 504])
        self.assertEqual(method_whitelist, ["PUT", "POST"])
        self.assertEqual(backoff_factor, 0.2)

    def test_argv(self) -> None:
        """Test sys.argv processing."""
        backup = sys.argv
        try:
            sys.argv = ["wlc", "version"]
            output = self.execute(None)
            self.assertIn(f"version: {wlc.__version__}", output)
        finally:
            sys.argv = backup


class TestOutput(CLITestBase):
    """Test output formatting."""

    def test_version_text(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "text", "version"])
        self.assertIn(f"version: {wlc.__version__}", output)

    def test_version_json(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "json", "version"])
        values = json.loads(output)
        self.assertEqual({"version": wlc.__version__}, values)

    def test_version_csv(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "csv", "version"])
        self.assertIn(f"version,{wlc.__version__}", output)

    def test_version_html(self) -> None:
        """Test version printing."""
        output = self.execute(["--format", "html", "version"])
        self.assertIn(wlc.__version__, output)

    def test_projects_text(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "text", "list-projects"])
        self.assertIn("name: Hello", output)

    def test_projects_json(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "json", "list-projects"])
        values = json.loads(output)
        self.assertEqual(2, len(values))

    def test_projects_csv(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "csv", "list-projects"])
        self.assertIn("Hello", output)

    def test_projects_html(self) -> None:
        """Test projects printing."""
        output = self.execute(["--format", "html", "list-projects"])
        self.assertIn("Hello", output)

    def test_json_encoder(self) -> None:
        """Test JSON encoder."""
        output = StringIO()
        cmd = Version(args=[], config=WeblateConfig(), stdout=output)
        with self.assertRaises(TypeError):
            cmd.print_json(self)


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
        self.assertIn("Not supported", output)

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
        with self.assertRaises(FileNotFoundError):
            self.execute(["show", "bug"])

    def test_delete(self) -> None:
        """Project delete."""
        output = self.execute(["delete", "hello"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate"])
        self.assertEqual("", output)

        output = self.execute(["delete", "hello/weblate/cs"])
        self.assertEqual("", output)

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

    def test_download(self) -> None:
        """Translation file downloads."""
        output = self.execute(["download"], expected=1)
        self.assertIn("Output is needed", output)

        with TemporaryDirectory() as tmpdirname:
            self.execute(["download", "--output", tmpdirname])

        output = self.execute(["download", "hello/weblate/cs"])
        self.assertIn(b"Plural-Forms:", output)

        output = self.execute(["download", "hello/weblate/cs", "--convert", "csv"])
        self.assertIn(b'"location"', output)

        with NamedTemporaryFile() as handle:
            handle.close()
            self.execute(["download", "hello/weblate/cs", "-o", handle.name])
            with open(handle.name, "rb") as tmp:
                output = tmp.read()
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
            self.assertEqual(os.listdir(tmpdirname), ["hello-weblate.zip"])

        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "download",
                    "hello",
                    "--convert",
                    "zip",
                    "--output",
                    os.path.join(tmpdirname, "output"),
                ]
            )
            self.assertEqual(os.listdir(tmpdirname), ["output"])

    def test_download_config(self) -> None:
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    TEST_CONFIG,
                    "--config-section",
                    "withcomponent",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(os.listdir(tmpdirname), ["hello-weblate.zip"])
        with TemporaryDirectory() as tmpdirname:
            self.execute(
                [
                    "--config",
                    TEST_CONFIG,
                    "--config-section",
                    "withproject",
                    "download",
                    "--output",
                    tmpdirname,
                ],
                settings=False,
            )
            self.assertEqual(
                set(os.listdir(tmpdirname)), {"hello-weblate.zip", "hello-android.zip"}
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

    @staticmethod
    def get_text_io_wrapper(string):
        """Create a text io wrapper from a string."""
        return TextIOWrapper(BytesIO(string.encode()), "utf8")


class TestErrors(CLITestBase):
    """Error handling tests."""

    def test_commandline_missing_key(self) -> None:
        """Configuration using command-line."""
        output = self.execute(
            ["--url", "http://denied.example.com", "list-projects"], expected=1
        )
        self.assertIn("Missing API key", output)

    def test_commandline_wrong_key(self) -> None:
        """Configuration using command-line."""
        output = self.execute(
            ["--key", "x", "--url", "http://denied.example.com", "list-projects"],
            expected=1,
        )
        self.assertIn("was rejected by server", output)
